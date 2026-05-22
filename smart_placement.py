# -*- coding: utf-8 -*-
"""
Smart Placement Wizard.

Takes a data.json with items missing dates → proposes a chronological layout
based on:
  - Period (parse Hebrew "יוני 2026" or "20.5-30.6.2026")
  - Day-of-week preferences per content type
  - Avoidance of Fridays/Saturdays and known Israeli holidays
  - Even distribution across available days

Outputs:
  - Markdown table to stdout (for user review)
  - Updated data.json in place (date_iso + day filled)
"""
import sys, io, json, re, argparse
from datetime import date, timedelta
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pyluach.dates import GregorianDate


HEB_MONTHS = {
    'ינואר': 1, 'פברואר': 2, 'מרץ': 3, 'מארס': 3, 'אפריל': 4,
    'מאי': 5, 'יוני': 6, 'יולי': 7, 'אוגוסט': 8, 'ספטמבר': 9,
    'אוקטובר': 10, 'נובמבר': 11, 'דצמבר': 12,
}

# Keywords that hint a content item is related to a specific holiday.
# When placing an item with a matching keyword, prefer dates near the holiday.
HOLIDAY_KEYWORDS = {
    'יום השואה':   ['שואה', 'הנצחה', 'גטו', 'אנטישמיות', 'ניצולי'],
    'יום הזיכרון': ['זיכרון', 'חללים', 'נופלים', 'משפחות שכולות'],
    'יום העצמאות': ['עצמאות', 'מדינה', 'דגל', 'תקומה', '78', '77', 'יום העצמאות'],
    'יום ירושלים': ['ירושלים', 'מאוחדת', 'כותל', 'עיר הקודש'],
    'יום המשפחה':  ['יום המשפחה', 'יום האם', 'אמהות', 'יום האב', 'אבהות'],
    'פסח':         ['פסח', 'סדר', 'הגדה', 'יציאת מצרים', 'מצה'],
    'שבועות':      ['שבועות', 'מתן תורה', 'ביכורים', 'הר סיני'],
    'ראש השנה':    ['ראש השנה', 'שנה טובה', 'שופר', 'דבש', 'תפוח'],
    'יום כיפור':   ['יום כיפור', 'כיפורים', 'תשובה', 'סליחה'],
    'סוכות':       ['סוכות', 'סוכה', 'ארבעת המינים', 'לולב', 'אתרוג'],
    'שמיני עצרת':  ['שמחת תורה', 'שמיני עצרת', 'הקפות'],
    'חנוכה':       ['חנוכה', 'חנוכייה', 'סופגנייה', 'לביבה', 'מכבים'],
    'פורים':       ['פורים', 'מגילה', 'מסיכה', 'תחפושת', 'משלוח מנות'],
    'ט״ו בשבט':    ['ט"ו בשבט', 'ראש השנה לאילנות', 'נטיעה', 'עץ'],
    'ל״ג בעומר':   ['ל"ג בעומר', 'מדורה', 'בר יוחאי'],
    'ט׳ באב':      ['תשעה באב', 'חורבן', 'בית המקדש'],
}

HEB_DOW = ['ב', 'ג', 'ד', 'ה', 'ו', 'ש', 'א']  # Mon=0..Sun=6 → Hebrew letters
HEB_DOW_NAMES = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון']


# Known Israeli holidays/anchors (rough - extend per year)
HOLIDAYS = {
    '2026-05-22': 'ערב שבועות',
    '2026-05-23': 'חג שבועות',
    '2026-06-21': 'יום אבא',
    # Avoiding placing content on these by default
}

# Day-of-week placement preferences per content type (Mon..Sun = 0..6)
# Higher score = more preferred. Friday (4) and Saturday (5) = banned.
DOW_SCORES = {
    'post':     {0: 9, 1: 8, 2: 9, 3: 9, 6: 8, 4: 1, 5: 0},  # Mon/Wed/Thu best
    'carousel': {0: 7, 1: 9, 2: 10, 3: 9, 6: 7, 4: 1, 5: 0}, # Tue/Wed best
    'reel':     {0: 10, 1: 8, 2: 9, 3: 10, 6: 9, 4: 1, 5: 0},# Mon/Thu best
    'story':    {0: 9, 1: 8, 2: 8, 3: 9, 6: 8, 4: 1, 5: 0},  # any weekday
}


