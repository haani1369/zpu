typedef unsigned int u32;
typedef int s32;
typedef unsigned long long u64;
typedef long long s64;

#define SNAN 0x7fc00000u
#define SINF 0x7f800000u

static int sf_isnan(u32 a) { return ((a >> 23) & 0xff) == 0xff && (a & 0x7fffff); }

u32 __addsf3(u32 a, u32 b) {
    u32 aExp = (a >> 23) & 0xff, bExp = (b >> 23) & 0xff;
    u32 aSig = a & 0x7fffff, bSig = b & 0x7fffff;
    if (aExp == 0xff || bExp == 0xff) {
        if (aExp == 0xff && aSig)
            return a | 0x400000;
        if (bExp == 0xff && bSig)
            return b | 0x400000;
        if (aExp == 0xff && bExp == 0xff)
            return ((a ^ b) & 0x80000000) ? SNAN : a;
        return aExp == 0xff ? a : b;
    }
    u32 sa = a >> 31, sb = b >> 31;
    u32 ma = aExp ? (aSig | 0x800000) : 0;
    u32 mb = bExp ? (bSig | 0x800000) : 0;
    s32 ea = aExp ? (s32)aExp : 1, eb = bExp ? (s32)bExp : 1;
    if (ma == 0 && mb == 0)
        return (sa & sb) << 31;
    if (ma == 0)
        return b;
    if (mb == 0)
        return a;
    if (ea < eb || (ea == eb && ma < mb)) {
        u32 t = ma; ma = mb; mb = t;
        s32 te = ea; ea = eb; eb = te;
        t = sa; sa = sb; sb = t;
    }
    s32 diff = ea - eb;
    u64 A = (u64)ma << 3, B = (u64)mb << 3, sticky = 0;
    if (diff > 0) {
        if (diff < 64) {
            sticky = (B & (((u64)1 << diff) - 1)) ? 1 : 0;
            B >>= diff;
        } else {
            sticky = B ? 1 : 0;
            B = 0;
        }
    }
    B |= sticky;
    u64 R;
    s32 exp = ea;
    if (sa == sb) {
        R = A + B;
        if (R & ((u64)1 << 27)) {
            R = (R >> 1) | (R & 1);
            exp++;
        }
    } else {
        R = A - B;
        if (R == 0)
            return 0;
        while (!(R & ((u64)1 << 26))) {
            R <<= 1;
            exp--;
        }
    }
    u32 sig = (u32)(R >> 3) & 0xffffff, rnd = (u32)(R & 7);
    if (rnd > 4 || (rnd == 4 && (sig & 1))) {
        sig++;
        if (sig & 0x1000000) {
            sig >>= 1;
            exp++;
        }
    }
    if (exp >= 0xff)
        return (sa << 31) | SINF;
    if (exp <= 0)
        return sa << 31;
    return (sa << 31) | ((u32)exp << 23) | (sig & 0x7fffff);
}

u32 __subsf3(u32 a, u32 b) { return __addsf3(a, b ^ 0x80000000); }

u32 __mulsf3(u32 a, u32 b) {
    u32 aExp = (a >> 23) & 0xff, bExp = (b >> 23) & 0xff;
    u32 sign = (a ^ b) & 0x80000000;
    u32 aSig = a & 0x7fffff, bSig = b & 0x7fffff;
    if (aExp == 0xff) {
        if (aSig)
            return a | 0x400000;
        return (b & 0x7fffffff) == 0 ? SNAN : sign | SINF;
    }
    if (bExp == 0xff) {
        if (bSig)
            return b | 0x400000;
        return (a & 0x7fffffff) == 0 ? SNAN : sign | SINF;
    }
    if ((a & 0x7fffffff) == 0 || (b & 0x7fffffff) == 0 || aExp == 0 || bExp == 0)
        return sign;
    u32 ma = aSig | 0x800000, mb = bSig | 0x800000;
    s32 exp = (s32)aExp + (s32)bExp - 127;
    u64 prod = (u64)ma * mb;
    u32 shift;
    if (prod & ((u64)1 << 47)) {
        exp++;
        shift = 24;
    } else {
        shift = 23;
    }
    u32 sig = (u32)(prod >> shift) & 0xffffff;
    u32 rem = (u32)(prod & (((u64)1 << shift) - 1)), half = 1u << (shift - 1);
    if (rem > half || (rem == half && (sig & 1))) {
        sig++;
        if (sig & 0x1000000) {
            sig >>= 1;
            exp++;
        }
    }
    if (exp >= 0xff)
        return sign | SINF;
    if (exp <= 0)
        return sign;
    return sign | ((u32)exp << 23) | (sig & 0x7fffff);
}

