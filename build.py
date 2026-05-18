# -*- coding: utf-8 -*-
"""
Build V4: data.json -> index.html.

Premium dark mode monthly Gantt viewer for Seliger Shomron clients.
- One month per view, tabs between months
- 3 content types only (post / story / reel) drive color
- Rubik (Hebrew) + Inter (English/digits)
- Generous breathing room
- Modal: editable copy (right) + image dropzone (left), localStorage persistence
- Status dropdown per cell with localStorage persistence
"""
import sys, io, json, html, argparse, base64, calendar
from datetime import date
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pyluach.dates import GregorianDate


# Three content types - only these drive color.
TYPE_COLORS = {
    'post':  {'accent': '#67E8F9', 'soft': 'rgba(103,232,249,0.14)', 'label': 'פוסט'},
    'story': {'accent': '#C4B5FD', 'soft': 'rgba(196,181,253,0.14)', 'label': 'סטורי'},
    'reel':  {'accent': '#FDA4AF', 'soft': 'rgba(253,164,175,0.14)', 'label': 'רילס'},
}

STATUS_COLORS = {
    'בעבודה':       '#94A3B8',
    'בעיצוב':       '#60A5FA',
    'ממתין לאישור': '#FBBF24',
    'אושר':          '#34D399',
}

STATUS_ORDER = ['בעבודה', 'בעיצוב', 'ממתין לאישור', 'אושר']

HEB_WEEKDAYS = ['ראשון','שני','שלישי','רביעי','חמישי','שישי','שבת']

# Hebrew names for Gregorian months
HEB_GREG_MONTHS = ['','ינואר','פברואר','מרץ','אפריל','מאי','יוני',
                   'יולי','אוגוסט','ספטמבר','אוקטובר','נובמבר','דצמבר']

HOLIDAYS_2026 = {
    '2026-05-22': 'ערב שבועות',
    '2026-05-23': 'חג שבועות',
    '2026-06-16': 'ראש חודש תמוז',
    '2026-06-21': 'יום אבא',
}


def heb_date(d: date) -> tuple[str, str]:
    gd = GregorianDate(d.year, d.month, d.day)
    hd = gd.to_heb()
    full = hd.hebrew_date_string()
    parts = full.split()
    return parts[0], full


def build_month_grid(year: int, month: int, items_by_date: dict) -> list:
    cal = calendar.Calendar(firstweekday=6)
    weeks = []
    for week_dates in cal.monthdatescalendar(year, month):
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
        cell = {**cell, 'items': [], 'holiday': ''}
    if cell['is_friday']:
        classes.append('friday')
    if cell['is_saturday']:
        classes.append('saturday')
    if cell['holiday']:
        classes.append('holiday')
    if cell['items']:
        classes.append('has-content')

    header_parts = [
        f'<div class="cell-num">{cell["day_num"]}</div>',
        f'<div class="cell-heb">{html.escape(cell["heb_short"])}</div>',
    ]
    if cell['holiday']:
        header_parts.append(f'<div class="cell-hol">{html.escape(cell["holiday"])}</div>')

    body_parts = []
    for it in cell['items']:
        tc = TYPE_COLORS.get(it['type_key'], TYPE_COLORS['post'])
        pillar = html.escape(it.get('pillar_label', ''))
        title = html.escape(it['title'])
        body_parts.append(f'''
        <div class="item" data-num="{it['num']}" data-type="{it['type_key']}">
          <div class="item-pillar">{pillar}</div>
          <div class="item-title">{title}</div>
        </div>''')

    return f'''<div class="{' '.join(classes)}" data-iso="{cell['iso']}">
      <div class="cell-head">{''.join(header_parts)}</div>
      <div class="cell-body">{''.join(body_parts)}</div>
    </div>'''


def render_month(year: int, month: int, items_by_date: dict, is_active: bool) -> str:
    weeks = build_month_grid(year, month, items_by_date)
    title = f'{HEB_GREG_MONTHS[month]} {year}'

    head_cells = ''.join(f'<div class="wd">{wd}</div>' for wd in HEB_WEEKDAYS)
    rows_html = []
    for week in weeks:
        rows_html.append('<div class="week">' + ''.join(render_cell(c) for c in week) + '</div>')

    active_cls = ' active' if is_active else ''
    return f'''
    <section class="month{active_cls}" data-month="{year}-{month:02d}">
      <div class="weekdays">{head_cells}</div>
      <div class="grid">
        {''.join(rows_html)}
      </div>
    </section>
    '''


