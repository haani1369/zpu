import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))

from zpu import ZPU
import zpld

CLANG = os.path.join(ROOT, "llvm-project/build/bin/clang")

R_ZPU_IM = 1
SHT_PROGBITS = 1
SHT_NOBITS = 8
SHF_ALLOC = 2
SHF_EXECINSTR = 4
STB_LOCAL = 0
STB_GLOBAL = 1


def compile_obj(src, workdir):
    path = os.path.join(workdir, "t%d.c" % len(os.listdir(workdir)))
    open(path, "w").write(src)
    obj = path[:-2] + ".o"
    subprocess.run([CLANG, "--target=zpu", "-O2", "-fno-builtin", "-c", path,
                    "-o", obj], check=True)
    return open(obj, "rb").read()


def link_and_run(objs, entry="main", limit=200000):
    image, syms = zpld.link(objs, entry=entry)
    cpu = ZPU(image, memory_size=len(image) + 8192)
    cpu.run(limit=limit)
    return cpu, syms


class ObjBuilder:
    """Builds a minimal big-endian elf32 relocatable object by hand, the
    same shape llc -filetype=obj emits, for tests that exercise the
    linker's handling of symbol tables and relocations directly rather
    than real generated code."""

    def __init__(self):
        self.sections = [{"name": "", "type": 0, "flags": 0, "align": 0,
                          "data": b""}]
        self.section_index = {}
        self.symbols = [("", 0, STB_LOCAL, 0)]
        self.symbol_index = {}
        self.relocs = {}

    def add_section(self, name, data=b"", flags=SHF_ALLOC, align=1,
                    nobits=False):
        idx = len(self.sections)
        self.sections.append({"name": name,
                              "type": SHT_NOBITS if nobits else SHT_PROGBITS,
                              "flags": flags, "align": align, "data": data})
        self.section_index[name] = idx
        return idx

    def add_symbol(self, name, value, bind, section_name):
        shndx = self.section_index[section_name] if section_name else 0
        idx = len(self.symbols)
        self.symbols.append((name, value, bind, shndx))
        self.symbol_index[name] = idx
        return idx

    def add_reloc(self, section_name, offset, symbol_name, addend=0):
        self.relocs.setdefault(section_name, []).append(
            (offset, self.symbol_index[symbol_name], addend))

    def build(self):
        strtab = bytearray(b"\0")
        str_off = {}
        for name, *_ in self.symbols:
            if name and name not in str_off:
                str_off[name] = len(strtab)
                strtab += name.encode() + b"\0"

        symtab = bytearray()
        for name, value, bind, shndx in self.symbols:
            symtab += struct.pack(">IIIBBH", str_off.get(name, 0), value, 0,
                                  bind << 4, 0, shndx)

        secs = [dict(s) for s in self.sections]
        symtab_idx = len(secs)
        strtab_idx = symtab_idx + 1
        secs.append({"name": ".symtab", "type": 2, "flags": 0, "align": 4,
                     "data": bytes(symtab), "link": strtab_idx, "info": 1,
                     "entsize": 16})
        secs.append({"name": ".strtab", "type": 3, "flags": 0, "align": 1,
                     "data": bytes(strtab)})

        for sec_name, entries in self.relocs.items():
            applies = self.section_index[sec_name]
            data = bytearray()
            for offset, sym, addend in entries:
                data += struct.pack(">IIi", offset, (sym << 8) | R_ZPU_IM,
                                    addend)
            secs.append({"name": ".rela" + sec_name, "type": 4, "flags": 0,
                         "align": 4, "data": bytes(data), "link": symtab_idx,
                         "info": applies, "entsize": 12})

        shstrtab = bytearray(b"\0")
        shstr_off = {}
        for s in secs:
            if s["name"] not in shstr_off:
                shstr_off[s["name"]] = len(shstrtab)
                shstrtab += s["name"].encode() + b"\0"
        shstrtab_idx = len(secs)
        secs.append({"name": ".shstrtab", "type": 3, "flags": 0, "align": 1,
                     "data": b""})
        if ".shstrtab" not in shstr_off:
            shstr_off[".shstrtab"] = len(shstrtab)
            shstrtab += b".shstrtab\0"
        secs[shstrtab_idx]["data"] = bytes(shstrtab)

        ehsize, shentsize = 52, 40
        offset = ehsize
        offsets = []
        for s in secs:
            align = s["align"] or 1
            offset = (offset + align - 1) // align * align
            offsets.append(offset)
            if s["type"] != SHT_NOBITS:
                offset += len(s["data"])
        shoff = offset

        body = bytearray(shoff - ehsize)
        for s, off in zip(secs, offsets):
            if s["type"] != SHT_NOBITS:
                body[off - ehsize:off - ehsize + len(s["data"])] = s["data"]

        shdrs = bytearray()
        for s, off in zip(secs, offsets):
            shdrs += struct.pack(
                ">IIIIIIIIII", shstr_off[s["name"]], s["type"], s["flags"],
                0, off if s["type"] != SHT_NOBITS else 0, len(s["data"]),
                s.get("link", 0), s.get("info", 0), s["align"],
                s.get("entsize", 0))

        ident = b"\x7fELF" + bytes([1, 2, 1]) + b"\0" * 9
        ehdr = ident + struct.pack(
            ">HHIIIIIHHHHHH", 1, 0, 1, 0, 0, shoff, 0, ehsize, 0, 0,
            shentsize, len(secs), shstrtab_idx)
        return bytes(ehdr) + bytes(body) + bytes(shdrs)