def parse_period(period: str) -> tuple[date, date]:
    """Parse 'יוני 2026' or '20.5-30.6.2026' or '20.5-30.6' (current year) → (start, end)."""
    period = period.strip()

    # Try Hebrew "MONTH YEAR" form
    m = re.match(r'^(\S+)\s+(\d{4})$', period)
    if m and m.group(1) in HEB_MONTHS:
        month = HEB_MONTHS[m.group(1)]
        year = int(m.group(2))
        start = date(year, month, 1)
        # Last day of month
        if month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        return start, end

    # Try "DD.M-DD.M.YYYY" form
    m = re.match(r'^(\d{1,2})\.(\d{1,2})\s*[-–]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})$', period)
    if m:
        d1, m1, d2, m2, y = m.groups()
        return date(int(y), int(m1), int(d1)), date(int(y), int(m2), int(d2))

    # Try "DD.M.YYYY - DD.M.YYYY" form
    m = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})\s*[-–]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})$', period)
    if m:
        d1, m1, y1, d2, m2, y2 = m.groups()
        return date(int(y1), int(m1), int(d1)), date(int(y2), int(m2), int(d2))

    raise ValueError(f"Cannot parse period: '{period}'. Use 'יוני 2026' or '20.5-30.6.2026'")


def eligible_days(start: date, end: date) -> list[date]:
    """All days in range that are NOT Fri/Sat and NOT holidays."""
    out = []
    cur = start
    while cur <= end:
        wd = cur.weekday()  # Mon=0..Sun=6
        iso = cur.isoformat()
        if wd not in (4, 5) and iso not in HOLIDAYS:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def score_day(d: date, type_key: str) -> int:
    """Score how suitable a day is for a given content type."""
    return DOW_SCORES.get(type_key, DOW_SCORES['post']).get(d.weekday(), 5)


def detect_holiday_anchor(item: dict, holidays_in_period: dict[str, str]) -> str | None:
    """If the item's title/explanation/pillar mentions a holiday that exists in the period,
    return the ISO date of that holiday for anchoring."""
    text = ' '.join(filter(None, [
        item.get('title', ''),
        item.get('pillar', ''),
        item.get('explanation', ''),
        item.get('short_explanation', ''),
    ])).lower()
    if not text:
        return None

    # Build inverse map: keyword → holiday_name
    for holiday_name, keywords in HOLIDAY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                # Find this holiday in the period
                for iso, name in holidays_in_period.items():
                    if holiday_name in name or name in holiday_name:
                        return iso
                break
    return None


