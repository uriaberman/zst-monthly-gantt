# -*- coding: utf-8 -*-
"""
Build: data.json -> index.html (Seliger Shomron branded monthly Gantt viewer).

RTL landscape, side-by-side May/June calendars, content pillars color-coded,
cell-click modal with full content (2 visuals / 2 copy / 2 captions).
"""
import sys, io, json, html, argparse, base64, calendar
from datetime import date, timedelta
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pyluach.dates import GregorianDate

# ---------- Pillar / status palette ----------

PILLAR_COLORS = {
    'numbers':   {'bg': '#DBEAFE', 'edge': '#1E40AF', 'label': 'מאחורי המספרים'},
    'question':  {'bg': '#EDE9FE', 'edge': '#6D28D9', 'label': 'השאלה השבועית'},
    'reel':      {'bg': '#FCE7F3', 'edge': '#BE185D', 'label': 'רילס'},
    'voices':    {'bg': '#D1FAE5', 'edge': '#047857', 'label': 'קולות מהשטח'},
    'anchor':    {'bg': '#FEF3C7', 'edge': '#B45309', 'label': 'עוגן / חג'},
    'advocacy':  {'bg': '#FECACA', 'edge': '#B91C1C', 'label': 'אדווקסי'},
    'community': {'bg': '#CFFAFE', 'edge': '#0E7490', 'label': 'אנחנו כאן'},
    'other':     {'bg': '#F3F4F6', 'edge': '#374151', 'label': 'אחר'},
}

STATUS_COLORS = {
    'בעבודה':       '#9CA3AF',
    'בעיצוב':       '#3B82F6',
    'ממתין לאישור': '#F59E0B',
    'אושר':          '#10B981',
}

HEB_WEEKDAYS = ['ראשון','שני','שלישי','רביעי','חמישי','שישי','שבת']

# Hebrew month names (Gregorian)
HEB_GREG_MONTHS = ['','ינואר','פברואר','מרץ','אפריל','מאי','יוני',
                   'יולי','אוגוסט','ספטמבר','אוקטובר','נובמבר','דצמבר']

# Known holidays for May-June 2026 (manual since pyluach API for festivals)
HOLIDAYS_2026 = {
    '2026-05-22': 'ערב שבועות',
    '2026-05-23': 'חג שבועות',
    '2026-06-16': 'ראש חודש תמוז',
    '2026-06-21': 'יום אבא',
}


def heb_date(d: date) -> tuple[str, str]:
    """Return (day-only-letters, full-string) e.g. ('כ"ה', 'כ"ה אייר תשפ"ו')."""
    gd = GregorianDate(d.year, d.month, d.day)
    hd = gd.to_heb()
    full = hd.hebrew_date_string()
    parts = full.split()
    return parts[0], full


def build_month_grid(year: int, month: int, items_by_date: dict) -> list:
    """
    Return list of weeks, each week = list of 7 cells.
    Cells outside the month are marked is_outside=True.
    Order in week is Sunday->Saturday (Israeli/Hebrew week start).
    """
    cal = calendar.Calendar(firstweekday=6)  # 6 = Sunday
    weeks = []
    for week_dates in cal.monthdatescalendar(year, month):
        # monthdatescalendar with firstweekday=6 gives Sun..Sat
        row = []
        for d in week_dates:
            heb_short, heb_full = heb_date(d)
            iso = d.isoformat()
            cell = {
                'iso': iso,
                'day_num': d.day,
                'weekday': d.weekday(),
                'heb_short': heb_short,
                'heb_full': heb_full,
                'is_outside': d.month != month,
                'is_friday': d.weekday() == 4,
                'is_saturday': d.weekday() == 5,
                'holiday': HOLIDAYS_2026.get(iso, ''),
                'items': items_by_date.get(iso, []),
            }
            row.append(cell)
        weeks.append(row)
    return weeks