def render_legend() -> str:
    type_chips = ''.join(
        f'<span class="legend-chip"><span class="sw" style="background:{v["accent"]};"></span>{html.escape(v["label"])}</span>'
        for v in TYPE_COLORS.values()
    )
    status_chips = ''.join(
        f'<span class="legend-chip"><span class="sw round" style="background:{c}; box-shadow:0 0 6px {c}80;"></span>{html.escape(s)}</span>'
        for s, c in STATUS_COLORS.items()
    )
    return f'''
    <div class="legend">
      <div class="legend-group">
        <span class="legend-label">סוג תוכן</span>
        {type_chips}
      </div>
      <div class="legend-divider"></div>
      <div class="legend-group">
        <span class="legend-label">סטטוס</span>
        {status_chips}
      </div>
    </div>
    '''


def render_tabs(months: list) -> str:
    if len(months) <= 1:
        return ''
    btns = []
    for i, (y, m) in enumerate(months):
        title = f'{HEB_GREG_MONTHS[m]} <span class="tab-year">{y}</span>'
        active = ' active' if i == 0 else ''
        btns.append(f'<button class="tab{active}" data-month="{y}-{m:02d}">{title}</button>')
    return f'<div class="tabs">{"".join(btns)}</div>'


def render_modal_data(items: list) -> str:
    slim = []
    for it in items:
        tc = TYPE_COLORS.get(it['type_key'], TYPE_COLORS['post'])
        slim.append({
            'num': it['num'],
            'date': it['date_iso'],
            'day': it['day'],
            'type_key': it['type_key'],
            'type_label': tc['label'],
            'type_accent': tc['accent'],
            'type_soft': tc['soft'],
            'pillar_label': it.get('pillar_label', ''),
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
  /* Slate dark base */
  --bg:        #07101F;
  --paper:     #0F1A2E;
  --paper-2:   #14223A;
  --paper-3:   #0C1828;
  --paper-4:   #18253F;
  --ink:       #F1F5F9;
  --ink-soft:  #94A3B8;
  --ink-faint: #475569;
  --ink-mute:  #64748B;
  --border:    #1E2D45;
  --border-soft: #182338;
  --accent-cyan: #67E8F9;
  --gold:      #FBBF24;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 20px rgba(0,0,0,0.35);
  --shadow-lg: 0 20px 60px rgba(0,0,0,0.5);

  /* Fonts - Hebrew = Rubik, English/digits = Inter (different family, complements Rubik) */
  --font-he: 'Rubik', system-ui, -apple-system, sans-serif;
  --font-en: 'Inter', system-ui, -apple-system, sans-serif;
  /* Inter first → Latin/digits picked from Inter, Hebrew falls through to Rubik */
  --font: 'Inter', 'Rubik', system-ui, sans-serif;
}

* { box-sizing: border-box; }
html, body { margin:0; padding:0; }
body {
  font-family: var(--font);
  direction: rtl;
  background: var(--bg);
  color: var(--ink);
  font-size: 14px;
  line-height: 1.55;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

.page {
  max-width: 1480px;
  margin: 0 auto;
  padding: 36px 40px 60px;
}

/* HEADER */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 26px 32px;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow-md);
  margin-bottom: 28px;
}
.header-brand {
  display: flex;
  align-items: center;
  filter: invert(1) hue-rotate(180deg) brightness(1.05);
}
.header img.logo {
  height: 62px;
  width: auto;
  display: block;
}
.header-titles {
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.header-titles h1 {
  margin: 0;
  font-family: var(--font-he);
  font-size: 32px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1.05;
}
.header-titles .period {
  font-family: var(--font);
  font-size: 16px;
  color: var(--ink-soft);
  font-weight: 400;
  letter-spacing: 0.01em;
}
.header-titles .count-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}
.header-titles .count-pill {
  font-family: var(--font-en);
  font-size: 11px;
  font-weight: 600;
  color: var(--accent-cyan);
  padding: 4px 12px;
  background: rgba(103,232,249,0.08);
  border: 1px solid rgba(103,232,249,0.25);
  border-radius: 999px;
  letter-spacing: 0.02em;
}
.header-titles .hint {
  font-size: 12px;
  color: var(--ink-mute);
  letter-spacing: 0.01em;
}

