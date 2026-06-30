import struct
import sys

R_ZPU_IM = 1
SHT_SYMTAB = 2
SHT_RELA = 4
SHT_NOBITS = 8
SHF_ALLOC = 2
SHN_UNDEF = 0
STB_GLOBAL = 1

EHDR_SIZE = 52
SHDR_SIZE = 40
SYM_SIZE = 16
RELA_SIZE = 12


class LinkError(Exception):
    pass


def _section_kind(name):
    if name.startswith(".text"):
        return 0
    if name.startswith(".rodata"):
        return 1
    if name.startswith(".bss"):
        return 3
    return 2  # .data and anything else allocatable


class Obj:
    def __init__(self, data, name="<object>"):
        self.data = data
        self.name = name
        if len(data) < EHDR_SIZE:
            raise LinkError("%s: truncated elf header" % name)
        if data[:4] != b"\x7fELF":
            raise LinkError("%s: not an elf object" % name)
        ei_class, ei_data, ei_version = data[4], data[5], data[6]
        if ei_class != 1:
            raise LinkError("%s: not a 32-bit elf object" % name)
        if ei_data != 2:
            raise LinkError("%s: not a big-endian elf object" % name)
        if ei_version != 1:
            raise LinkError("%s: unsupported elf identification version" %
                            name)

        (_, _, e_version, _, _, shoff, _, ehsize, _, _, shentsize, shnum,
         shstrndx) = struct.unpack(">HHIIIIIHHHHHH", data[16:EHDR_SIZE])
        if e_version != 1:
            raise LinkError("%s: unsupported elf version" % name)
        if shentsize != 0 and shentsize != SHDR_SIZE:
            raise LinkError("%s: unsupported section header size" % name)

        self.secs = []
        for i in range(shnum):
            off = shoff + i * SHDR_SIZE
            self._require(off, SHDR_SIZE, "section header %d" % i)
            self.secs.append(struct.unpack(">IIIIIIIIII",
                                           data[off:off + SHDR_SIZE]))
        if shstrndx >= len(self.secs):
            raise LinkError("%s: section name string table index out of "
                            "range" % name)

        strtab_off, strtab_size = self.secs[shstrndx][4], self.secs[shstrndx][5]
        self._require(strtab_off, strtab_size, "section name string table")
        names_blob = data[strtab_off:strtab_off + strtab_size]
        self.names = [self._str(names_blob, s[0], "a section name")
                     for s in self.secs]

        self.symtab = next((i for i, s in enumerate(self.secs)
                            if s[1] == SHT_SYMTAB), None)

    def _require(self, off, size, what):
        if off < 0 or size < 0 or off + size > len(self.data):
            raise LinkError("%s: %s out of bounds" % (self.name, what))

    def _str(self, blob, off, what):
        if off < 0 or off > len(blob):
            raise LinkError("%s: %s out of bounds" % (self.name, what))
        end = blob.find(b"\0", off)
        if end < 0:
            raise LinkError("%s: %s is not nul-terminated" % (self.name, what))
        return blob[off:end].decode()

    def section_bytes(self, i):
        s = self.secs[i]
        if s[1] == SHT_NOBITS:
            return bytes(s[5])
        self._require(s[4], s[5], "section %s" % self.names[i])
        return self.data[s[4]:s[4] + s[5]]

    def symbols(self):
        if self.symtab is None:
            return []
        sym = self.secs[self.symtab]
        if sym[6] >= len(self.secs):
            raise LinkError("%s: symbol table string table index out of "
                            "range" % self.name)
        strtab = self.secs[sym[6]]
        self._require(strtab[4], strtab[5], "symbol string table")
        strs = self.data[strtab[4]:strtab[4] + strtab[5]]
        self._require(sym[4], sym[5], "symbol table")
        if sym[5] % SYM_SIZE:
            raise LinkError("%s: symbol table size is not a multiple of "
                            "the entry size" % self.name)
        out = []
        for off in range(sym[4], sym[4] + sym[5], SYM_SIZE):
            n, val, _, info, _, shndx = struct.unpack(
                ">IIIBBH", self.data[off:off + SYM_SIZE])
            reserved = shndx >= 0xff00  # SHN_ABS, SHN_COMMON, ...
            if shndx != SHN_UNDEF and not reserved and shndx >= len(self.secs):
                raise LinkError("%s: symbol section index out of range" %
                                self.name)
            out.append((self._str(strs, n, "a symbol name"), val, info >> 4,
                       shndx))
        return out

    def relas(self):
        for si, s in enumerate(self.secs):
            if s[1] != SHT_RELA:
                continue
            applies = s[7]
            if applies >= len(self.secs):
                raise LinkError("%s: relocation section %s targets an "
                                "out-of-range section" %
                                (self.name, self.names[si]))
            self._require(s[4], s[5], "relocation section %s" %
                         self.names[si])
            if s[5] % RELA_SIZE:
                raise LinkError("%s: relocation section %s size is not a "
                                "multiple of the entry size" %
                                (self.name, self.names[si]))
            for off in range(s[4], s[4] + s[5], RELA_SIZE):
                r_off, info, add = struct.unpack(">IIi",
                                                 self.data[off:off + RELA_SIZE])
                yield applies, r_off, info >> 8, info & 0xff, add


def _im(value):
    value &= 0xffffffff
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
    return bytes(0x80 | c for c in reversed(chunks))


_NOP = bytes([0x0b])
_TRAMPOLINE_ALIGN = 4


