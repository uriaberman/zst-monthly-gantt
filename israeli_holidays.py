# -*- coding: utf-8 -*-
"""
Israeli holidays + national days for any date range.

Combines:
  - Religious holidays (via pyluach): חגי תורה + ימי תענית
  - Israeli civil/national days (manual): שואה, זיכרון, עצמאות, ירושלים, האם/המשפחה
  - ימים שאינם חגים אבל משמעותיים: ל"ג בעומר, ט"ו באב, ט"ו בשבט, ראש חודש (אופציונלי)

Returns dict {iso_date: holiday_name} for the requested range.
"""
from datetime import date, timedelta
from pyluach.dates import HebrewDate, GregorianDate


# Israeli civil holidays - tied to Hebrew dates
# (Hebrew month, Hebrew day, name)
ISRAELI_CIVIL = [
    (1, 27, "יום השואה"),
    (2, 4, "יום הזיכרון"),
    (2, 5, "יום העצמאות"),
    (2, 28, "יום ירושלים"),
    (11, 30, "יום המשפחה"),  # ל' שבט
]

# Significant days to also flag (in pyluach but worth flagging)
SIGNIFICANT_FROM_PYLUACH = {
    "פסח שני",
    "ל״ג בעומר",
    "ט״ו באב",
    "ט״ו בשבט",
    "ראש השנה",
    "יום כיפור",
    "סוכות",
    "שמיני עצרת",
    "חנוכה",
    "פורים",
    "שושן פורים",
    "פסח",
    "שבועות",
    "ט׳ באב",
    "י״ז בתמוז",
    "צום גדליה",
    "י׳ בטבת",
    "תענית אסתר",
}


def get_israeli_holidays(start_iso: str, end_iso: str, include_fasts: bool = True,
                         include_rosh_chodesh: bool = False) -> dict[str, str]:
    """Return {iso_date: holiday_name_hebrew} for the inclusive range.

    Args:
      start_iso / end_iso: 'YYYY-MM-DD'
      include_fasts: include fast days (i"z be-tammuz, etc.)
      include_rosh_chodesh: include monthly ראש חודש markers (off by default - too many)
    """
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)

    holidays = {}

    # 1) pyluach festivals + fasts
    cur = start
    while cur <= end:
        hd = GregorianDate(cur.year, cur.month, cur.day).to_heb()
        # Get holiday with prefix_day=False to avoid "first day of"
        name = hd.holiday(hebrew=True, israel=True, prefix_day=False)
        if name and name != 'None':
            if name in SIGNIFICANT_FROM_PYLUACH:
                if not include_fasts and name in ("ט׳ באב", "י״ז בתמוז", "צום גדליה", "י׳ בטבת", "תענית אסתר"):
                    pass
                else:
                    holidays[cur.isoformat()] = name
        # Rosh Chodesh (1st or 30th of Hebrew month)
        if include_rosh_chodesh and hd.day in (1, 30):
            heb_month_name = hd.month_name(hebrew=True)
            holidays.setdefault(cur.isoformat(), f"ראש חודש {heb_month_name}")
        cur += timedelta(days=1)

    # 2) Israeli civil holidays (manual mapping)
    for year in range(start.year, end.year + 2):
        # Need to figure out matching Hebrew year - approximate
        # Hebrew year roughly = Gregorian year + 3760 (varies)
        for heb_year_offset in [3760, 3761]:
            heb_year = year + heb_year_offset
            for heb_month, heb_day, name in ISRAELI_CIVIL:
                try:
                    hd = HebrewDate(heb_year, heb_month, heb_day)
                    gd = hd.to_pydate()
                    if start <= gd <= end:
                        holidays[gd.isoformat()] = name
                except Exception:
                    continue

    return holidays


def hebrew_month_for_gregorian(year: int, month: int) -> str:
    """Return the Hebrew month name for the START of the Gregorian month."""
    gd = GregorianDate(year, month, 1)
    hd = gd.to_heb()
    return hd.month_name(hebrew=True)


def hebrew_year_for_gregorian(year: int, month: int) -> str:
    """Return Hebrew year string like 'תשפ״ו' for the start of the Gregorian month."""
    gd = GregorianDate(year, month, 1)
    hd = gd.to_heb()
    return hd.hebrew_date_string().split()[-1]  # last token = year


if __name__ == '__main__':
    # Self-test: print all Israeli holidays in 2026
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    hols = get_israeli_holidays('2026-01-01', '2026-12-31')
    print(f"Israeli holidays in 2026: {len(hols)}")
    for iso in sorted(hols.keys()):
        print(f"  {iso}: {hols[iso]}")

    print()
    print(f"יוני 2026 = {hebrew_month_for_gregorian(2026, 6)} {hebrew_year_for_gregorian(2026, 6)}")