def render_cell(cell: dict) -> str:
    classes = ['cell']
    if cell['is_outside']:
        classes.append('outside')
        # Don't render items/holiday tag in outside cells (avoids DOM duplicates across months)
        cell = {**cell, 'items': [], 'holiday': ''}
    if cell['is_friday']:
        classes.append('friday')
    if cell['is_saturday']:
        classes.append('saturday')
    if cell['holiday']:
        classes.append('holiday')
    if cell['items']:
        classes.append('has-content')
        # pillar of first item drives background
        primary = cell['items'][0]
        pcolor = PILLAR_COLORS.get(primary['pillar_key'], PILLAR_COLORS['other'])
        bg = pcolor['bg']
    else:
        bg = ''

    style = f'background:{bg};' if bg else ''

    # header: gregorian (large) + hebrew (small) + holiday tag
    header_parts = [
        f'<div class="num">{cell["day_num"]}</div>',
        f'<div class="heb">{html.escape(cell["heb_short"])}</div>',
    ]
    if cell['holiday']:
        header_parts.append(f'<div class="hol">{html.escape(cell["holiday"])}</div>')

    # items
    body_parts = []
    for it in cell['items']:
        pcolor = PILLAR_COLORS.get(it['pillar_key'], PILLAR_COLORS['other'])
        status_color = STATUS_COLORS.get(it['status'], '#9CA3AF')
        title = html.escape(it['title'])
        pillar_label = html.escape(pcolor['label'])
        body_parts.append(f'''
        <div class="item" data-num="{it['num']}" style="border-right:4px solid {pcolor['edge']};">
          <div class="item-top">
            <span class="pill" style="background:{pcolor['edge']};">{pillar_label}</span>
            <span class="status-dot" style="background:{status_color};" title="{html.escape(it['status'])}"></span>
          </div>
          <div class="item-title">{title}</div>
        </div>''')

    return f'''<div class="{' '.join(classes)}" style="{style}">
      <div class="cell-head">{''.join(header_parts)}</div>
      <div class="cell-body">{''.join(body_parts)}</div>
    </div>'''


def render_month(year: int, month: int, items_by_date: dict) -> str:
    weeks = build_month_grid(year, month, items_by_date)
    title = f'{HEB_GREG_MONTHS[month]} {year}'

    head_cells = ''.join(f'<div class="wd">{wd}</div>' for wd in HEB_WEEKDAYS)
    rows_html = []
    for week in weeks:
        rows_html.append('<div class="week">' + ''.join(render_cell(c) for c in week) + '</div>')

    return f'''
    <section class="month">
      <h2 class="month-title">{title}</h2>
      <div class="weekdays">{head_cells}</div>
      <div class="grid">
        {''.join(rows_html)}
      </div>
    </section>
    '''


def render_legend() -> str:
    pillar_chips = ''.join(
        f'<span class="legend-chip"><span class="sw" style="background:{v["edge"]};"></span>{html.escape(v["label"])}</span>'
        for k, v in PILLAR_COLORS.items() if k != 'other'
    )
    status_chips = ''.join(
        f'<span class="legend-chip"><span class="sw round" style="background:{c};"></span>{html.escape(s)}</span>'
        for s, c in STATUS_COLORS.items()
    )
    return f'''
    <div class="legend">
      <div class="legend-group">
        <span class="legend-label">פינות תוכן</span>
        {pillar_chips}
      </div>
      <div class="legend-group">
        <span class="legend-label">סטטוס</span>
        {status_chips}
      </div>
    </div>
    '''


def render_modal_data(items: list) -> str:
    """Serialize items for client-side modal."""
    slim = []
    for it in items:
        pcolor = PILLAR_COLORS.get(it['pillar_key'], PILLAR_COLORS['other'])
        slim.append({
            'num': it['num'],
            'date': it['date_iso'],
            'day': it['day'],
            'pillar_key': it['pillar_key'],
            'pillar_label': pcolor['label'],
            'pillar_edge': pcolor['edge'],
            'title': it['title'],
            'explanation': it['explanation'],
            'visuals': it['visuals'],
            'copy_on_visual': it['copy_on_visual'],
            'captions': it['captions'],
            'status': it['status'],
        })
    return json.dumps(slim, ensure_ascii=False)