u32 __divsf3(u32 a, u32 b) {
    u32 aExp = (a >> 23) & 0xff, bExp = (b >> 23) & 0xff;
    u32 sign = (a ^ b) & 0x80000000;
    u32 aSig = a & 0x7fffff, bSig = b & 0x7fffff;
    if (aExp == 0xff) {
        if (aSig)
            return a | 0x400000;
        return bExp == 0xff ? SNAN : sign | SINF;
    }
    if (bExp == 0xff) {
        if (bSig)
            return b | 0x400000;
        return sign;
    }
    if ((b & 0x7fffffff) == 0)
        return (a & 0x7fffffff) == 0 ? SNAN : sign | SINF;
    if ((a & 0x7fffffff) == 0 || aExp == 0)
        return sign;
    if (bExp == 0)
        return sign | SINF;
    u32 ma = aSig | 0x800000, mb = bSig | 0x800000;
    s32 exp = (s32)aExp - (s32)bExp + 127;
    u64 num = (u64)ma << 26;
    u32 q = (u32)(num / mb), r = (u32)(num % mb);
    if (q < (1u << 26)) {
        q <<= 1;
        exp--;
    }
    u32 sig = (q >> 3) & 0xffffff, rnd = q & 7;
    if (r)
        rnd |= 1;
    if (rnd > 4 || (rnd == 4 && (sig & 1))) {
        sig++;
        if (sig & 0x1000000) {
            sig >>= 1;
            exp++;
        }
    }
    if (exp >= 0xff)
        return sign | SINF;
    if (exp <= 0)
        return sign;
    return sign | ((u32)exp << 23) | (sig & 0x7fffff);
}

u32 __floatsisf(s32 i) {
    if (i == 0)
        return 0;
    u32 sign = i < 0 ? 0x80000000 : 0;
    u32 u = i < 0 ? (u32)(-(s64)i) : (u32)i;
    s32 e = 31;
    while (!(u & (1u << e)))
        e--;
    u32 exp = 127 + e, sig;
    if (e <= 23) {
        sig = u << (23 - e);
    } else {
        u32 sh = e - 23, round = u & ((1u << sh) - 1), half = 1u << (sh - 1);
        sig = u >> sh;
        if (round > half || (round == half && (sig & 1))) {
            sig++;
            if (sig & 0x1000000) {
                sig >>= 1;
                exp++;
            }
        }
    }
    return sign | (exp << 23) | (sig & 0x7fffff);
}

u32 __floatunsisf(u32 u) {
    if (u == 0)
        return 0;
    s32 e = 31;
    while (!(u & (1u << e)))
        e--;
    u32 exp = 127 + e, sig;
    if (e <= 23) {
        sig = u << (23 - e);
    } else {
        u32 sh = e - 23, round = u & ((1u << sh) - 1), half = 1u << (sh - 1);
        sig = u >> sh;
        if (round > half || (round == half && (sig & 1))) {
            sig++;
            if (sig & 0x1000000) {
                sig >>= 1;
                exp++;
            }
        }
    }
    return (exp << 23) | (sig & 0x7fffff);
}

s32 __fixsfsi(u32 a) {
    u32 exp = (a >> 23) & 0xff;
    if (exp < 127)
        return 0;
    s32 e = (s32)exp - 127;
    int sign = a >> 31;
    if (e >= 31)
        return sign ? (s32)0x80000000 : 0x7fffffff;
    u32 sig = (a & 0x7fffff) | 0x800000, r;
    r = e >= 23 ? sig << (e - 23) : sig >> (23 - e);
    return sign ? -(s32)r : (s32)r;
}

u32 __fixunssfsi(u32 a) {
    u32 exp = (a >> 23) & 0xff;
    if (exp < 127 || (a >> 31))
        return 0;
    s32 e = (s32)exp - 127;
    if (e >= 32)
        return 0xffffffff;
    u32 sig = (a & 0x7fffff) | 0x800000;
    return e >= 23 ? sig << (e - 23) : sig >> (23 - e);
}