/* TABS */
.tabs {
  display: flex;
  gap: 8px;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 6px;
  margin-bottom: 24px;
  width: fit-content;
  margin-inline: auto;
}
.tab {
  font-family: var(--font);
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-soft);
  background: transparent;
  border: none;
  padding: 10px 22px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  letter-spacing: 0.01em;
}
.tab .tab-year {
  font-family: var(--font-en);
  font-weight: 400;
  color: var(--ink-mute);
  margin-inline-start: 6px;
}
.tab:hover {
  color: var(--ink);
  background: var(--paper-2);
}
.tab.active {
  background: var(--accent-cyan);
  color: var(--bg);
}
.tab.active .tab-year {
  color: var(--bg);
  opacity: 0.7;
}

/* LEGEND */
.legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px 22px;
  padding: 14px 20px;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 999px;
  margin-bottom: 24px;
  width: fit-content;
  margin-inline: auto;
}
.legend-divider {
  width: 1px;
  height: 18px;
  background: var(--border);
}
.legend-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.legend-label {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--ink-mute);
  letter-spacing: 0.08em;
  padding: 3px 9px;
  background: rgba(148,163,184,0.08);
  border-radius: 8px;
  text-transform: none;
}
.legend-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12.5px;
  color: var(--ink);
}
.legend-chip .sw {
  width: 12px;
  height: 12px;
  border-radius: 3px;
}
.legend-chip .sw.round { border-radius: 50%; }

/* MONTH (one at a time via tabs) */
.month {
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 26px 28px 32px;
  box-shadow: var(--shadow-md);
  display: none;
}
.month.active { display: block; }

/* WEEKDAY HEADER */
.weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 8px;
  margin-bottom: 10px;
}
.wd {
  text-align: center;
  font-family: var(--font);
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-soft);
  padding: 8px 0 10px;
  letter-spacing: 0.04em;
}

.grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.week {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 8px;
}

/* CELL */
.cell {
  position: relative;
  background: var(--paper-2);
  border: 1px solid var(--border);
  border-radius: 10px;
  min-height: 138px;
  padding: 12px 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: hidden;
  transition: all 0.15s ease;
}
.cell:hover {
  border-color: rgba(148,163,184,0.35);
  background: var(--paper-4);
  transform: translateY(-1px);
}

.cell.friday { background: var(--paper-3); }
.cell.saturday {
  background: var(--paper-3);
  border-color: rgba(251,191,36,0.18);
}
.cell.saturday::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(251,191,36,0.04), transparent 60%);
  pointer-events: none;
  border-radius: 10px;
}
.cell.outside {
  background: transparent;
  border-color: var(--border-soft);
}
.cell.outside .cell-head { opacity: 0.35; }
.cell.outside .cell-body { display: none; }
.cell.outside .cell-num,
.cell.outside .cell-heb { color: var(--ink-faint); }

.cell.holiday::before {
  content: '';
  position: absolute;
  top: 0; right: 0;
  width: 0; height: 0;
  border-style: solid;
  border-width: 16px 16px 0 0;
  border-color: var(--gold) transparent transparent transparent;
  opacity: 0.9;
  pointer-events: none;
}

/* CELL HEAD: numbers, dates */
.cell-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-soft);
  min-height: 36px;
}
.cell-num {
  font-family: var(--font-en);
  font-size: 20px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1;
  letter-spacing: -0.02em;
}
.cell-heb {
  font-family: var(--font-he);
  font-size: 11.5px;
  color: var(--ink-soft);
  font-weight: 500;
  line-height: 1.3;
}
.cell-hol {
  width: 100%;
  font-family: var(--font-he);
  font-size: 10.5px;
  font-weight: 600;
  color: var(--gold);
  margin-top: 4px;
  letter-spacing: 0.01em;
}

.cell-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  padding-top: 4px;
}