CSS = '''
:root {
  --bg: #FAFAF7;
  --paper: #FFFFFF;
  --ink: #1F2937;
  --ink-soft: #6B7280;
  --border: #E5E7EB;
  --border-strong: #D1D5DB;
  --weekend: #FDF6E3;
  --saturday: #F5EAD2;
  --outside-bg: #F9FAFB;
  --outside-ink: #D1D5DB;
  --accent: #0F172A;
  --shadow: 0 1px 2px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.06);
  --font: 'Rubik', system-ui, -apple-system, 'Segoe UI', sans-serif;
}

* { box-sizing: border-box; }
html, body { margin:0; padding:0; }
body {
  font-family: var(--font);
  direction: rtl;
  background: var(--bg);
  color: var(--ink);
  font-size: 14px;
  line-height: 1.5;
  min-height: 100vh;
}

.page {
  max-width: 1840px;
  margin: 0 auto;
  padding: 28px 32px 48px;
}

/* HEADER */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow);
  margin-bottom: 22px;
}
.header-right { display:flex; align-items:center; gap:18px; }
.header img.logo { height: 48px; width: auto; display: block; }
.header-titles h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.01em;
}
.header-titles .sub {
  font-size: 13px;
  color: var(--ink-soft);
  margin-top: 2px;
}
.header-meta {
  text-align: left;
  font-size: 12px;
  color: var(--ink-soft);
}
.header-meta .count {
  font-size: 13px;
  color: var(--accent);
  font-weight: 600;
}

/* LEGEND */
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 22px;
  align-items: center;
  padding: 14px 20px;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 12px;
  margin-bottom: 22px;
  box-shadow: var(--shadow);
}
.legend-group { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.legend-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-soft);
  letter-spacing: 0.05em;
  margin-left: 6px;
  padding: 3px 8px;
  background: #F3F4F6;
  border-radius: 4px;
}
.legend-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink);
}
.legend-chip .sw {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  display: inline-block;
}
.legend-chip .sw.round { border-radius: 50%; }

/* MONTHS LAYOUT - SIDE BY SIDE */
.months {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 22px;
}
@media (max-width: 1200px) {
  .months { grid-template-columns: 1fr; }
}

.month {
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px;
  box-shadow: var(--shadow);
}
.month-title {
  margin: 0 0 14px;
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  text-align: center;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

/* WEEKDAYS HEADER */
.weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
  margin-bottom: 6px;
}
.wd {
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-soft);
  padding: 6px 0;
  text-transform: none;
  letter-spacing: 0.02em;
}

/* GRID */
.grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.week {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}

/* CELL */
.cell {
  position: relative;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 8px;
  min-height: 110px;
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}
.cell.friday { background: var(--weekend); }
.cell.saturday { background: var(--saturday); border-color: #E5D49A; }
.cell.outside {
  background: var(--outside-bg);
  border-color: transparent;
}
.cell.outside .cell-head { opacity: 0.35; }
.cell.outside .cell-body { display: none; }
.cell.holiday::after {
  content: '';
  position: absolute;
  top: 0; left: 0; bottom: 0;
  width: 3px;
  background: #B45309;
  border-radius: 8px 0 0 8px;
}

.cell-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
  padding-bottom: 4px;
  border-bottom: 1px dashed rgba(0,0,0,0.06);
  min-height: 32px;
}
.cell-head .num {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  line-height: 1;
}
.cell-head .heb {
  font-size: 11px;
  color: var(--ink-soft);
  font-weight: 500;
  line-height: 1.2;
}
.cell-head .hol {
  width: 100%;
  font-size: 10px;
  font-weight: 600;
  color: #B45309;
  margin-top: 2px;
  letter-spacing: 0.02em;
}

.cell-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
}

/* ITEM CHIP */
.item {
  background: rgba(255,255,255,0.7);
  border-radius: 5px;
  padding: 4px 6px;
  cursor: pointer;
  transition: transform 0.1s ease, box-shadow 0.1s ease;
}
.item:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0,0,0,0.1);
  background: #FFFFFF;
}
.item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  margin-bottom: 2px;
}
.item-top .pill {
  font-size: 9px;
  font-weight: 600;
  color: white;
  padding: 1px 5px;
  border-radius: 8px;
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 90%;
}
.item-top .status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 1.5px white;
}
.item-title {
  font-size: 11.5px;
  font-weight: 500;
  color: var(--ink);
  line-height: 1.25;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* MODAL */
.modal-bg {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(4px);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 40px 20px;
}
.modal-bg.open { display: flex; }
.modal {
  background: var(--paper);
  border-radius: 16px;
  max-width: 880px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 50px rgba(0,0,0,0.25);
  direction: rtl;
}
.modal-head {
  padding: 22px 28px 16px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--paper);
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.modal-head-left .modal-pill {
  font-size: 11px;
  font-weight: 600;
  color: white;
  padding: 3px 10px;
  border-radius: 12px;
  display: inline-block;
  margin-bottom: 8px;
}
.modal-head-left h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--accent);
}
.modal-head-left .date-row {
  margin-top: 6px;
  font-size: 13px;
  color: var(--ink-soft);
}
.modal-close {
  background: #F3F4F6;
  border: none;
  font-size: 18px;
  font-weight: 600;
  color: var(--ink-soft);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease;
}
.modal-close:hover { background: #E5E7EB; color: var(--ink); }

.modal-body {
  padding: 22px 28px 28px;
}
.modal-section {
  margin-bottom: 24px;
}
.modal-section:last-child { margin-bottom: 0; }
.modal-section h3 {
  margin: 0 0 10px;
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-soft);
  letter-spacing: 0.06em;
  text-transform: none;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}
.modal-section .explanation {
  font-size: 14px;
  line-height: 1.6;
  color: var(--ink);
  white-space: pre-wrap;
}
.pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 720px) { .pair { grid-template-columns: 1fr; } }
.pair-item {
  background: #F9FAFB;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
}
.pair-item .pair-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-soft);
  margin-bottom: 8px;
}
.pair-item .pair-text {
  font-size: 13.5px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--ink);
}

.footer {
  margin-top: 30px;
  text-align: center;
  font-size: 12px;
  color: var(--ink-soft);
}
'''

