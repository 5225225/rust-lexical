'''
    div128
    ======

    Generate the constants for 128-bit division.
    Note that this doesn't work for **all** values.

    For unsigned values, the `precision` is the number
    of bits of the type size, and we only guarantee that
    m fits in `max(prec, bits − div_bits) + 1`, or
    guarantee it fits in 129 bits. Most values fit a bit
    smaller, however, we have to fall back to a slower
    division algorithm in these cases.
'''

import math

u64_max = 2**64 - 1
u128_max = 2**128-1

def is_valid(x):
    '''Determine if the power is valid.'''
    return (
        x <= u64_max
        and (u128_max / (x**2)) < x
    )

def find_power(radix):
    '''Find the power of the divisor.'''

    start_power = int(math.floor(math.log(u64_max, radix))) - 1
    while is_valid(radix**start_power):
        start_power += 1
    return start_power - 1

def choose_multiplier(divisor, bits, is_signed=False):
    '''
    Choose multiplier algorithm from:
        https://gmplib.org/~tege/divcnst-pldi94.pdf
    '''

    # Precision is the number of bits of precision we need,
    # which for signed values, even in 1's/2's complement, is
    # 1 less than the bits.
    precision = bits
    if is_signed:
        precision -= 1

    div_bits = math.ceil(math.log2(divisor))
    sh_post = div_bits
    m_low = 2**(bits+div_bits) // divisor
    m_high = (2**(bits+div_bits) + 2**(bits + div_bits - precision)) // divisor

    while m_low // 2 < m_high // 2 and sh_post > 0:
        m_low //= 2
        m_high //= 2
        sh_post -= 1

    return (m_high, sh_post, div_bits)

def fast_shift(divisor):
    '''
    Check if we can do a fast shift for quick division as a smaller type.
    This only holds if the divisor is not rounded while shifting.
    '''

    n = 0
    while divisor % 2**(n + 1) == 0:
        n += 1
    return n

def is_pow2(radix):
    '''Determine if the value is an exact power-of-two.'''
    return radix == 2**int(math.log2(radix))

def print_pow2(radix):
    '''Print the function for a power-of-two.'''

    log2 = int(math.log2(radix))
    digits = 64 // log2
    shr = digits * log2
    mask = (1 << shr) - 1

    print('#[inline]')
    print(f'fn u128_divrem_{radix}(n: u128) -> (u128, u64) {{')
    print(f'    pow2_u128_divrem(n, {mask}, {shr})')
    print('}')
    print('')

    print('#[inline]')
    print(f'fn u64_step_{radix}() -> usize {{')
    print(f'    {digits}')
    print('}')
    print('')

def print_fast(radix, divisor, fast_shr, factor, factor_shr, digits):
    '''Print the fastest division algorithm.'''

    fast = 1 << (64 + fast_shr)
    print('#[inline]')
    print(f'fn u128_divrem_{radix}(n: u128) -> (u128, u64) {{')
    print(f'    fast_u128_divrem(n, {divisor}, {fast}, {fast_shr}, {factor}, {factor_shr})')
    print('}')
    print('')

    print('#[inline]')
    print(f'fn u64_step_{radix}() -> usize {{')
    print(f'    {digits}')
    print('}')
    print('')

def print_moderate(radix, divisor, factor, factor_shr, digits):
    '''Print the moderate division algorithm.'''

    print('#[inline]')
    print(f'fn u128_divrem_{radix}(n: u128) -> (u128, u64) {{')
    print(f'    moderate_u128_divrem(n, {divisor}, {factor}, {factor_shr})')
    print('}')
    print('')

    print('#[inline]')
    print(f'fn u64_step_{radix}() -> usize {{')
    print(f'    {digits}')
    print('}')
    print('')

def print_slow(radix, divisor, digits):
    '''Print the function for the slow division.'''

    ctlz = 66 - len(bin(divisor))
    print('#[inline]')
    print(f'fn u128_divrem_{radix}(n: u128) -> (u128, u64) {{')
    print(f'    slow_u128_divrem(n, {divisor}, {ctlz})')
    print('}')
    print('')

    print('#[inline]')
    print(f'fn u64_step_{radix}() -> usize {{')
    print(f'    {digits}')
    print('}')
    print('')

def divisor_constants():
    '''Generate all the divisor constants for all radices.'''

    for radix in range(2, 37):
        # Handle powers-of-two.
        if is_pow2(radix):
            print_pow2(radix)
            continue

        # Not a power of two, must be slower.
        digits = find_power(radix)
        divisor = radix**digits
        fast_shr = fast_shift(divisor)
        factor, factor_shr, _ = choose_multiplier(divisor, 128)

        if factor >= 2**128:
            # Cannot fit in a u128, must revert to the slow algorithm.
            print_slow(radix, divisor, digits)
        elif fast_shr != 0:
            print_fast(radix, divisor, fast_shr, factor, factor_shr, digits)
        else:
            print_moderate(radix, divisor, factor, factor_shr, digits)

# PYTHON LOGIC
# This is the approach, in Python, for how to do this.

def u128_mulhi(x, y):
    '''Multiply 2 128-bit integers, and get the high 128 bits.'''

    lo_mask = (1<<64) - 1
    x_lo = x & lo_mask
    x_hi = x >> 64
    y_lo = y & lo_mask
    y_hi = y >> 64

    carry = (x_lo * y_lo) >> 64
    m = x_lo * y_hi + carry
    high1 = m >> 64

    m_lo = m & lo_mask
    high2 = (x_hi * y_lo + m_lo) >> 64

    return x_hi * y_hi + high1 + high2

def udiv128(n, divisor=10**19):
    '''Do an exact division using pre-computed values.'''

    factor, factor_shr, _ = choose_multiplier(divisor, 128)
    shr = fast_shift(divisor)
    if n < (1<<(64 + shr)):
        quotient = (n >> shr) // (divisor >> shr)
    else:
        quotient = u128_mulhi(n, factor) >> factor_shr
    remainder = (n - quotient * divisor)
    return (quotient, remainder)

if __name__ == '__main__':
    divisor_constants()
