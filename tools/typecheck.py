"""Type-aware check of if/else branch compatibility in a Pine v6 source.

Added after TradingView's compiler reported

    Return type of one of the "if" or "switch" blocks is not compatible
    with return type of other block(s) (void; series bool)

A void/value scan found only that one site; inferring actual TYPES found nine.
Run before pasting into the Pine Editor:

    python3 tools/typecheck.py src/ACE.pine


Pine requires every branch of an if/else chain to have a compatible return type,
even when the `if` is used as a statement. int and float are mutually
compatible; everything else must match.
"""
import re, sys

SCALARS = {'int', 'float', 'bool', 'string', 'color'}

VOID_CALL = re.compile(
    r'^(array\.(set|push|unshift|clear|fill|sort|reverse|insert)|'
    r'(box|line|label|polyline|table)\.(set_\w+|delete|merge_cells)|'
    r'table\.(cell|clear)|runtime\.error|alertcondition|'
    r'plot|plotchar|plotshape|plotarrow|fill|hline|bgcolor|barcolor)\s*\(')

BUILTIN_TYPE = [
    (re.compile(r'^array\.(shift|pop|remove|get|max|min|sum|avg)\s*\('), 'ELEM'),
    (re.compile(r'^array\.(size|indexof|lastindexof|binary_search)\s*\('), 'int'),
    (re.compile(r'^array\.(includes)\s*\('), 'bool'),
    (re.compile(r'^array\.(copy|new|from)\s*'), 'array'),
    (re.compile(r'^(math|ta)\.\w+\s*\('), 'float'),
    (re.compile(r'^str\.\w+\s*\('), 'string'),
    (re.compile(r'^(box|line|label|table|polyline)\.new\s*\('), 'obj'),
    (re.compile(r'^nz\s*\('), 'float'),
    (re.compile(r'^na\s*\('), 'bool'),
]

def indent(l): return len(l) - len(l.lstrip())

def parse_types(lines):
    """variable -> type, and UDT field -> type."""
    var, field = {}, {}
    cur_udt = None
    for l in lines:
        s = l.rstrip()
        if not s.strip() or s.strip().startswith('//'): continue
        m = re.match(r'^type\s+(\w+)', s)
        if m: cur_udt = m.group(1); continue
        if cur_udt and indent(s) >= 4:
            m = re.match(r'^\s+(\w+(?:<[^>]+>)?)\s+(\w+)', s)
            if m: field[m.group(2)] = m.group(1)
            continue
        if indent(s) == 0: cur_udt = None
        m = re.match(r'^(?:var\s+|varip\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*=', s.lstrip())
        if m and (m.group(1) in SCALARS or m.group(1).startswith('array<')
                  or m.group(1)[:1].isupper()):
            var.setdefault(m.group(2), m.group(1))
    return var, field

def elem_of(arrname, var):
    t = var.get(arrname, '')
    m = re.match(r'array<(\w+)>', t)
    return m.group(1) if m else 'float'

def stmt_type(s, var, field, fns):
    s = s.strip()
    if not s or s.startswith('//') or s.startswith(('break', 'continue')): return None
    m = re.match(r'^([\w.]+)\s*(?::=|\+=|-=|\*=|/=|%=)', s)   # assignment / compound
    if m:
        name = m.group(1)
        return field.get(name.split('.')[-1], 'float') if '.' in name \
               else var.get(name, 'float')
    m = re.match(r'^(?:var\s+|varip\s+)?(\w+(?:<[^>]+>)?)\s+\w+\s*=', s)   # declaration
    if m and (m.group(1) in SCALARS or m.group(1).startswith('array<')
              or m.group(1)[:1].isupper()):
        return m.group(1)
    if re.match(r'^\[', s): return 'tuple'
    if VOID_CALL.match(s): return 'void'
    for rx, t in BUILTIN_TYPE:
        if rx.match(s):
            if t == 'ELEM':
                a = re.match(r'^array\.\w+\s*\(\s*(\w+)', s)
                return elem_of(a.group(1), var) if a else 'float'
            return t
    m = re.match(r'^(\w+)\s*\(', s)
    if m and m.group(1) in fns: return fns[m.group(1)]
    if re.match(r'^(true|false)\b', s): return 'bool'
    if re.match(r'^"', s): return 'string'
    if re.match(r'^-?\d+\.\d', s): return 'float'
    if re.match(r'^-?\d+\b', s): return 'int'
    if re.match(r'^\w+$', s): return var.get(s, 'unknown')
    return 'unknown'

def block_type(lines, start, base, var, field, fns):
    last, i = None, start
    while i < len(lines):
        l = lines[i]
        if not l.strip() or l.strip().startswith('//'): i += 1; continue
        if indent(l) < base: break
        if indent(l) == base:
            s = l.strip()
            if re.match(r'^(if|else|for|while|switch)\b', s):
                last = block_type(lines, i + 1, base + 4, var, field, fns) or 'void'
            else:
                t = stmt_type(s, var, field, fns)
                if t: last = t
        i += 1
    return last

def compatible(ts):
    ts = {t for t in ts if t not in (None, 'unknown')}
    if len(ts) <= 1: return True
    return ts <= {'int', 'float'}          # Pine auto-casts int -> float

src = open(sys.argv[1], encoding='utf-8').read().split('\n')
var, field = parse_types(src)
fns = {}
for _ in range(4):
    for i, l in enumerate(src):
        m = re.match(r'^(\w+)\s*\([^)]*\)\s*=>\s*$', l)
        if m: fns[m.group(1)] = block_type(src, i + 1, 4, var, field, fns) or 'void'

bad = []
for i, l in enumerate(src):
    s = l.strip()
    if not s.startswith('if ') or s.startswith('//'): continue
    base = indent(l)
    chain = [('if', i + 1, block_type(src, i + 1, base + 4, var, field, fns))]
    j = i + 1
    while j < len(src):
        lj = src[j]
        if lj.strip() and indent(lj) <= base:
            sj = lj.strip()
            if indent(lj) == base and (sj.startswith('else if ') or sj == 'else'):
                chain.append((sj.split()[0], j + 1,
                              block_type(src, j + 1, base + 4, var, field, fns)))
                j += 1; continue
            break
        j += 1
    if len(chain) > 1 and not compatible([t for _, _, t in chain]):
        bad.append((i + 1, s[:56], chain))

print(f"if/else chains with INCOMPATIBLE branch types: {len(bad)}\n")
for ln, s, ch in bad:
    print(f"  L{ln}: {s}")
    for tag, kl, t in ch:
        print(f"        {tag:8} ends ~L{kl:<5} -> {t}")
    print()