JS = '''
const ITEMS_DATA = __ITEMS_JSON__;
const itemsByNum = Object.fromEntries(ITEMS_DATA.map(i => [i.num, i]));

function openModal(num) {
  const it = itemsByNum[num];
  if (!it) return;

  const modal = document.getElementById('modal');
  const inner = document.getElementById('modal-inner');

  inner.innerHTML = `
    <div class="modal-head">
      <div class="modal-head-left">
        <span class="modal-pill" style="background:${it.pillar_edge};">${it.pillar_label}</span>
        <h2>${escapeHtml(it.title)}</h2>
        <div class="date-row">רעיון #${it.num} · ${formatDateHe(it.date)} (יום ${it.day}) · סטטוס: ${it.status}</div>
      </div>
      <button class="modal-close" aria-label="סגור" onclick="closeModal()">×</button>
    </div>
    <div class="modal-body">
      ${it.explanation ? `<div class="modal-section">
        <h3>הסבר לרעיון</h3>
        <div class="explanation">${escapeHtml(it.explanation)}</div>
      </div>` : ''}
      <div class="modal-section">
        <h3>2 הצעות ויזואל</h3>
        <div class="pair">
          <div class="pair-item"><div class="pair-label">ויזואל א'</div><div class="pair-text">${escapeHtml(it.visuals.a || '—')}</div></div>
          <div class="pair-item"><div class="pair-label">ויזואל ב'</div><div class="pair-text">${escapeHtml(it.visuals.b || '—')}</div></div>
        </div>
      </div>
      <div class="modal-section">
        <h3>2 הצעות קופי על ויזואל</h3>
        <div class="pair">
          <div class="pair-item"><div class="pair-label">קופי א'</div><div class="pair-text">${escapeHtml(it.copy_on_visual.a || '—')}</div></div>
          <div class="pair-item"><div class="pair-label">קופי ב'</div><div class="pair-text">${escapeHtml(it.copy_on_visual.b || '—')}</div></div>
        </div>
      </div>
      <div class="modal-section">
        <h3>2 הצעות קפשן</h3>
        <div class="pair">
          <div class="pair-item"><div class="pair-label">קפשן א'</div><div class="pair-text">${escapeHtml(it.captions.a || '—')}</div></div>
          <div class="pair-item"><div class="pair-label">קפשן ב'</div><div class="pair-text">${escapeHtml(it.captions.b || '—')}</div></div>
        </div>
      </div>
    </div>
  `;
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
  document.body.style.overflow = '';
}

function escapeHtml(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatDateHe(iso) {
  const [y, m, d] = iso.split('-');
  return `${parseInt(d)}.${parseInt(m)}.${y.slice(2)}`;
}

document.addEventListener('click', (e) => {
  const item = e.target.closest('.item');
  if (item) {
    const num = parseInt(item.dataset.num);
    if (num) openModal(num);
    return;
  }
  if (e.target.classList.contains('modal-bg')) closeModal();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
});
'''