static int sf_cmp(u32 a, u32 b) {
    if (sf_isnan(a) || sf_isnan(b))
        return 3;
    if ((a & 0x7fffffff) == 0 && (b & 0x7fffffff) == 0)
        return 0;
    u32 sa = a >> 31, sb = b >> 31;
    if (sa != sb)
        return sa ? 2 : 1;
    if (a == b)
        return 0;
    if (!sa)
        return a < b ? 2 : 1;
    return a < b ? 1 : 2;
}

s32 __eqsf2(u32 a, u32 b) { return sf_cmp(a, b) == 0 ? 0 : 1; }
s32 __nesf2(u32 a, u32 b) { return sf_cmp(a, b) == 0 ? 0 : 1; }
s32 __unordsf2(u32 a, u32 b) { return sf_cmp(a, b) == 3 ? 1 : 0; }
s32 __ltsf2(u32 a, u32 b) { return sf_cmp(a, b) == 2 ? -1 : sf_cmp(a, b) == 0 ? 0 : 1; }
s32 __lesf2(u32 a, u32 b) {
    int c = sf_cmp(a, b);
    return c == 2 ? -1 : c == 0 ? 0 : 1;
}
s32 __gtsf2(u32 a, u32 b) {
    int c = sf_cmp(a, b);
    return c == 1 ? 1 : c == 0 ? 0 : -1;
}
s32 __gesf2(u32 a, u32 b) {
    int c = sf_cmp(a, b);
    return c == 1 ? 1 : c == 0 ? 0 : -1;
}

#define DINF 0x7ff0000000000000ull
#define DNAN 0x7ff8000000000000ull
#define DIMPL 0x10000000000000ull
#define DMAN 0xfffffffffffffull

static int df_isnan(u64 a) {
    return ((a >> 52) & 0x7ff) == 0x7ff && (a & DMAN);
}

static void mul64(u64 a, u64 b, u64 *hi, u64 *lo) {
    u64 al = a & 0xffffffff, ah = a >> 32, bl = b & 0xffffffff, bh = b >> 32;
    u64 ll = al * bl, lh = al * bh, hl = ah * bl, hh = ah * bh;
    u64 mid = (ll >> 32) + (lh & 0xffffffff) + (hl & 0xffffffff);
    *lo = (ll & 0xffffffff) | (mid << 32);
    *hi = hh + (lh >> 32) + (hl >> 32) + (mid >> 32);
}

u64 __adddf3(u64 a, u64 b) {
    u32 aExp = (a >> 52) & 0x7ff, bExp = (b >> 52) & 0x7ff;
    u64 aSig = a & DMAN, bSig = b & DMAN;
    if (aExp == 0x7ff || bExp == 0x7ff) {
        if (aExp == 0x7ff && aSig)
            return a | 0x8000000000000;
        if (bExp == 0x7ff && bSig)
            return b | 0x8000000000000;
        if (aExp == 0x7ff && bExp == 0x7ff)
            return ((a ^ b) >> 63) ? DNAN : a;
        return aExp == 0x7ff ? a : b;
    }
    u32 sa = a >> 63, sb = b >> 63;
    u64 ma = aExp ? (aSig | DIMPL) : 0, mb = bExp ? (bSig | DIMPL) : 0;
    s32 ea = aExp ? (s32)aExp : 1, eb = bExp ? (s32)bExp : 1;
    if (ma == 0 && mb == 0)
        return (u64)(sa & sb) << 63;
    if (ma == 0)
        return b;
    if (mb == 0)
        return a;
    if (ea < eb || (ea == eb && ma < mb)) {
        u64 t = ma; ma = mb; mb = t;
        s32 te = ea; ea = eb; eb = te;
        u32 ts = sa; sa = sb; sb = ts;
    }
    s32 diff = ea - eb;
    u64 A = ma << 3, B = mb << 3, sticky = 0;
    if (diff > 0) {
        if (diff < 64) {
            sticky = (B & (((u64)1 << diff) - 1)) ? 1 : 0;
            B >>= diff;
        } else {
            sticky = B ? 1 : 0;
            B = 0;
        }
    }
    B |= sticky;
    u64 R;
    s32 exp = ea;
    if (sa == sb) {
        R = A + B;
        if (R & ((u64)1 << 56)) {
            R = (R >> 1) | (R & 1);
            exp++;
        }
    } else {
        R = A - B;
        if (R == 0)
            return 0;
        while (!(R & ((u64)1 << 55))) {
            R <<= 1;
            exp--;
        }
    }
    u64 sig = (R >> 3) & 0x1fffffffffffff;
    u32 rnd = (u32)(R & 7);
    if (rnd > 4 || (rnd == 4 && (sig & 1))) {
        sig++;
        if (sig & 0x20000000000000) {
            sig >>= 1;
            exp++;
        }
    }
    if (exp >= 0x7ff)
        return ((u64)sa << 63) | DINF;
    if (exp <= 0)
        return (u64)sa << 63;
    return ((u64)sa << 63) | ((u64)exp << 52) | (sig & DMAN);
}

