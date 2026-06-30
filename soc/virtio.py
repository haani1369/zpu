MAGICVALUE = 0x000
VERSION = 0x004
DEVICEID = 0x008
VENDORID = 0x00c
DEVICEFEATURES = 0x010
DEVICEFEATURESSEL = 0x014
DRIVERFEATURES = 0x020
DRIVERFEATURESSEL = 0x024
QUEUESEL = 0x030
QUEUENUMMAX = 0x034
QUEUENUM = 0x038
QUEUEREADY = 0x044
QUEUENOTIFY = 0x050
INTERRUPTSTATUS = 0x060
INTERRUPTACK = 0x064
STATUS = 0x070
QUEUEDESCLOW = 0x080
QUEUEDESCHIGH = 0x084
QUEUEAVAILLOW = 0x090
QUEUEAVAILHIGH = 0x094
QUEUEUSEDLOW = 0x0a0
QUEUEUSEDHIGH = 0x0a4
CONFIGGENERATION = 0x0fc
CONFIG = 0x100

DESCRIPTOR_WORDS = 5
DESCRIPTOR_BYTES = DESCRIPTOR_WORDS * 4
FLAG_NEXT = 1
FLAG_WRITE = 2


class Virtqueue:
    def __init__(self, ram, num):
        self.ram = ram
        self.num = num
        self.desc_addr = 0
        self.avail_addr = 0
        self.used_addr = 0
        self.last_avail_idx = 0

    def _read32(self, addr):
        return int.from_bytes(self.ram[addr:addr + 4], "big")

    def _write32(self, addr, value):
        self.ram[addr:addr + 4] = (value & 0xffffffff).to_bytes(4, "big")

    def descriptor(self, index):
        base = self.desc_addr + index * DESCRIPTOR_BYTES
        addr = self._read32(base)
        length = self._read32(base + 8)
        flags = self._read32(base + 12)
        nxt = self._read32(base + 16)
        return addr, length, flags, nxt

    def avail_idx(self):
        return self._read32(self.avail_addr + 4)

    def avail_ring(self, slot):
        return self._read32(self.avail_addr + 8 + (slot % self.num) * 4)

    def has_pending(self):
        return self.last_avail_idx != self.avail_idx()

    def next_pending(self):
        return self.avail_ring(self.last_avail_idx % self.num)

    def advance(self):
        self.last_avail_idx = (self.last_avail_idx + 1) & 0xffffffff

    def read_chain(self, head):
        data = bytearray()
        index = head
        while True:
            addr, length, flags, nxt = self.descriptor(index)
            data += bytes(self.ram[addr:addr + length])
            if not flags & FLAG_NEXT:
                break
            index = nxt
        return bytes(data)

    def write_chain(self, head, data):
        written = 0
        index = head
        while written < len(data):
            addr, length, flags, nxt = self.descriptor(index)
            chunk = data[written:written + length]
            self.ram[addr:addr + len(chunk)] = chunk
            written += len(chunk)
            if not flags & FLAG_NEXT or written >= len(data):
                break
            index = nxt
        return written

    def complete(self, head, length):
        used_idx = self._read32(self.used_addr + 4)
        slot = self.used_addr + 8 + (used_idx % self.num) * 8
        self._write32(slot, head)
        self._write32(slot + 4, length)
        self._write32(self.used_addr + 4, (used_idx + 1) & 0xffffffff)


class QueueState:
    def __init__(self, num_max):
        self.num_max = num_max
        self.num = 0
        self.ready = False
        self.desc_addr = 0
        self.avail_addr = 0
        self.used_addr = 0
        self.vq = None


class VirtioMMIODevice:
    MAGIC = 0x74726976
    VERSION = 2
    VENDOR_ID = 1

    ACKNOWLEDGE = 1
    DRIVER = 2
    DRIVER_OK = 4
    FEATURES_OK = 8
    FAILED = 0x80

    def __init__(self, device_id, queue_num_max, config_size=0):
        self.device_id = device_id
        self.config_size = config_size
        self.ram = None
        self.queues = [QueueState(n) for n in queue_num_max]
        self.selected_queue = 0
        self.device_features_sel = 0
        self.driver_features_sel = 0
        self.status = 0
        self.interrupt_status = 0
        self.config_generation = 0

    def attach_ram(self, ram):
        self.ram = ram

    @property
    def queue(self):
        return self.queues[self.selected_queue]

    def read32(self, offset):
        if offset == MAGICVALUE:
            return self.MAGIC
        if offset == VERSION:
            return self.VERSION
        if offset == DEVICEID:
            return self.device_id
        if offset == VENDORID:
            return self.VENDOR_ID
        if offset == DEVICEFEATURES:
            return 0
        if offset == QUEUENUMMAX:
            return self.queue.num_max
        if offset == QUEUEREADY:
            return 1 if self.queue.ready else 0
        if offset == INTERRUPTSTATUS:
            return self.interrupt_status
        if offset == STATUS:
            return self.status
        if offset == CONFIGGENERATION:
            return self.config_generation
        if CONFIG <= offset < CONFIG + self.config_size:
            return self.config_read32(offset - CONFIG)
        return 0

    def write32(self, offset, value):
        if offset == DEVICEFEATURESSEL:
            self.device_features_sel = value
        elif offset == DRIVERFEATURESSEL:
            self.driver_features_sel = value
        elif offset == QUEUESEL:
            self.selected_queue = value
        elif offset == QUEUENUM:
            self.queue.num = value
        elif offset == QUEUEREADY:
            self.queue.ready = bool(value)
            if self.queue.ready:
                self._make_virtqueue(self.queue)
        elif offset == QUEUENOTIFY:
            if self.status & self.DRIVER_OK:
                self.on_notify(value)
        elif offset == INTERRUPTACK:
            self.interrupt_status &= ~value
        elif offset == STATUS:
            self.status = value
            if value == 0:
                self.reset()
        elif offset == QUEUEDESCLOW:
            self.queue.desc_addr = value
        elif offset == QUEUEAVAILLOW:
            self.queue.avail_addr = value
        elif offset == QUEUEUSEDLOW:
            self.queue.used_addr = value
        elif CONFIG <= offset < CONFIG + self.config_size:
            self.config_write32(offset - CONFIG, value)

    def _make_virtqueue(self, q):
        vq = Virtqueue(self.ram, q.num)
        vq.desc_addr = q.desc_addr
        vq.avail_addr = q.avail_addr
        vq.used_addr = q.used_addr
        q.vq = vq

    def reset(self):
        for q in self.queues:
            q.num = 0
            q.ready = False
            q.vq = None
        self.interrupt_status = 0

    def on_notify(self, queue_idx):
        pass

    def config_read32(self, offset):
        return 0

    def config_write32(self, offset, value):
        pass
