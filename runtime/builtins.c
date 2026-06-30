typedef unsigned int u32;
typedef int s32;
typedef unsigned long long u64;
typedef long long s64;

// Frame pointer for functions with dynamically sized stack objects.
unsigned __zpu_fp;

static u64 mul32(u32 a, u32 b) {
    u32 al = a & 0xffff, ah = a >> 16;
    u32 bl = b & 0xffff, bh = b >> 16;
    u64 ll = (u64)(al * bl);
    u64 lh = (u64)(al * bh);
    u64 hl = (u64)(ah * bl);
    u64 hh = (u64)(ah * bh);
    return ll + (lh << 16) + (hl << 16) + (hh << 32);
}

u64 __muldi3(u64 a, u64 b) {
    u32 al = (u32)a, ah = (u32)(a >> 32);
    u32 bl = (u32)b, bh = (u32)(b >> 32);
    return mul32(al, bl) + ((u64)(al * bh + ah * bl) << 32);
}

static u64 udivmod(u64 n, u64 d, u64 *rem) {
    u64 q = 0, r = 0;
    for (int i = 0; i < 64; i++) {
        r = (r << 1) | (n >> 63);
        n = n << 1;
        q = q << 1;
        if (r >= d) {
            r = r - d;
            q = q | 1;
        }
    }
    if (rem)
        *rem = r;
    return q;
}

u64 __udivdi3(u64 a, u64 b) { return udivmod(a, b, 0); }

u64 __umoddi3(u64 a, u64 b) {
    u64 r;
    udivmod(a, b, &r);
    return r;
}

s64 __divdi3(s64 a, s64 b) {
    u64 ua = a < 0 ? -(u64)a : (u64)a;
    u64 ub = b < 0 ? -(u64)b : (u64)b;
    u64 q = udivmod(ua, ub, 0);
    return (a < 0) ^ (b < 0) ? -(s64)q : (s64)q;
}

s64 __moddi3(s64 a, s64 b) {
    u64 ua = a < 0 ? -(u64)a : (u64)a;
    u64 ub = b < 0 ? -(u64)b : (u64)b;
    u64 r;
    udivmod(ua, ub, &r);
    return a < 0 ? -(s64)r : (s64)r;
}

u64 __ashldi3(u64 a, int b) {
    u32 lo = (u32)a, hi = (u32)(a >> 32);
    u32 rl, rh;
    if (b == 0)
        return a;
    if (b >= 32) {
        rh = lo << (b - 32);
        rl = 0;
    } else {
        rh = (hi << b) | (lo >> (32 - b));
        rl = lo << b;
    }
    return ((u64)rh << 32) | rl;
}

u64 __lshrdi3(u64 a, int b) {
    u32 lo = (u32)a, hi = (u32)(a >> 32);
    u32 rl, rh;
    if (b == 0)
        return a;
    if (b >= 32) {
        rl = hi >> (b - 32);
        rh = 0;
    } else {
        rl = (lo >> b) | (hi << (32 - b));
        rh = hi >> b;
    }
    return ((u64)rh << 32) | rl;
}

s64 __ashrdi3(s64 a, int b) {
    u32 lo = (u32)a;
    s32 hi = (s32)(a >> 32);
    u32 rl;
    s32 rh;
    if (b == 0)
        return a;
    if (b >= 32) {
        rl = (u32)(hi >> (b - 32));
        rh = hi >> 31;
    } else {
        rl = (lo >> b) | ((u32)hi << (32 - b));
        rh = hi >> b;
    }
    return ((u64)(u32)rh << 32) | rl;
}
