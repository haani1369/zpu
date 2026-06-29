WORD = 4
MASK = 0xffffffff


class ZPUError(Exception):
    pass


def _reverse_bits(value):
    result = 0
    for _ in range(32):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


class ZPU:
    def __init__(self, program, memory_size=4096):
        if len(program) > memory_size:
            raise ZPUError("program does not fit in memory")
        self.mem = bytearray(memory_size)
        self.mem[:len(program)] = program
        self.pc = 0
        self.sp = memory_size
        self.halted = False
        self._prev_im = False

    def read_word(self, addr):
        addr &= ~3
        if addr < 0 or addr + WORD > len(self.mem):
            raise ZPUError("read out of bounds at %d" % addr)
        return int.from_bytes(self.mem[addr:addr + WORD], "big")

    def write_word(self, addr, value):
        addr &= ~3
        if addr < 0 or addr + WORD > len(self.mem):
            raise ZPUError("write out of bounds at %d" % addr)
        self.mem[addr:addr + WORD] = (value & MASK).to_bytes(WORD, "big")

    def push(self, value):
        self.sp -= WORD
        self.write_word(self.sp, value)

    def pop(self):
        value = self.read_word(self.sp)
        self.sp += WORD
        return value

    def stack(self):
        return [self.read_word(a)
                for a in range(self.sp, len(self.mem), WORD)]

    def step(self):
        op = self.mem[self.pc]
        prev_im = self._prev_im
        self._prev_im = False
        branched = False

        if op & 0x80:
            imm = op & 0x7f
            if prev_im:
                self.push((self.pop() << 7 | imm) & MASK)
            else:
                if imm & 0x40:
                    imm |= 0xffffff80
                self.push(imm)
            self._prev_im = True
        elif op & 0xe0 == 0x40:
            offset = ((op & 0x1f) ^ 0x10) * WORD
            self.write_word(self.sp + offset, self.read_word(self.sp))
            self.sp += WORD
        elif op & 0xe0 == 0x60:
            offset = ((op & 0x1f) ^ 0x10) * WORD
            self.push(self.read_word(self.sp + offset))
        elif op & 0xf0 == 0x10:
            offset = (op & 0x0f) * WORD
            total = (self.read_word(self.sp)
                     + self.read_word(self.sp + offset)) & MASK
            self.write_word(self.sp, total)
        elif op & 0xe0 == 0x20:
            self.push((self.pc + 1) & MASK)
            self.pc = (op & 0x1f) * 32
            branched = True
        else:
            branched = self._execute_short(op)

        if not branched:
            self.pc += 1

    def _execute_short(self, op):
        if op == 0x00:
            self.halted = True
            return True
        if op == 0x02:
            self.push(self.sp)
            return False
        if op == 0x04:
            self.pc = self.pop()
            return True
        if op == 0x05:
            self.push((self.pop() + self.pop()) & MASK)
            return False
        if op == 0x06:
            self.push(self.pop() & self.pop())
            return False
        if op == 0x07:
            self.push(self.pop() | self.pop())
            return False
        if op == 0x08:
            self.push(self.read_word(self.pop()))
            return False
        if op == 0x09:
            self.push(~self.pop() & MASK)
            return False
        if op == 0x0a:
            self.push(_reverse_bits(self.pop()))
            return False
        if op == 0x0b:
            return False
        if op == 0x0c:
            addr = self.pop()
            self.write_word(addr, self.pop())
            return False
        if op == 0x0d:
            self.sp = self.pop()
            return False
        raise ZPUError("illegal opcode 0x%02x at %d" % (op, self.pc))

    def run(self, limit=1000000):
        steps = 0
        while not self.halted:
            if steps >= limit:
                raise ZPUError("step limit exceeded")
            self.step()
            steps += 1
        return steps
