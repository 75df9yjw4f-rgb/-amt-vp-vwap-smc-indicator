#!/usr/bin/env python3
"""Create a DCA bot on Veles from the configuration in config.md.

The token is read from VELES_TOKEN and never written anywhere. Run it yourself:

    read -s VELES_TOKEN && export VELES_TOKEN
    python3 veles/create_bot.py --exchange bybit --pair BTCUSDT --base-order 30 --dry-run

Drop --dry-run only once the printed payload is what you want. The endpoint path
and field names below follow the documented shape of the Veles bot constructor;
if their API has renamed a field, the error response says which one, and this
script is deliberately small enough to adjust in place.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://veles.finance/api"


def payload(args):
    return {
        "name": args.name or f"DCA {args.pair} long",
        "exchange": args.exchange,
        "pair": args.pair,
        "direction": "long",
        "leverage": args.leverage,
        "base_order_size": args.base_order,
        "safety_orders": {
            "count": args.safety_orders,
            "step_percent": args.step,
            "step_scale": args.step_scale,
            "volume_scale": args.volume_scale,
        },
        "take_profit_percent": args.take_profit,
        "stop_loss_percent": args.stop_loss,     # None keeps it off
        "restart_after_close": True,
    }


def grid_maths(args):
    """What the configuration costs and how deep it reaches — before any order."""
    volumes = [1.0] + [1.0 * args.volume_scale ** (k + 1) for k in range(args.safety_orders)]
    depth, step = 0.0, args.step / 100.0
    for _ in range(args.safety_orders):
        depth += step
        step *= args.step_scale
    return sum(volumes), depth


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--exchange", required=True, help="bybit | binance | okx | ...")
    p.add_argument("--pair", required=True, help="e.g. BTCUSDT")
    p.add_argument("--name")
    p.add_argument("--base-order", type=float, required=True, help="start order size, quote currency")
    p.add_argument("--safety-orders", type=int, default=7)
    p.add_argument("--step", type=float, default=1.5, help="percent")
    p.add_argument("--step-scale", type=float, default=1.2)
    p.add_argument("--volume-scale", type=float, default=1.4)
    p.add_argument("--take-profit", type=float, default=1.5, help="percent")
    p.add_argument("--stop-loss", type=float, default=None, help="percent, omitted = off")
    p.add_argument("--leverage", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    units, depth = grid_maths(args)
    print(f"Полная сетка: {units:.1f} x стартовый ордер = "
          f"{units * args.base_order:,.2f} в валюте котировки")
    print(f"Последний страховочный ордер: -{depth:.1%} от цены входа")
    if args.leverage > 1:
        print(f"ВНИМАНИЕ: плечо {args.leverage} умножает и требуемую маржу, и убыток "
              f"ниже -{depth:.1%}")

    body = payload(args)
    print("\nPayload:")
    print(json.dumps(body, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("\n--dry-run: ничего не отправлено.")
        return 0

    token = os.environ.get("VELES_TOKEN")
    if not token:
        print("\nVELES_TOKEN не задан. Экспортируйте его и повторите.", file=sys.stderr)
        return 2

    req = urllib.request.Request(
        f"{API}/bots",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("\nСоздан:", r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"\nHTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