# --- tests against real compiler output ---------------------------------


def test_entry_trampoline_calls_main_and_halts():
    with tempfile.TemporaryDirectory() as d:
        obj = compile_obj("int main(void) { return 42; }", d)
        cpu, syms = link_and_run([obj])
    assert cpu.halted
    assert cpu.stack()[0] == 42


def test_cross_object_call():
    with tempfile.TemporaryDirectory() as d:
        a = compile_obj("extern int seven(void);\n"
                        "int main(void) { return seven(); }", d)
        b = compile_obj("int seven(void) { return 7; }", d)
        cpu, syms = link_and_run([a, b])
    assert cpu.stack()[0] == 7


def test_bss_global_across_objects():
    with tempfile.TemporaryDirectory() as d:
        a = compile_obj("int counter;", d)
        b = compile_obj("extern int counter;\n"
                        "int main(void) { return counter; }", d)
        cpu, syms = link_and_run([a, b])
    assert cpu.stack()[0] == 0


def test_locals_with_the_same_name_do_not_collide():
    with tempfile.TemporaryDirectory() as d:
        a = compile_obj("static int helper(void) { return 5; }\n"
                        "int main(void) { return helper(); }", d)
        b = compile_obj("static int helper(void) { return 9; }\n"
                        "int other(void) { return helper(); }", d)
        cpu_main, _ = link_and_run([a, b], entry="main")
        cpu_other, _ = link_and_run([a, b], entry="other")
    assert cpu_main.stack()[0] == 5
    assert cpu_other.stack()[0] == 9


def test_i64_multiply_through_the_runtime():
    with tempfile.TemporaryDirectory() as d:
        user = compile_obj(
            "long long mul(long long a, long long b) { return a * b; }\n"
            "int main(void) { return (int)mul(123456789012LL, 3); }", d)
        builtins = compile_obj(open(os.path.join(ROOT, "runtime",
                                                  "builtins.c")).read(), d)
        cpu, _ = link_and_run([user, builtins])
    expected = (123456789012 * 3) & 0xffffffff
    if expected & 0x80000000:
        expected -= 0x100000000
    assert cpu.stack()[0] == expected & 0xffffffff


# --- tests against hand-built objects (structural / error paths) -------


def test_undefined_symbol_error_names_the_symbol():
    b = ObjBuilder()
    b.add_section(".text", bytes([0x80] * 5 + [0x2d]),
                  flags=SHF_ALLOC | SHF_EXECINSTR, align=4)
    b.add_symbol("_missing_", 0, STB_GLOBAL, "")
    b.add_symbol("main", 0, STB_GLOBAL, ".text")
    b.add_reloc(".text", 0, "_missing_", 0)
    try:
        zpld.link([b.build()])
        assert False, "expected a LinkError"
    except zpld.LinkError as e:
        assert "_missing_" in str(e)


def test_duplicate_global_definition_is_an_error():
    def make():
        b = ObjBuilder()
        b.add_section(".text", bytes([0x00]),
                      flags=SHF_ALLOC | SHF_EXECINSTR, align=4)
        b.add_symbol("dup", 0, STB_GLOBAL, ".text")
        return b.build()

    try:
        zpld.link([make(), make()])
        assert False, "expected a LinkError"
    except zpld.LinkError as e:
        assert "dup" in str(e)


def test_sections_are_grouped_by_kind_across_objects():
    def make(text_byte, rodata_byte):
        b = ObjBuilder()
        b.add_section(".text", bytes([text_byte]),
                      flags=SHF_ALLOC | SHF_EXECINSTR, align=4)
        b.add_section(".rodata", bytes([rodata_byte]), flags=SHF_ALLOC,
                      align=4)
        return b

    a = make(0x11, 0xaa)
    z = make(0x22, 0xbb)
    image, syms = zpld.link([a.build(), z.build()], entry=None)
    assert (image.index(0x11) < image.index(0x22) < image.index(0xaa) <
           image.index(0xbb))


def test_large_relocation_addend_packs_correctly():
    pad = ObjBuilder()
    pad.add_section(".text", bytes(2000), flags=SHF_ALLOC | SHF_EXECINSTR,
                    align=4)
    pad.add_symbol("pad", 0, STB_GLOBAL, ".text")

    user = ObjBuilder()
    user.add_section(".text", bytes([0x80] * 5),
                     flags=SHF_ALLOC | SHF_EXECINSTR, align=4)
    user.add_symbol("pad", 0, STB_GLOBAL, "")
    user.add_reloc(".text", 0, "pad", 0)
    user.add_symbol("user_target", 0, STB_GLOBAL, ".text")

    image, syms = zpld.link([pad.build(), user.build()], entry=None)
    at = syms["user_target"]
    value = 0
    for c in image[at:at + 5]:
        value = (value << 7) | (c & 0x7f)
    assert value == syms["pad"]


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


if __name__ == "__main__":
    main()
