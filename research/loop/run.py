"""CLI for the loop: `step N` runs until N trades close, then stops."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import run

BARS = None   # задаётся при старте нового эксперимента
POL = 'research/loop/policies'
LED = 'research/loop/state/ledger.jsonl'

if __name__ == '__main__':
    if BARS is None or len(sys.argv) < 3:
        sys.exit('Состояние пусто. Запуск: run.py <файл баров> <сделок в партии>\n'
                 'Сначала нужен каталог политик с v1.json — политик прошлого эксперимента больше нет.')
    bars, n = sys.argv[1], int(sys.argv[2])
    made = run(bars, POL, LED, stop_after_trades=n)
    print(f"--- закрыто сделок в этой партии: {made} ---")