/* ITEM CARD - color-driven by type, text RTL with title centered */
.item {
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
  overflow: hidden;
}
.item::before {
  content: '';
  position: absolute;
  top: 0; right: 0; left: 0;
  height: 3px;
  background: var(--item-accent, #67E8F9);
}
.item[data-type="post"]  { --item-accent: #67E8F9; --item-soft: rgba(103,232,249,0.10); }
.item[data-type="story"] { --item-accent: #C4B5FD; --item-soft: rgba(196,181,253,0.10); }
.item[data-type="reel"]  { --item-accent: #FDA4AF; --item-soft: rgba(253,164,175,0.10); }
.item:hover {
  background: var(--item-soft, rgba(103,232,249,0.10));
  border-color: var(--item-accent, #67E8F9);
  transform: translateY(-1px);
}
.item-pillar {
  font-family: var(--font-he);
  font-size: 10.5px;
  font-weight: 500;
  color: var(--ink-mute);
  text-align: right;
  letter-spacing: 0.01em;
  margin-top: 2px;
  margin-bottom: 4px;
}
.item-title {
  font-family: var(--font-he);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.35;
  text-align: center;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* MODAL */
.modal-bg {
  position: fixed;
  inset: 0;
  background: rgba(7, 16, 31, 0.78);
  backdrop-filter: blur(8px);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 40px 20px;
}
.modal-bg.open { display: flex; }
.modal {
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 18px;
  max-width: 1100px;
  width: 100%;
  max-height: 92vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
  direction: rtl;
}
.modal-head {
  padding: 26px 32px 22px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--paper);
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
}
.modal-head-left .modal-pill {
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 999px;
  display: inline-block;
  margin-bottom: 12px;
}
.modal-head-left h2 {
  margin: 0;
  font-family: var(--font-he);
  font-size: 26px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.015em;
}
.modal-head-left .pillar-name {
  font-family: var(--font-he);
  font-size: 13px;
  color: var(--ink-soft);
  margin-top: 4px;
}
.modal-head-left .date-row {
  margin-top: 10px;
  font-family: var(--font);
  font-size: 12.5px;
  color: var(--ink-soft);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.modal-head-left .date-row .dot {
  width: 4px; height: 4px; border-radius: 50%; background: var(--ink-mute);
}
.modal-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.status-select {
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 500;
  background: var(--paper-2);
  border: 1px solid var(--border);
  color: var(--ink);
  padding: 4px 28px 4px 10px;
  border-radius: 999px;
  cursor: pointer;
  appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, var(--ink-soft) 50%), linear-gradient(135deg, var(--ink-soft) 50%, transparent 50%);
  background-position: calc(100% - 14px) 50%, calc(100% - 9px) 50%;
  background-size: 5px 5px;
  background-repeat: no-repeat;
}
.status-dot {
  width: 9px; height: 9px; border-radius: 50%;
  box-shadow: 0 0 6px currentColor;
}

.modal-close {
  background: rgba(148,163,184,0.08);
  border: 1px solid var(--border);
  font-size: 18px;
  font-weight: 500;
  color: var(--ink-soft);
  width: 36px; height: 36px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  flex-shrink: 0;
}
.modal-close:hover {
  background: rgba(148,163,184,0.18);
  color: var(--ink);
}

.modal-body { padding: 26px 32px 32px; }

/* PRIMARY ROW: image dropzone (left) + accompanying copy (right) */
.modal-primary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-bottom: 28px;
}
@media (max-width: 820px) { .modal-primary { grid-template-columns: 1fr; } }

.dropzone {
  background: var(--paper-2);
  border: 2px dashed var(--border);
  border-radius: 14px;
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
  overflow: hidden;
}
.dropzone:hover {
  border-color: var(--accent-cyan);
  background: rgba(103,232,249,0.04);
}
.dropzone.has-image { padding: 0; border-style: solid; }
.dropzone img.uploaded {
  max-width: 100%;
  max-height: 380px;
  border-radius: 12px;
  display: block;
}
.dropzone .dz-icon {
  width: 44px; height: 44px;
  color: var(--ink-mute);
}
.dropzone .dz-text {
  font-family: var(--font-he);
  font-size: 14px;
  color: var(--ink-soft);
  text-align: center;
  font-weight: 500;
}
.dropzone .dz-sub {
  font-family: var(--font);
  font-size: 11.5px;
  color: var(--ink-mute);
}
.dropzone input[type="file"] { display: none; }
.dz-remove {
  position: absolute;
  top: 10px; left: 10px;
  background: rgba(0,0,0,0.55);
  border: 1px solid rgba(255,255,255,0.15);
  color: white;
  border-radius: 999px;
  font-size: 11px;
  padding: 4px 12px;
  cursor: pointer;
  display: none;
}
.dropzone.has-image .dz-remove { display: block; }

.copy-area {
  display: flex;
  flex-direction: column;
}
.copy-area label {
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-mute);
  letter-spacing: 0.04em;
  margin-bottom: 8px;
}
.copy-area textarea {
  font-family: var(--font-he);
  font-size: 14px;
  line-height: 1.65;
  color: var(--ink);
  background: var(--paper-2);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 18px;
  resize: none;
  flex: 1;
  min-height: 280px;
  direction: rtl;
  text-align: right;
  transition: border-color 0.15s ease;
}
.copy-area textarea:focus {
  outline: none;
  border-color: var(--accent-cyan);
}
.copy-area textarea::placeholder { color: var(--ink-faint); }
.copy-saved {
  font-family: var(--font-he);
  font-size: 11px;
  color: var(--ink-mute);
  margin-top: 6px;
  text-align: left;
  min-height: 14px;
}

/* SECONDARY: original explanation + 2x3 options collapsible */
.modal-section {
  margin-bottom: 22px;
}
.modal-section:last-child { margin-bottom: 0; }
.modal-section > h3 {
  margin: 0 0 12px;
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 700;
  color: var(--ink-mute);
  letter-spacing: 0.08em;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-soft);
}
.explanation {
  font-family: var(--font-he);
  font-size: 14px;
  line-height: 1.7;
  color: var(--ink-soft);
  white-space: pre-wrap;
}

details.collapsible {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--paper-2);
  margin-bottom: 12px;
}
details.collapsible > summary {
  font-family: var(--font-he);
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  padding: 14px 18px;
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
details.collapsible > summary::-webkit-details-marker { display: none; }
details.collapsible > summary::after {
  content: '+';
  font-family: var(--font-en);
  font-size: 18px;
  font-weight: 300;
  color: var(--ink-soft);
  transition: transform 0.15s ease;
}
details.collapsible[open] > summary::after { content: '−'; }
details.collapsible > .pair {
  padding: 0 18px 18px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 700px) { details.collapsible > .pair { grid-template-columns: 1fr; } }
.pair-item {
  background: var(--paper);
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 14px 16px;
}
.pair-item .pair-label {
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-mute);
  margin-bottom: 8px;
  letter-spacing: 0.04em;
}
.pair-item .pair-text {
  font-family: var(--font-he);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--ink);
}