def render_html(data: dict, logo_b64: str) -> str:
    items = data['items']
    items_by_date = {}
    for it in items:
        items_by_date.setdefault(it['date_iso'], []).append(it)

    client = data['client']
    period = data['period']
    count = data['count']

    # Find date range for months
    dates = sorted(it['date_iso'] for it in items)
    first = dates[0]
    last = dates[-1]
    year_a, month_a = int(first[:4]), int(first[5:7])
    year_b, month_b = int(last[:4]), int(last[5:7])

    months_html_parts = []
    seen = set()
    cur_y, cur_m = year_a, month_a
    while (cur_y, cur_m) <= (year_b, month_b):
        if (cur_y, cur_m) not in seen:
            months_html_parts.append(render_month(cur_y, cur_m, items_by_date))
            seen.add((cur_y, cur_m))
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1

    legend_html = render_legend()
    items_json = render_modal_data(items)
    js_filled = JS.replace('__ITEMS_JSON__', items_json)

    logo_tag = f'<img class="logo" src="data:image/png;base64,{logo_b64}" alt="זליגר שומרון" />'

    return f'''<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5" />
<title>{html.escape(client)} | גאנט {html.escape(period)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="page">
  <header class="header">
    <div class="header-right">
      {logo_tag}
      <div class="header-titles">
        <h1>{html.escape(client)} · גאנט {html.escape(period)}</h1>
        <div class="sub">תכנון תוכן חודשי</div>
      </div>
    </div>
    <div class="header-meta">
      <div class="count">{count} תכנים</div>
      <div>גאנט חי · לחץ על תא לפרטים</div>
    </div>
  </header>

  {legend_html}

  <div class="months">
    {''.join(months_html_parts)}
  </div>

  <div class="footer">מחלקת הסושיאל · זליגר שומרון</div>
</div>

<div class="modal-bg" id="modal">
  <div class="modal" id="modal-inner"></div>
</div>

<script>{js_filled}</script>
</body>
</html>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--logo', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.data).read_text(encoding='utf-8'))
    logo_b64 = base64.b64encode(Path(args.logo).read_bytes()).decode('ascii')

    out_html = render_html(data, logo_b64)
    Path(args.out).write_text(out_html, encoding='utf-8')
    print(f'WROTE {args.out} ({len(out_html):,} chars)')


if __name__ == '__main__':
    main()