def _entry_trampoline(unshifted_entry_addr):
    # im 0 (reserve the result slot), im <ret>, im <entry>, call,
    # ret: breakpoint, then enough trailing nops to round the whole
    # trampoline up to a 4-byte multiple. A nop separates each pair of
    # adjacent im runs, since the hardware otherwise chains them into a
    # single immediate; the trailing padding keeps the trampoline's total
    # length (the shift applied to every other section) a multiple of the
    # alignment those sections already assume, so inserting it never
    # changes how much front-padding they need.
    #
    # the entry symbol's final address and the offset of the trailing
    # breakpoint both depend on the trampoline's own length, so both are
    # solved for as fixed points: the inner loop finds the unpadded length
    # for a given total length, the outer loop finds a total length whose
    # padding is consistent with itself.
    length = _TRAMPOLINE_ALIGN
    for _ in range(20):
        entry_im = _im(unshifted_entry_addr + length)
        ret = 0
        for _ in range(20):
            body = _im(0) + _NOP + _im(ret) + _NOP + entry_im + \
                bytes([0x2d, 0x00])
            if len(body) - 1 == ret:
                break
            ret = len(body) - 1
        else:
            raise LinkError("entry trampoline return address did not "
                            "converge")
        unpadded = len(body)
        padded = -(-unpadded // _TRAMPOLINE_ALIGN) * _TRAMPOLINE_ALIGN
        body += _NOP * (padded - unpadded)
        if padded == length:
            return body
        length = padded
    raise LinkError("entry trampoline did not converge")


def _layout_and_resolve(objs, base):
    placed = {}  # (obj index, section index) -> address
    by_kind = {k: [] for k in range(4)}
    for oi, o in enumerate(objs):
        for si, s in enumerate(o.secs):
            if not (s[2] & SHF_ALLOC):
                continue
            by_kind[_section_kind(o.names[si])].append((oi, si))

    image = bytearray()
    for kind in range(4):
        for oi, si in by_kind[kind]:
            s = objs[oi].secs[si]
            align = s[8] or 1
            while (base + len(image)) % align:
                image.append(0)
            placed[(oi, si)] = base + len(image)
            image += objs[oi].section_bytes(si)

    globals_ = {}
    defined_at = {}
    for oi, o in enumerate(objs):
        for name, val, bind, shndx in o.symbols():
            if shndx == SHN_UNDEF or (oi, shndx) not in placed:
                continue
            if bind != STB_GLOBAL:
                continue
            addr = placed[(oi, shndx)] + val
            if name in globals_:
                raise LinkError("duplicate definition of '%s' (in %s and %s)"
                                % (name, defined_at[name], o.name))
            globals_[name] = addr
            defined_at[name] = o.name

    def resolve(oi, idx, context):
        syms = objs[oi].symbols()
        if idx >= len(syms):
            raise LinkError("%s: %s references an out-of-range symbol table "
                            "entry" % (objs[oi].name, context))
        name, val, bind, shndx = syms[idx]
        if shndx != SHN_UNDEF and (oi, shndx) in placed:
            return placed[(oi, shndx)] + val
        if name in globals_:
            return globals_[name]
        raise LinkError("%s: undefined symbol '%s' referenced at %s" %
                        (objs[oi].name, name, context))

    for oi, o in enumerate(objs):
        for applies, r_off, sym, rtype, add in o.relas():
            if rtype != R_ZPU_IM:
                raise LinkError("%s: unsupported relocation type %d" %
                                (o.name, rtype))
            context = "offset %#x in %s" % (r_off, o.names[applies])
            if (oi, applies) not in placed:
                raise LinkError("%s: relocation at %s targets a "
                                "non-allocatable section" % (o.name, context))
            at = placed[(oi, applies)] - base + r_off
            if at < 0 or at + 5 > len(image):
                raise LinkError("%s: relocation at %s is out of bounds" %
                                (o.name, context))
            value = resolve(oi, sym, context) + add
            for k in range(5):
                image[at + k] = 0x80 | ((value >> (7 * (4 - k))) & 0x7f)

    return bytes(image), globals_


def link(objects, entry="main"):
    objs = [Obj(d, "object %d" % i) for i, d in enumerate(objects)]

    if entry is None:
        return _layout_and_resolve(objs, base=0)

    _, unshifted_globals = _layout_and_resolve(objs, base=0)
    if entry not in unshifted_globals:
        raise LinkError("undefined entry symbol '%s'" % entry)
    trampoline = _entry_trampoline(unshifted_globals[entry])

    image, globals_ = _layout_and_resolve(objs, base=len(trampoline))
    return trampoline + image, globals_


def main(argv):
    args = argv[1:]
    out = None
    entry = "main"
    map_path = None
    inputs = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-o":
            i += 1
            out = args[i]
        elif a == "--entry":
            i += 1
            entry = args[i]
        elif a == "--map":
            i += 1
            map_path = args[i]
        else:
            inputs.append(a)
        i += 1

    if out is None:
        raise LinkError("missing -o output path")
    if not inputs:
        raise LinkError("no input objects")

    objs = [open(p, "rb").read() for p in inputs]
    image, syms = link(objs, entry=entry)
    with open(out, "wb") as f:
        f.write(image)
    with open(map_path or out + ".map", "w") as f:
        for name, addr in sorted(syms.items(), key=lambda kv: kv[1]):
            f.write("%08x %s\n" % (addr, name))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except LinkError as e:
        sys.exit("zpld: %s" % e)
