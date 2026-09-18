#!/usr/bin/env python3
"""Compile-oriented static scan of a Pine v6 source.

Catches the error classes TradingView's compiler reports, without needing the
compiler:

  1. positional arguments landing in the wrong parameter slot
     (table.cell(id, col, row, text, <color>) -> `width` expects series int)
  2. a function referencing a global declared LATER in the file
     ("Undeclared identifier") - Pine resolves globals in source order
  3. positional/named argument mix-ups in the other drawing calls
  4. stateful ta.*() calls inside a conditional branch or behind and/or/?: -
     Pine needs them evaluated on EVERY bar or their series state falls behind
  5. functions approaching the 254 external-element limit Pine applies per
     function

if/else and switch branch-type compatibility lives in tools/typecheck.py.

    python3 tools/pinecheck.py src/ACE.pine
"""
import re, sys

# Calls whose first N positional parameters are safe; anything beyond N passed
# positionally is suspicious because the next slot has an unrelated type.
SAFE_POSITIONAL = {
    'table.cell': 4,      # table_id, column, row, text | then width (int)
    'box.new': 4,         # left, top, right, bottom
    'line.new': 4,        # x1, y1, x2, y2
    'label.new': 3,       # x, y, text
    'table.new': 3,       # position, columns, rows
    'plot': 5,            # series, title, color, linewidth, style
    'plotchar': 5,        # series, title, char, location, color
}

KEYWORDS = {
    'if','else','for','while','switch','var','varip','import','export','type',
    'enum','method','true','false','na','and','or','not','break','continue',
    'to','by','in','const','simple','series','input','float','int','bool',
    'string','color','line','label','box','table','array','matrix','map',
    'polyline','chart','linefill',
}

BUILTIN_VARS = {
    'open','high','low','close','volume','time','time_close','bar_index',
    'last_bar_index','last_bar_time','hl2','hlc3','ohlc4','hlcc4','year',
    'month','dayofmonth','dayofweek','weekofyear','hour','minute','second',
    'timenow','nz','na','fixnan','timestamp','indicator','strategy','library',
    'plot','plotchar','plotshape','plotarrow','plotcandle','plotbar','hline',
    'fill','bgcolor','barcolor','alertcondition','alert','runtime','max_bars_back',
}

NAMESPACES = {
    'math','str','ta','array','matrix','map','request','input','color','size',
    'location','scale','display','extend','format','text','position','order',
    'shape','plot','line','label','box','table','polyline','barmerge','xloc',
    'yloc','currency','adjustment','session','timeframe','syminfo','barstate',
    'chart','dayofweek','strategy','alert','runtime','linefill','earnings',
    'dividends','splits','font','hline','volume_row','footprint','ticker',
}

def indent(l): return len(l) - len(l.lstrip())

def strip_code(lines):
    out = []
    for l in lines:
        c = l.split('//')[0]
        out.append(re.sub(r'"[^"]*"', '""', c))
    return out

def split_args(s):
    """Top-level comma split."""
    args, depth, cur = [], 0, ''
    for ch in s:
        if ch in '([': depth += 1
        elif ch in ')]': depth -= 1
        if ch == ',' and depth == 0:
            args.append(cur); cur = ''
        else:
            cur += ch
    if cur.strip(): args.append(cur)
    return args

def find_calls(code, name):
    """Yield (line_index, argument_string) for each call to `name`."""
    joined = '\n'.join(code)
    for m in re.finditer(re.escape(name) + r'\s*\(', joined):
        i, depth, start = m.end(), 1, m.end()
        while i < len(joined) and depth:
            if joined[i] in '([': depth += 1
            elif joined[i] in ')]': depth -= 1
            i += 1
        yield joined[:m.start()].count('\n'), joined[start:i-1]

