from zpu import MASK

NULLARY = {
    "breakpoint": 0x00,
    "pushsp": 0x02,
    "poppc": 0x04,
    "add": 0x05,
    "and": 0x06,
    "or": 0x07,
    "load": 0x08,
    "not": 0x09,
    "flip": 0x0a,
    "nop": 0x0b,
    "store": 0x0c,
    "popsp": 0x0d,
    "loadh": 0x22,
    "storeh": 0x23,
    "loadb": 0x33,
    "storeb": 0x34,
    "lessthan": 0x24,
    "lessthanorequal": 0x25,
    "ulessthan": 0x26,
    "ulessthanorequal": 0x27,
    "call": 0x2d,
    "mult": 0x29,
    "lshiftright": 0x2a,
    "ashiftleft": 0x2b,
    "ashiftright": 0x2c,
    "eq": 0x2e,
    "neq": 0x2f,
    "neg": 0x30,
    "sub": 0x31,
    "xor": 0x32,
    "div": 0x35,
    "mod": 0x36,
    "eqbranch": 0x37,
    "neqbranch": 0x38,
}

LABEL_IM_BYTES = 5


class AsmError(Exception):
    pass


def _is_number(token):
    try:
        int(token, 0)
        return True
    except ValueError:
        return False


def _number(token):
    if token is None:
        raise AsmError("missing operand")
    return int(token, 0)


def _im_minimal(value):
    value &= MASK
    if value & 0x80000000:
        value -= 0x100000000
    chunks = []
    while True:
        chunk = value & 0x7f
        value >>= 7
        chunks.append(chunk)
        if value == 0 and not chunk & 0x40:
            break
        if value == -1 and chunk & 0x40:
            break
    chunks.reverse()
    return bytes(0x80 | c for c in chunks)


def _im_fixed(value, count):
    value &= MASK
    return bytes(0x80 | (value >> 7 * (count - 1 - i) & 0x7f)
                 for i in range(count))


def _offset_field(token, limit):
    n = _number(token)
    if n < 0 or n > limit or n % 4:
        raise AsmError("offset must be a multiple of 4 in 0..%d" % limit)
    return n // 4


def _expand(rows):
    prev_im = False
    for names, mnemonic, operand in rows:
        if mnemonic == "im" and prev_im:
            yield ("insn", "nop", None)
        for name in names:
            yield ("label", name)
        if mnemonic is not None:
            yield ("insn", mnemonic, operand)
            prev_im = mnemonic == "im"


def _tokenize(source):
    rows = []
    for raw in source.splitlines():
        tokens = raw.split(";", 1)[0].split()
        labels = []
        i = 0
        while i < len(tokens) and tokens[i].endswith(":"):
            labels.append(tokens[i][:-1])
            i += 1
        mnemonic = operand = None
        if i < len(tokens):
            mnemonic = tokens[i].lower()
            i += 1
        if i < len(tokens):
            operand = tokens[i]
            i += 1
        if i < len(tokens):
            raise AsmError("unexpected token: %s" % tokens[i])
        if labels or mnemonic:
            rows.append((labels, mnemonic, operand))
    return rows


def _length(mnemonic, operand):
    if mnemonic == "im":
        if operand is None:
            raise AsmError("im requires an operand")
        if _is_number(operand):
            return len(_im_minimal(_number(operand)))
        return LABEL_IM_BYTES
    return 1


def _resolve(rows):
    labels = {}
    addr = 0
    for unit in _expand(rows):
        if unit[0] == "label":
            if unit[1] in labels:
                raise AsmError("duplicate label: %s" % unit[1])
            labels[unit[1]] = addr
        else:
            addr += _length(unit[1], unit[2])
    return labels


def _encode(mnemonic, operand, labels):
    if mnemonic == "im":
        if _is_number(operand):
            return _im_minimal(_number(operand))
        if operand not in labels:
            raise AsmError("unknown label: %s" % operand)
        return _im_fixed(labels[operand], LABEL_IM_BYTES)
    if mnemonic == "loadsp":
        return bytes([0x60 | _offset_field(operand, 124) ^ 0x10])
    if mnemonic == "storesp":
        return bytes([0x40 | _offset_field(operand, 124) ^ 0x10])
    if mnemonic == "addsp":
        return bytes([0x10 | _offset_field(operand, 60)])
    if mnemonic == "emulate":
        n = _number(operand)
        if n < 0 or n > 31:
            raise AsmError("emulate vector must be in 0..31")
        return bytes([0x20 | n])
    if mnemonic in NULLARY:
        if operand is not None:
            raise AsmError("%s takes no operand" % mnemonic)
        return bytes([NULLARY[mnemonic]])
    raise AsmError("unknown mnemonic: %s" % mnemonic)


def assemble(source):
    rows = _tokenize(source)
    labels = _resolve(rows)
    out = bytearray()
    for unit in _expand(rows):
        if unit[0] == "insn":
            out += _encode(unit[1], unit[2], labels)
    return bytes(out)