.footer {
  margin-top: 36px;
  text-align: center;
  font-family: var(--font);
  font-size: 11px;
  color: var(--ink-mute);
  letter-spacing: 0.04em;
}
'''


JS = '''
const ITEMS_DATA = __ITEMS_JSON__;
const itemsByNum = Object.fromEntries(ITEMS_DATA.map(i => [i.num, i]));
const CLIENT_KEY = '__CLIENT_KEY__';

const STATUS_COLORS = {
  'בעבודה': '#94A3B8',
  'בעיצוב': '#60A5FA',
  'ממתין לאישור': '#FBBF24',
  'אושר': '#34D399',
};
const STATUS_ORDER = ['בעבודה', 'בעיצוב', 'ממתין לאישור', 'אושר'];

/* ---------- localStorage helpers (per-client, per-item) ---------- */
function lsKey(num, field) { return `gantt:${CLIENT_KEY}:${num}:${field}`; }
function getLocal(num, field, fallback) {
  try { return localStorage.getItem(lsKey(num, field)) ?? fallback; } catch (e) { return fallback; }
}
function setLocal(num, field, value) {
  try { localStorage.setItem(lsKey(num, field), value); } catch (e) {}
}

/* ---------- Status decoration on cells (read from localStorage) ---------- */
function applyStatusToCells() {
  document.querySelectorAll('.item').forEach(el => {
    const num = parseInt(el.dataset.num);
    const status = getLocal(num, 'status', itemsByNum[num]?.status || 'בעבודה');
    el.dataset.status = status;
    // soft top-stripe color = type accent; but add a status border-bottom band:
    const c = STATUS_COLORS[status] || STATUS_COLORS['בעבודה'];
    el.style.boxShadow = `inset 0 -3px 0 ${c}`;
  });
}