def main(path):
    raw = open(path, encoding='utf-8').read().split('\n')
    code = strip_code(raw)
    problems = []

    # ---- 1. positional arguments in the wrong slot -------------------------
    for fn, safe in SAFE_POSITIONAL.items():
        for ln, argstr in find_calls(code, fn):
            args = split_args(argstr)
            pos = 0
            for a in args:
                if re.match(r'^\s*\w+\s*=(?!=)', a): break
                pos += 1
            if pos > safe:
                problems.append(('POSITIONAL', ln + 1,
                    f"{fn}() has {pos} positional args (safe: {safe}) -> "
                    f"arg #{safe+1} is {args[safe].strip()[:40]!r}"))

    # ---- collect declarations ---------------------------------------------
    globals_ = {}                       # name -> line
    for i, l in enumerate(code):
        if not l.strip() or indent(l): continue
        m = re.match(r'^(?:var\s+|varip\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*=', l)
        if m: globals_.setdefault(m.group(1), i)
        m = re.match(r'^\[([^\]]+)\]\s*=', l)
        if m:
            for n in m.group(1).split(','): globals_.setdefault(n.strip(), i)
        m = re.match(r'^(\w+)\s*=(?!=)', l)
        if m: globals_.setdefault(m.group(1), i)

    fns, enums, udts, udt_fields = {}, set(), set(), set()
    for i, l in enumerate(code):
        m = re.match(r'^(\w+)\s*\(([^)]*)\)\s*=>\s*$', l)
        if m: fns[m.group(1)] = (i, m.group(2))
        m = re.match(r'^enum\s+(\w+)', l)
        if m: enums.add(m.group(1))
        m = re.match(r'^type\s+(\w+)', l)
        if m: udts.add(m.group(1))
    cur = None
    for i, l in enumerate(code):
        if re.match(r'^type\s+\w+', l): cur = True; continue
        if cur and indent(l) >= 4 and l.strip():
            m = re.match(r'^\s+\w+(?:<[^>]+>)?\s+(\w+)', l)
            if m: udt_fields.add(m.group(1))
        elif l.strip() and indent(l) == 0: cur = None

    known = set(globals_) | set(fns) | enums | udts | udt_fields | KEYWORDS | BUILTIN_VARS

    # ---- 2. function referencing a global declared later -------------------
    for fname, (fline, params) in fns.items():
        pnames = {p.strip().split()[-1] for p in params.split(',') if p.strip()}
        locals_ = set(pnames)
        j = fline + 1
        body = []
        while j < len(code):
            if code[j].strip() and indent(code[j]) == 0: break
            body.append((j, code[j])); j += 1
        for ln, l in body:
            m = re.match(r'^\s+(?:var\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*=', l)
            if m: locals_.add(m.group(1))
            m = re.match(r'^\s+for\s+(\w+)', l)
            if m: locals_.add(m.group(1))
            m = re.match(r'^\s+\[([^\]]+)\]\s*=', l)
            if m: locals_.update(n.strip() for n in m.group(1).split(','))
        for ln, l in body:
            for ident in re.findall(r'(?<![\w.])([A-Za-z_]\w*)', l):
                if ident in locals_ or ident in KEYWORDS or ident in NAMESPACES: continue
                if ident in globals_ and globals_[ident] > fline:
                    problems.append(('FORWARD_REF', ln + 1,
                        f"{fname}() uses global '{ident}' declared later at L{globals_[ident]+1}"))

    # NOTE: a general "undeclared identifier" heuristic was tried and removed.
    # Without real scope resolution it cannot tell locals, enum members and
    # named arguments from genuinely undeclared names, and reported hundreds of
    # false positives. The FORWARD_REF check above covers the case that actually
    # bit us, which is the one Pine reports as "Undeclared identifier".

    # ---- 4. stateful ta.*() that may not run on every bar --------------
    STATEFUL = ('crossover','crossunder','highestbars','lowestbars','vwap','barssince',
                'change','valuewhen','cum','sma','ema','rma','atr','highest','lowest',
                'pivothigh','pivotlow','rising','falling','mom','roc','stdev')
    for i, l in enumerate(code):
        # math.sum keeps a rolling window, so it belongs to the same class as
        # the stateful ta.* calls; TradingView reports it as CW10004.
        for m in re.finditer(r'\b(?:ta|math)\.(\w+)\s*\(', l):
            if m.group(1) not in STATEFUL and m.group(0).split('.')[0] != 'math':
                continue
            if m.group(0).startswith('math.') and m.group(1) != 'sum':
                continue
            indented = len(l) - len(l.lstrip()) > 0
            before = l[:m.start()]
            # Either operand of a ternary is conditional, not just the text
            # right after the `?`, so any unclosed `?` earlier on the line
            # counts - that is the CW10004 shape TradingView reports.
            guarded = bool(re.search(r'(\?|\band\b|\bor\b)\s*$', before.rstrip())) \
                      or '?' in re.sub(r'"[^"]*"', '', before)
            if indented or guarded:
                why = 'conditional scope' if indented else 'behind and/or/?: (short-circuit)'
                problems.append(('TA_SCOPE', i + 1,
                    f"{m.group(0)[:-1]}() in {why} - hoist it to global scope"))

    # ---- 5. external elements per function (transitive) ------------------
    # Pine counts, per user-defined function, the elements the body reaches
    # that live outside it - and it counts THROUGH calls, so a wrapper that
    # merely calls five helpers carries the union of all five. int/float/bool
    # cost 2, everything else 1. Calibrated against a TradingView-reported
    # 265 for renderDebug(), where this model gives 275.
    NUM = {'int', 'float', 'bool'}
    gtype = {}
    for l in code:
        m = re.match(r'^(?:var\s+|varip\s+)?(\w+)(?:<[^>]*>)?\s+(\w+)\s*=', l)
        # `float x = ...` declares x: the type word is a keyword, the NAME is
        # what we record, so KEYWORDS must not filter the declaration away.
        if m and m.group(1) not in ('if', 'else', 'for', 'while', 'switch'):
            gtype.setdefault(m.group(2), m.group(1))
    bodies = {}
    for fname, (fline, params) in fns.items():
        pl = [p.strip() for p in params.split(',') if p.strip()]
        pcost = sum(2 if p.split()[0] in NUM else 1 for p in pl)
        body, j2 = [], fline + 1
        while j2 < len(code):
            if code[j2].strip() and indent(code[j2]) == 0: break
            body.append(code[j2]); j2 += 1
        bodies[fname] = (pcost, {p.split()[-1] for p in pl}, '\n'.join(body))

    def reach(name, seen, globs, acc):
        if name in seen: return
        seen.add(name)
        pcost, pnames, body = bodies[name]
        acc[0] += pcost
        loc = set(pnames)
        for l in body.split('\n'):
            m = re.match(r'^\s+(?:var\s+)?(\w+)(?:<[^>]*>)?\s+(\w+)\s*=', l)
            if m: loc.add(m.group(2))
            m = re.match(r'^\s+for\s+(\w+)', l)
            if m: loc.add(m.group(1))
        for t in set(re.findall(r'(?<![\w.])([A-Za-z_]\w*)', body)):
            if t in gtype and t not in loc and t not in bodies:
                globs.add(t)
        for t in set(re.findall(r'(?<![\w.])(\w+)\s*\(', body)):
            if t in bodies: reach(t, seen, globs, acc)

    for fname, (fline, _) in fns.items():
        globs, acc = set(), [0]
        reach(fname, set(), globs, acc)
        est = acc[0] + sum(2 if gtype[g] in NUM else 1 for g in globs)
        if est > 230:
            problems.append(('EXTERNAL_ELEMENTS', fline + 1,
                f"{fname}() ~{est} external elements (limit 254) - split it, or "
                f"move the body to global scope if it is only a wrapper"))

    # ---- 5b. user functions that must run on every calculation -----------
    # A function whose own body reads a series at a VARIABLE offset (`src[i]`)
    # or calls a stateful builtin depends on Pine having maintained its history
    # on every bar. Calling it from a conditional scope is CW10003. Constant
    # offsets like `time[1]` do not count, which is why this looks at the
    # function's own body only and not at what it calls.
    hist = set()
    for fname, (pcost, pnames, body) in bodies.items():
        varoff = re.search(r'\w\s*\[\s*(?!\d+\s*\])[A-Za-z_]\w*\s*\]', body)
        stateful = re.search(r'\bta\.(?:' + '|'.join(STATEFUL) + r')\s*\(|\bmath\.sum\s*\(', body)
        if varoff or stateful:
            hist.add(fname)
    fnline = {fline for fline, _ in fns.values()}
    infn = False
    for i, l in enumerate(code):
        if i in fnline:
            infn = True
        elif l.strip() and indent(l) == 0:
            infn = False
        # The top level of a function body is unconditional, so the baseline to
        # compare against is 4 inside a function and 0 at global scope.
        base = 4 if infn else 0
        for m in re.finditer(r'(?<![\w.])(\w+)\s*\(', l):
            if m.group(1) not in hist:
                continue
            before = l[:m.start()]
            if indent(l) > base or '?' in re.sub(r'"[^"]*"', '', before):
                problems.append(('CONDITIONAL_CALL', i + 1,
                    f"{m.group(1)}() reads history at a variable offset and is "
                    f"called in conditional scope - make the call unconditional "
                    f"and pass the condition in as a parameter"))

    # ---- 6. same-scope duplicate declarations --------------------------
    # Pine allows the same name in sibling blocks (two `if` branches, two
    # `for` loops), so a flat name count produces false positives. Track the
    # indent stack instead: a declaration collides only with one already made
    # at the same indent inside the same enclosing block. This is the class
    # TradingView reports as `"x" is already defined (CE10095)`.
    DECL = re.compile(r'^(\s*)(?:var\s+|varip\s+)?'
                      r'(?:int|float|bool|string|color|line|label|box|table|array|matrix|map'
                      r'|linefill|polyline|chart\.point|[A-Z]\w*)'
                      r'(?:<[^>]+>)?\s+(\w+)\s*=(?!=)')
    scopes = [(-1, set())]          # (indent, names declared at that indent)
    for i, l in enumerate(code):
        if not l.strip():
            continue
        ind = indent(l)
        while len(scopes) > 1 and ind < scopes[-1][0]:
            scopes.pop()
        m = DECL.match(l)
        if not m:
            # a deeper line opens a nested scope for anything that follows
            if ind > scopes[-1][0]:
                scopes.append((ind, set()))
            continue
        name = m.group(2)
        if ind > scopes[-1][0]:
            scopes.append((ind, set()))
        names = scopes[-1][1]
        if name in names:
            problems.append(('DUPLICATE_DECL', i + 1,
                f"'{name}' is already defined in this scope (CE10095)"))
        names.add(name)

    # ---- report ------------------------------------------------------------
    seen = set()
    uniq = []
    for kind, ln, msg in problems:
        if (kind, ln, msg) in seen: continue
        seen.add((kind, ln, msg)); uniq.append((kind, ln, msg))
    print(f"{path}: {len(uniq)} problem(s)\n")
    for kind, ln, msg in sorted(uniq, key=lambda x: x[1]):
        print(f"  [{kind}] L{ln}: {msg}")
    return len(uniq)

if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1]) else 0)