u64 __subdf3(u64 a, u64 b) { return __adddf3(a, b ^ 0x8000000000000000ull); }

u64 __muldf3(u64 a, u64 b) {
    u32 aExp = (a >> 52) & 0x7ff, bExp = (b >> 52) & 0x7ff;
    u64 sign = (a ^ b) & 0x8000000000000000ull;
    u64 aSig = a & DMAN, bSig = b & DMAN;
    if (aExp == 0x7ff) {
        if (aSig)
            return a | 0x8000000000000;
        return (b & 0x7fffffffffffffffull) == 0 ? DNAN : sign | DINF;
    }
    if (bExp == 0x7ff) {
        if (bSig)
            return b | 0x8000000000000;
        return (a & 0x7fffffffffffffffull) == 0 ? DNAN : sign | DINF;
    }
    if ((a & 0x7fffffffffffffffull) == 0 || (b & 0x7fffffffffffffffull) == 0 ||
        aExp == 0 || bExp == 0)
        return sign;
    u64 ma = aSig | DIMPL, mb = bSig | DIMPL;
    s32 exp = (s32)aExp + (s32)bExp - 1023;
    u64 hi, lo;
    mul64(ma, mb, &hi, &lo);
    u32 shift;
    if (hi & ((u64)1 << 41)) {
        exp++;
        shift = 53;
    } else {
        shift = 52;
    }
    u64 sig = (hi << (64 - shift)) | (lo >> shift);
    u64 g = lo & (((u64)1 << shift) - 1), half = (u64)1 << (shift - 1);
    if (g > half || (g == half && (sig & 1))) {
        sig++;
        if (sig & 0x20000000000000) {
            sig >>= 1;
            exp++;
        }
    }
    if (exp >= 0x7ff)
        return sign | DINF;
    if (exp <= 0)
        return sign;
    return sign | ((u64)exp << 52) | (sig & DMAN);
}

u64 __divdf3(u64 a, u64 b) {
    u32 aExp = (a >> 52) & 0x7ff, bExp = (b >> 52) & 0x7ff;
    u64 sign = (a ^ b) & 0x8000000000000000ull;
    u64 aSig = a & DMAN, bSig = b & DMAN;
    if (aExp == 0x7ff) {
        if (aSig)
            return a | 0x8000000000000;
        return bExp == 0x7ff ? DNAN : sign | DINF;
    }
    if (bExp == 0x7ff) {
        if (bSig)
            return b | 0x8000000000000;
        return sign;
    }
    if ((b & 0x7fffffffffffffffull) == 0)
        return (a & 0x7fffffffffffffffull) == 0 ? DNAN : sign | DINF;
    if ((a & 0x7fffffffffffffffull) == 0 || aExp == 0)
        return sign;
    if (bExp == 0)
        return sign | DINF;
    u64 ma = aSig | DIMPL, mb = bSig | DIMPL;
    s32 exp = (s32)aExp - (s32)bExp + 1023;
    if (ma < mb) {
        ma <<= 1;
        exp--;
    }
    u64 q = 1, rem = ma - mb;
    for (int i = 0; i < 55; i++) {
        q <<= 1;
        rem <<= 1;
        if (rem >= mb) {
            rem -= mb;
            q |= 1;
        }
    }
    u64 sig = q >> 3;
    u32 rnd = (u32)(q & 7);
    if (rem)
        rnd |= 1;
    if (rnd > 4 || (rnd == 4 && (sig & 1))) {
        sig++;
        if (sig & 0x20000000000000) {
            sig >>= 1;
            exp++;
        }
    }
    if (exp >= 0x7ff)
        return sign | DINF;
    if (exp <= 0)
        return sign;
    return sign | ((u64)exp << 52) | (sig & DMAN);
}

