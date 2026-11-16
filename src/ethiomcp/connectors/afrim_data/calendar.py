"""Python ports of the afrim-data Rhai translators.

- :func:`geez_numeral` ports ``gez/scripts/numerals.rhai`` (after
  https://www.geez.org/Numerals/).
- :func:`gregorian_to_ethiopian` ports ``am/scripts/datetime/date.rhai``.
  :func:`ethiopian_to_gregorian` is its inverse, which upstream does not have.
"""

from __future__ import annotations

from datetime import date

UNITS = ["", "፩", "፪", "፫", "፬", "፭", "፮", "፯", "፰", "፱"]
TENS = ["", "፲", "፳", "፴", "፵", "፶", "፷", "፸", "፹", "፺"]
GROUPS = ["", "፻", "፼"]
MAX_DIGITS = 13  # the upstream limit

ETHIOPIAN_MONTHS = [
    "መስከረም", "ጥቅምት", "ሕዳር", "ታህሳስ", "ጥር", "የካቲት", "መጋቢት",
    "ሚያዝያ", "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜ",
]  # fmt: skip
GREGORIAN_MONTHS_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]  # fmt: skip
GREGORIAN_MONTHS_AM = [
    "ጃንዋሪ", "ፌብሩዋሪ", "ማርች", "ኤፕሪል", "ሜይ", "ጁን",
    "ጁላይ", "ኦገስት", "ሴፕቴምበር", "ኦክቶበር", "ኖቬምበር", "ዲሴምበር",
]  # fmt: skip
ETHIOPIAN_YEAR_STARTS = [0, 365, 730, 1096]  # day offsets in the 4-year leap cycle
ETHIOPIAN_EPOCH_JDN = 1724221  # JDN of 1 Meskerem 1 (Amete Mihret)


def geez_numeral(number: int) -> str:
    """Write a positive integer with Ge'ez numerals, e.g. 1966 -> ፲፱፻፷፮."""
    if number < 1:
        raise ValueError("Ge'ez numerals have no zero or negative numbers")
    digits = str(number)
    if len(digits) > MAX_DIGITS:
        raise ValueError(f"at most {MAX_DIGITS} digits are supported")
    if len(digits) % 2:
        digits = "0" + digits
    n = len(digits)
    result = ""
    # Walk the digit pairs from the right; i is the index of the pair's units digit.
    for i in range(1, n, 2):
        pos = n - i - 1
        ten, unit = int(digits[pos]), int(digits[pos + 1])
        group = 0 if i < 2 else 2 if (i // 2) % 2 == 0 else 1
        if ten == 0 and unit == 0:
            part = GROUPS[2] if group == 2 else ""
        elif ten == 0:
            # A leading 1 is implicit before ፻ and ፼ (፻ = 100, not ፩፻), except ፩፼.
            implicit = unit == 1 and i > 1 and (pos == 0 or group != 2)
            part = ("" if implicit else UNITS[unit]) + GROUPS[group]
        else:
            part = TENS[ten] + UNITS[unit] + GROUPS[group]
        result = part + result
    return result


def _gregorian_to_jdn(year: int, month: int, day: int) -> int:
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def _jdn_to_ethiopian(jdn: int) -> tuple[int, int, int]:
    r = jdn - ETHIOPIAN_EPOCH_JDN
    n, rem = divmod(r, 1461)
    cycle = 3
    for i in range(3):
        if rem < ETHIOPIAN_YEAR_STARTS[i + 1]:
            cycle = i
            break
    day_in_year = rem - ETHIOPIAN_YEAR_STARTS[cycle]
    return 4 * n + cycle + 1, day_in_year // 30 + 1, day_in_year % 30 + 1


def _ethiopian_to_jdn(year: int, month: int, day: int) -> int:
    n, cycle = divmod(year - 1, 4)
    start = ETHIOPIAN_EPOCH_JDN + 1461 * n + ETHIOPIAN_YEAR_STARTS[cycle]
    return start + 30 * (month - 1) + day - 1


def _jdn_to_gregorian(jdn: int) -> tuple[int, int, int]:
    a = jdn + 32044
    b = (4 * a + 3) // 146097
    c = a - 146097 * b // 4
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + m // 10
    return year, month, day


def parse_date(text: str) -> tuple[int, int, int]:
    """Parse DD/MM/YYYY, DD.MM.YY, DD-MM-YYYY (as upstream) or ISO YYYY-MM-DD.
    Returns (year, month, day). Two-digit years are 20YY, as upstream."""
    text = text.strip()
    for sep in "/.-":
        parts = text.split(sep)
        if len(parts) == 3:
            break
    else:
        raise ValueError(f"cannot parse date {text!r}; use DD/MM/YYYY or YYYY-MM-DD")
    try:
        nums = [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError(f"cannot parse date {text!r}") from exc
    if len(parts[0]) == 4:
        year, month, day = nums
    else:
        day, month, year = nums
    if 0 <= year < 100:
        year += 2000
    return year, month, day


def gregorian_to_ethiopian(year: int, month: int, day: int) -> dict:
    date(year, month, day)  # validates
    ey, em, ed = _jdn_to_ethiopian(_gregorian_to_jdn(year, month, day))
    month_am = ETHIOPIAN_MONTHS[em - 1]
    return {
        "gregorian": {"year": year, "month": month, "day": day},
        "ethiopian": {"year": ey, "month": em, "day": ed, "month_name": month_am},
        "formats": [
            f"{ed} {month_am} {ey}",
            f"{month_am} {ed} ቀን {ey} ዓ.ም.",
            f"{day} {GREGORIAN_MONTHS_EN[month - 1]} {year}",
            f"{GREGORIAN_MONTHS_AM[month - 1]} {day}, {year}",
            f"{year:04d}-{month:02d}-{day:02d}",
        ],
    }


def ethiopian_to_gregorian(year: int, month: int, day: int) -> dict:
    if year < 1 or not 1 <= month <= 13:
        raise ValueError("Ethiopian month must be 1-13 and year >= 1")
    max_day = 30 if month < 13 else (6 if year % 4 == 3 else 5)
    if not 1 <= day <= max_day:
        raise ValueError(f"day must be 1-{max_day} in Ethiopian month {month} of {year}")
    gy, gm, gd = _jdn_to_gregorian(_ethiopian_to_jdn(year, month, day))
    return gregorian_to_ethiopian(gy, gm, gd)
