import struct
import sys

R_ZPU_IM = 1
SHT_SYMTAB = 2
SHT_RELA = 4
SHT_NOBITS = 8
SHF_ALLOC = 2
SHN_UNDEF = 0


class LinkError(Exception):
    pass


class Obj:
    def __init__(self, data):
        if data[:4] != b"\x7fELF" or data[5] != 2:
            raise LinkError("not a big-endian elf32 object")
        e = struct.unpack(">16xHHIIIIIHHHHHH", data[:52])
        shoff, shentsize, shnum, shstrndx = e[5], e[10], e[11], e[12]
        self.data = data
        self.secs = []
        for i in range(shnum):
            off = shoff + i * shentsize
            self.secs.append(struct.unpack(">IIIIIIIIII", data[off:off + 40]))
        names = data[self.secs[shstrndx][4]:]
        self.names = [self._str(names, s[0]) for s in self.secs]
        self.symtab = next((i for i, s in enumerate(self.secs)
                            if s[1] == SHT_SYMTAB), None)

    @staticmethod
    def _str(blob, off):
        end = blob.index(b"\0", off)
        return blob[off:end].decode()

    def section_bytes(self, i):
        s = self.secs[i]
        if s[1] == SHT_NOBITS:
            return bytes(s[5])
        return self.data[s[4]:s[4] + s[5]]

    def symbols(self):
        sym = self.secs[self.symtab]
        strs = self.data[self.secs[sym[6]][4]:]
        out = []
        for off in range(sym[4], sym[4] + sym[5], 16):
            n, val, _, info, _, shndx = struct.unpack(
                ">IIIBBH", self.data[off:off + 16])
            out.append((self._str(strs, n), val, info >> 4, shndx))
        return out

    def relas(self):
        for s in self.secs:
            if s[1] != SHT_RELA:
                continue
            applies = s[7]
            for off in range(s[4], s[4] + s[5], 12):
                r_off, info, add = struct.unpack(">IIi", self.data[off:off + 12])
                yield applies, r_off, info >> 8, info & 0xff, add


def link(objects, base=0):
    objs = [Obj(d) for d in objects]
    image = bytearray()
    placed = {}  # (obj index, section index) -> address
    for oi, o in enumerate(objs):
        for si, s in enumerate(o.secs):
            if not (s[2] & SHF_ALLOC):
                continue
            align = s[8] or 1
            while (base + len(image)) % align:
                image.append(0)
            placed[(oi, si)] = base + len(image)
            image += o.section_bytes(si)

    globals_ = {}
    for oi, o in enumerate(objs):
        for name, val, bind, shndx in o.symbols():
            if shndx == SHN_UNDEF or (oi, shndx) not in placed:
                continue
            if bind == 1:  # global
                globals_[name] = placed[(oi, shndx)] + val

    def resolve(oi, idx):
        name, val, bind, shndx = objs[oi].symbols()[idx]
        if shndx != SHN_UNDEF and (oi, shndx) in placed:
            return placed[(oi, shndx)] + val
        if name in globals_:
            return globals_[name]
        raise LinkError("undefined symbol: " + name)

    for oi, o in enumerate(objs):
        for applies, r_off, sym, rtype, add in o.relas():
            if rtype != R_ZPU_IM:
                raise LinkError("unsupported relocation %d" % rtype)
            value = resolve(oi, sym) + add
            at = placed[(oi, applies)] - base + r_off
            for k in range(5):
                image[at + k] = 0x80 | ((value >> (7 * (4 - k))) & 0x7f)

    return bytes(image), globals_


def main(argv):
    out = argv[argv.index("-o") + 1]
    inputs = [a for a in argv[1:] if a != "-o" and a != out]
    objs = [open(p, "rb").read() for p in inputs]
    image, syms = link(objs)
    open(out, "wb").write(image)
    with open(out + ".map", "w") as f:
        for name, addr in sorted(syms.items(), key=lambda kv: kv[1]):
            f.write("%08x %s\n" % (addr, name))


if __name__ == "__main__":
    main(sys.argv)