u64 __extendsfdf2(u32 a) {
    u32 aExp = (a >> 23) & 0xff, aSig = a & 0x7fffff;
    u64 sign = (u64)(a >> 31) << 63;
    if (aExp == 0xff)
        return sign | DINF | ((u64)aSig << 29);
    if (aExp == 0 && aSig == 0)
        return sign;
    if (aExp == 0)
        return sign; /* flush denormal */
    return sign | ((u64)(aExp - 127 + 1023) << 52) | ((u64)aSig << 29);
}

u32 __truncdfsf2(u64 a) {
    u32 aExp = (a >> 52) & 0x7ff;
    u64 aSig = a & DMAN;
    u32 sign = (u32)(a >> 63) << 31;
    if (aExp == 0x7ff)
        return sign | SINF | (aSig ? 0x400000 : 0) | (u32)(aSig >> 29);
    if ((a & 0x7fffffffffffffffull) == 0)
        return sign;
    s32 exp = (s32)aExp - 1023 + 127;
    u64 m = aSig | DIMPL; /* 53-bit */
    u32 sig = (u32)(m >> 29) & 0xffffff;
    u64 g = m & 0x1fffffff, half = 0x10000000;
    if (g > half || (g == half && (sig & 1))) {
        sig++;
        if (sig & 0x1000000) {
            sig >>= 1;
            exp++;
        }
    }
    if (exp >= 0xff)
        return sign | SINF;
    if (exp <= 0)
        return sign;
    return sign | ((u32)exp << 23) | (sig & 0x7fffff);
}

u64 __floatsidf(s32 i) {
    if (i == 0)
        return 0;
    u64 sign = i < 0 ? 0x8000000000000000ull : 0;
    u32 u = i < 0 ? (u32)(-(s64)i) : (u32)i;
    s32 e = 31;
    while (!(u & (1u << e)))
        e--;
    u64 sig = (u64)u << (52 - e);
    return sign | ((u64)(1023 + e) << 52) | (sig & DMAN);
}

u64 __floatunsidf(u32 u) {
    if (u == 0)
        return 0;
    s32 e = 31;
    while (!(u & (1u << e)))
        e--;
    u64 sig = (u64)u << (52 - e);
    return ((u64)(1023 + e) << 52) | (sig & DMAN);
}

s32 __fixdfsi(u64 a) {
    u32 exp = (a >> 52) & 0x7ff;
    if (exp < 1023)
        return 0;
    s32 e = (s32)exp - 1023;
    int sign = a >> 63;
    if (e >= 31)
        return sign ? (s32)0x80000000 : 0x7fffffff;
    u64 sig = (a & DMAN) | DIMPL;
    u32 r = (u32)(e >= 52 ? sig << (e - 52) : sig >> (52 - e));
    return sign ? -(s32)r : (s32)r;
}

static int df_cmp(u64 a, u64 b) {
    if (df_isnan(a) || df_isnan(b))
        return 3;
    if ((a & 0x7fffffffffffffffull) == 0 && (b & 0x7fffffffffffffffull) == 0)
        return 0;
    u32 sa = a >> 63, sb = b >> 63;
    if (sa != sb)
        return sa ? 2 : 1;
    if (a == b)
        return 0;
    if (!sa)
        return a < b ? 2 : 1;
    return a < b ? 1 : 2;
}

s32 __eqdf2(u64 a, u64 b) { return df_cmp(a, b) == 0 ? 0 : 1; }
s32 __nedf2(u64 a, u64 b) { return df_cmp(a, b) == 0 ? 0 : 1; }
s32 __unorddf2(u64 a, u64 b) { return df_cmp(a, b) == 3 ? 1 : 0; }
s32 __ltdf2(u64 a, u64 b) {
    int c = df_cmp(a, b);
    return c == 2 ? -1 : c == 0 ? 0 : 1;
}
s32 __ledf2(u64 a, u64 b) {
    int c = df_cmp(a, b);
    return c == 2 ? -1 : c == 0 ? 0 : 1;
}
s32 __gtdf2(u64 a, u64 b) {
    int c = df_cmp(a, b);
    return c == 1 ? 1 : c == 0 ? 0 : -1;
}
s32 __gedf2(u64 a, u64 b) {
    int c = df_cmp(a, b);
    return c == 1 ? 1 : c == 0 ? 0 : -1;
}