/* ---------- Tabs ---------- */
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const m = tab.dataset.month;
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t === tab));
    document.querySelectorAll('.month').forEach(s => s.classList.toggle('active', s.dataset.month === m));
    try { localStorage.setItem('gantt:active-month:' + CLIENT_KEY, m); } catch (e) {}
  });
});
/* Restore last active month */
try {
  const saved = localStorage.getItem('gantt:active-month:' + CLIENT_KEY);
  if (saved) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.month === saved));
    document.querySelectorAll('.month').forEach(s => s.classList.toggle('active', s.dataset.month === saved));
  }
} catch (e) {}

/* ---------- Modal ---------- */
function openModal(num) {
  const it = itemsByNum[num];
  if (!it) return;

  const status = getLocal(num, 'status', it.status || 'בעבודה');
  const savedCopy = getLocal(num, 'copy', '');
  const savedImg = getLocal(num, 'img', '');

  const statusOpts = STATUS_ORDER.map(s =>
    `<option value="${s}" ${s === status ? 'selected' : ''}>${s}</option>`
  ).join('');

  const modal = document.getElementById('modal');
  const inner = document.getElementById('modal-inner');

  inner.innerHTML = `
    <div class="modal-head">
      <div class="modal-head-left">
        <span class="modal-pill" style="background:${it.type_soft}; color:${it.type_accent}; border:1px solid ${it.type_accent}40;">${it.type_label}</span>
        <h2>${escapeHtml(it.title)}</h2>
        <div class="pillar-name">${escapeHtml(it.pillar_label || '')}</div>
        <div class="date-row">
          <span>רעיון #${it.num}</span>
          <span class="dot"></span>
          <span>${formatDateHe(it.date)} (יום ${escapeHtml(it.day)})</span>
          <span class="dot"></span>
          <span class="modal-status">
            <span class="status-dot" id="statusDot" style="background:${STATUS_COLORS[status]}; color:${STATUS_COLORS[status]};"></span>
            <select class="status-select" id="statusSelect" data-num="${num}">${statusOpts}</select>
          </span>
        </div>
      </div>
      <button class="modal-close" aria-label="סגור" onclick="closeModal()">×</button>
    </div>
    <div class="modal-body">
      <div class="modal-primary">
        <div class="dropzone ${savedImg ? 'has-image' : ''}" id="dropzone" data-num="${num}">
          <input type="file" id="fileInput" accept="image/*">
          ${savedImg
            ? `<img class="uploaded" src="${savedImg}" alt="ויזואל" /><button class="dz-remove" onclick="event.stopPropagation(); removeImage(${num})">הסר</button>`
            : `<svg class="dz-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
               <div class="dz-text">גרור תמונה לכאן או לחץ לבחירה</div>
               <div class="dz-sub">PNG · JPG · WebP</div>`
          }
        </div>
        <div class="copy-area">
          <label>קופי נלווה (ניתן לעריכה)</label>
          <textarea id="copyArea" data-num="${num}" placeholder="כתוב כאן את הקופי הסופי לפרסום...">${escapeHtml(savedCopy)}</textarea>
          <div class="copy-saved" id="copySaved"></div>
        </div>
      </div>

      ${it.explanation ? `<div class="modal-section">
        <h3>הסבר לרעיון</h3>
        <div class="explanation">${escapeHtml(it.explanation)}</div>
      </div>` : ''}

      <details class="collapsible">
        <summary>2 הצעות ויזואל</summary>
        <div class="pair">
          <div class="pair-item"><div class="pair-label">ויזואל א'</div><div class="pair-text">${escapeHtml(it.visuals.a || '—')}</div></div>
          <div class="pair-item"><div class="pair-label">ויזואל ב'</div><div class="pair-text">${escapeHtml(it.visuals.b || '—')}</div></div>
        </div>
      </details>

      <details class="collapsible">
        <summary>2 הצעות קופי על ויזואל</summary>
        <div class="pair">
          <div class="pair-item"><div class="pair-label">קופי א'</div><div class="pair-text">${escapeHtml(it.copy_on_visual.a || '—')}</div></div>
          <div class="pair-item"><div class="pair-label">קופי ב'</div><div class="pair-text">${escapeHtml(it.copy_on_visual.b || '—')}</div></div>
        </div>
      </details>

      <details class="collapsible">
        <summary>2 הצעות קפשן</summary>
        <div class="pair">
          <div class="pair-item"><div class="pair-label">קפשן א'</div><div class="pair-text">${escapeHtml(it.captions.a || '—')}</div></div>
          <div class="pair-item"><div class="pair-label">קפשן ב'</div><div class="pair-text">${escapeHtml(it.captions.b || '—')}</div></div>
        </div>
      </details>
    </div>
  `;

  modal.classList.add('open');
  document.body.style.overflow = 'hidden';

  // Wire up status select
  const sel = document.getElementById('statusSelect');
  const dot = document.getElementById('statusDot');
  sel.addEventListener('change', () => {
    const v = sel.value;
    setLocal(num, 'status', v);
    const c = STATUS_COLORS[v] || '#94A3B8';
    dot.style.background = c;
    dot.style.color = c;
    applyStatusToCells();
  });

  // Wire up copy editor (debounced save)
  const ta = document.getElementById('copyArea');
  const savedHint = document.getElementById('copySaved');
  let saveTimer;
  ta.addEventListener('input', () => {
    clearTimeout(saveTimer);
    savedHint.textContent = 'מקליד...';
    saveTimer = setTimeout(() => {
      setLocal(num, 'copy', ta.value);
      savedHint.textContent = '✓ נשמר אוטומטית';
      setTimeout(() => savedHint.textContent = '', 1800);
    }, 400);
  });

  // Wire up dropzone
  setupDropzone(num);
}