def propose_placement(items: list[dict], start: date, end: date,
                      holidays_in_period: dict[str, str] | None = None) -> list[dict]:
    """Assign date_iso + day to items missing them. Returns mutated items.

    If holidays_in_period is provided, items mentioning a holiday in the period
    will be anchored near that holiday (within 3 days before/after)."""
    pending = [it for it in items if not it.get('date_iso')]
    if not pending:
        return items

    holidays_in_period = holidays_in_period or {}
    eligible = eligible_days(start, end)
    if len(eligible) < len(pending):
        print(f"⚠ Only {len(eligible)} eligible days for {len(pending)} items - some will share days")

    pending.sort(key=lambda x: x['num'])
    used_days = set(it['date_iso'] for it in items if it.get('date_iso'))
    n = len(pending)

    # Step 1: Anchor items with holiday keywords FIRST
    anchored = {}
    leftover = []
    for item in pending:
        anchor_iso = detect_holiday_anchor(item, holidays_in_period)
        if anchor_iso:
            anchored[item['num']] = (item, anchor_iso)
        else:
            leftover.append(item)

    # Place anchored items - find best eligible day within ±3 of the anchor (before the holiday preferred)
    for num, (item, anchor_iso) in anchored.items():
        anchor_date = date.fromisoformat(anchor_iso)
        candidates = []
        # Prefer day BEFORE the holiday (so content publishes prior to the event)
        for offset in [-2, -1, -3, 1, 2, 0]:
            target = anchor_date + timedelta(days=offset)
            if not (start <= target <= end):
                continue
            if target.weekday() in (4, 5):  # skip Fri/Sat
                continue
            if target.isoformat() in used_days:
                continue
            if target.isoformat() in holidays_in_period and offset == 0:
                continue  # don't place ON the holiday itself
            score = score_day(target, item.get('type_key', 'post'))
            candidates.append((score, target))
        if candidates:
            candidates.sort(key=lambda x: -x[0])
            chosen = candidates[0][1]
            used_days.add(chosen.isoformat())
            _assign_date(item, chosen)
        else:
            leftover.append(item)

    # Step 2: Distribute leftover items evenly across remaining eligible days
    remaining_eligible = [d for d in eligible if d.isoformat() not in used_days]
    if remaining_eligible and leftover:
        m = len(leftover)
        for i, item in enumerate(leftover):
            target_idx = int((i + 0.5) / m * len(remaining_eligible))
            target_idx = min(target_idx, len(remaining_eligible) - 1)
            candidates = []
            for offset in range(-3, 4):
                j = target_idx + offset
                if 0 <= j < len(remaining_eligible):
                    d = remaining_eligible[j]
                    if d.isoformat() in used_days:
                        continue
                    score = score_day(d, item.get('type_key', 'post'))
                    distance_penalty = abs(offset)
                    candidates.append((score - distance_penalty, d))
            if not candidates:
                for d in remaining_eligible:
                    if d.isoformat() not in used_days:
                        candidates.append((0, d))
                        break
            if not candidates:
                candidates = [(0, eligible[0])]
            candidates.sort(key=lambda x: -x[0])
            chosen = candidates[0][1]
            used_days.add(chosen.isoformat())
            _assign_date(item, chosen)

    return items


def _assign_date(item: dict, chosen_day: date) -> None:
    wd = chosen_day.weekday()
    day_letter = HEB_DOW[wd]
    item['date'] = f"{chosen_day.day}.{chosen_day.month}.{chosen_day.year % 100:02d}"
    item['date_iso'] = chosen_day.isoformat()
    item['day'] = day_letter + "'"


def render_markdown_table(items: list[dict]) -> str:
    out = []
    out.append("| # | תאריך | יום | סוג | כותרת |")
    out.append("|---|---|---|---|---|")
    for it in sorted(items, key=lambda x: x.get('date_iso','9')):
        date_str = it.get('date_iso', '???')
        day = it.get('day', '?')
        type_label = it.get('type_label', it.get('type_key', '?'))
        title = (it.get('title', '') or '')[:60]
        out.append(f"| {it['num']} | {date_str} | {day} | {type_label} | {title} |")
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description='Propose dates for items missing them')
    ap.add_argument('data', help='Path to data.json (will be updated in place)')
    ap.add_argument('--period', help='Override period from data.json (e.g. "יוני 2026")')
    args = ap.parse_args()

    data = json.loads(Path(args.data).read_text(encoding='utf-8'))
    period = args.period or data.get('period', '')

    start, end = parse_period(period)
    print(f"Period: {start} → {end}")

    items = data['items']
    n_missing = sum(1 for it in items if not it.get('date_iso'))
    print(f"Items needing placement: {n_missing} / {len(items)}")

    # Pull Israeli holidays in the period - used for context-aware anchoring
    try:
        from israeli_holidays import get_israeli_holidays
        from datetime import timedelta
        ext_start = (start - timedelta(days=3)).isoformat()
        ext_end = (end + timedelta(days=3)).isoformat()
        holidays_in_period = get_israeli_holidays(ext_start, ext_end)
        print(f"Holidays in period: {len(holidays_in_period)}")
    except Exception as e:
        holidays_in_period = {}
        print(f"⚠ Could not load holidays: {e}")

    propose_placement(items, start, end, holidays_in_period)

    data['needs_placement'] = sum(1 for it in items if not it.get('date_iso'))
    Path(args.data).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    print()
    print("Proposed placement:")
    print()
    print(render_markdown_table(items))
    print()
    print(f"Updated: {args.data}")
    print("If the placement looks good, run build.py. Otherwise edit data.json manually.")


if __name__ == '__main__':
    main()