function setupDropzone(num) {
  const dz = document.getElementById('dropzone');
  const fi = document.getElementById('fileInput');
  if (!dz || !fi) return;
  dz.addEventListener('click', (e) => {
    if (e.target.classList.contains('dz-remove')) return;
    fi.click();
  });
  fi.addEventListener('change', (e) => {
    const f = e.target.files[0];
    if (f) handleImage(num, f);
  });
  dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.style.borderColor = '#67E8F9'; });
  dz.addEventListener('dragleave', () => { dz.style.borderColor = ''; });
  dz.addEventListener('drop', (e) => {
    e.preventDefault();
    dz.style.borderColor = '';
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith('image/')) handleImage(num, f);
  });
}

function handleImage(num, file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    const dataUrl = e.target.result;
    setLocal(num, 'img', dataUrl);
    openModal(num);
  };
  reader.readAsDataURL(file);
}

function removeImage(num) {
  try { localStorage.removeItem(lsKey(num, 'img')); } catch (e) {}
  openModal(num);
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

applyStatusToCells();
'''


def render_html(data: dict, logo_b64: str) -> str:
    items = data['items']
    items_by_date = {}
    for it in items:
        items_by_date.setdefault(it['date_iso'], []).append(it)

    client = data['client']
    period = data['period']
    count = data['count']

    dates = sorted(it['date_iso'] for it in items)
    first = dates[0]
    last = dates[-1]
    year_a, month_a = int(first[:4]), int(first[5:7])
    year_b, month_b = int(last[:4]), int(last[5:7])

    # Collect ordered list of months
    months = []
    cur_y, cur_m = year_a, month_a
    while (cur_y, cur_m) <= (year_b, month_b):
        months.append((cur_y, cur_m))
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1

    months_html_parts = []
    for i, (y, m) in enumerate(months):
        months_html_parts.append(render_month(y, m, items_by_date, is_active=(i == 0)))

    tabs_html = render_tabs(months)
    legend_html = render_legend()
    items_json = render_modal_data(items)

    # Client key for localStorage scoping (slug-ish)
    client_key = ''.join(c if c.isalnum() else '_' for c in client) or 'client'

    js_filled = JS.replace('__ITEMS_JSON__', items_json).replace('__CLIENT_KEY__', client_key)

    logo_tag = f'<img class="logo" src="data:image/png;base64,{logo_b64}" alt="זליגר שומרון" />'

    return f'''<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5" />
<title>{html.escape(client)} | גאנט {html.escape(period)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="page">
  <header class="header">
    <div class="header-brand">
      {logo_tag}
    </div>
    <div class="header-titles">
      <h1>{html.escape(client)}</h1>
      <div class="period">גאנט {html.escape(period)}</div>
      <div class="count-row">
        <span class="count-pill">{count} תכנים</span>
        <span class="hint">לחץ על תא לפרטים ועריכה</span>
      </div>
    </div>
  </header>

  {tabs_html}
  {legend_html}

  <div class="months-container">
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
