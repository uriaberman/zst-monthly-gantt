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

# Dark mode palette: lighter accent tones readable on slate-950 base.
# 'short' = compact label for in-cell chip (fits without truncation).
# 'label' = full label for modal/tooltip.
PILLAR_COLORS = {
    'numbers':   {'accent': '#38BDF8', 'chip_bg': 'rgba(56,189,248,0.15)',  'label': 'מאחורי המספרים', 'short': 'מספרים'},
    'question':  {'accent': '#A78BFA', 'chip_bg': 'rgba(167,139,250,0.15)', 'label': 'השאלה השבועית', 'short': 'שאלה'},
    'reel':      {'accent': '#FB7185', 'chip_bg': 'rgba(251,113,133,0.15)', 'label': 'רילס', 'short': 'רילס'},
    'voices':    {'accent': '#34D399', 'chip_bg': 'rgba(52,211,153,0.15)',  'label': 'קולות מהשטח', 'short': 'קולות'},
    'anchor':    {'accent': '#FBBF24', 'chip_bg': 'rgba(251,191,36,0.15)',  'label': 'עוגן / חג', 'short': 'עוגן'},
    'advocacy':  {'accent': '#F87171', 'chip_bg': 'rgba(248,113,113,0.15)', 'label': 'אדווקסי', 'short': 'אדווקסי'},
    'community': {'accent': '#22D3EE', 'chip_bg': 'rgba(34,211,238,0.15)',  'label': 'אנחנו כאן', 'short': 'קהילה'},
    'other':     {'accent': '#94A3B8', 'chip_bg': 'rgba(148,163,184,0.15)', 'label': 'אחר', 'short': 'אחר'},
}

STATUS_COLORS = {
    'בעבודה':       '#94A3B8',
    'בעיצוב':       '#60A5FA',
    'ממתין לאישור': '#FBBF24',
    'אושר':          '#34D399',
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
        cell = {**cell, 'items': [], 'holiday': ''}
    if cell['is_friday']:
        classes.append('friday')
    if cell['is_saturday']:
        classes.append('saturday')
    if cell['holiday']:
        classes.append('holiday')
    if cell['items']:
        classes.append('has-content')

    # Top accent line - color of primary item's pillar (subtle visual signal, no full fill)
    accent_html = ''
    if cell['items']:
        primary = cell['items'][0]
        pc = PILLAR_COLORS.get(primary['pillar_key'], PILLAR_COLORS['other'])
        accent_html = f'<div class="cell-accent" style="background:{pc["accent"]};"></div>'

    header_parts = [
        f'<div class="num">{cell["day_num"]}</div>',
        f'<div class="heb">{html.escape(cell["heb_short"])}</div>',
    ]
    if cell['holiday']:
        header_parts.append(f'<div class="hol">{html.escape(cell["holiday"])}</div>')

    body_parts = []
    for it in cell['items']:
        pc = PILLAR_COLORS.get(it['pillar_key'], PILLAR_COLORS['other'])
        status_color = STATUS_COLORS.get(it['status'], '#94A3B8')
        title = html.escape(it['title'])
        pillar_label = html.escape(pc['label'])
        pillar_short = html.escape(pc.get('short', pc['label']))
        body_parts.append(f'''
        <div class="item" data-num="{it['num']}">
          <div class="item-top">
            <span class="pill" style="background:{pc['chip_bg']}; color:{pc['accent']}; border:1px solid {pc['accent']}40;" title="{pillar_label}">{pillar_short}</span>
            <span class="status-dot" style="background:{status_color}; box-shadow:0 0 0 2px rgba(255,255,255,0.06), 0 0 8px {status_color}80;" title="{html.escape(it['status'])}"></span>
          </div>
          <div class="item-title">{title}</div>
        </div>''')

    return f'''<div class="{' '.join(classes)}">
      {accent_html}
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
    """Status-only legend. Pillars are self-explanatory via cell chips."""
    status_chips = ''.join(
        f'<span class="legend-chip"><span class="sw round" style="background:{c}; box-shadow:0 0 0 2px rgba(255,255,255,0.06), 0 0 6px {c}80;"></span>{html.escape(s)}</span>'
        for s, c in STATUS_COLORS.items()
    )
    return f'''
    <div class="legend">
      <span class="legend-label">סטטוס</span>
      {status_chips}
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
            'pillar_accent': pcolor['accent'],
            'pillar_chip_bg': pcolor['chip_bg'],
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
  /* Dark mode palette - slate scale */
  --bg: #0B1220;            /* page background, near-black navy */
  --paper: #111827;         /* card surface */
  --paper-2: #1E293B;       /* cell surface */
  --paper-3: #0A1929;       /* weekend cell - friday, darker tone */
  --paper-4: #1B2540;       /* saturday cell - slate-blue tinted, more contrast */
  --ink: #E2E8F0;           /* primary text */
  --ink-soft: #94A3B8;      /* secondary text */
  --ink-faint: #475569;     /* outside cell text */
  --border: #1F2A3B;        /* card borders */
  --border-soft: #1A2332;   /* subtle dividers */
  --accent: #F8FAFC;        /* titles / strong text */
  --gold: #FBBF24;          /* holiday accent */
  --shadow: 0 1px 2px rgba(0,0,0,0.4), 0 4px 14px rgba(0,0,0,0.3);
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
  padding: 22px 28px;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow);
  margin-bottom: 22px;
}
.header-brand {
  display: flex;
  align-items: center;
  /* Logo is dark-on-transparent (designed for light bg).
     invert(1) flips black→white; hue-rotate(180) returns cyan to cyan. */
  filter: invert(1) hue-rotate(180deg) brightness(1.05);
}
.header img.logo {
  height: 56px;
  width: auto;
  display: block;
}
.header-titles {
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.header-titles h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.015em;
  line-height: 1.1;
}
.header-titles .period {
  font-size: 15px;
  color: var(--ink-soft);
  font-weight: 500;
}
.header-titles .count-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
}
.header-titles .count-pill {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
  padding: 3px 10px;
  background: rgba(56,189,248,0.12);
  border: 1px solid rgba(56,189,248,0.25);
  border-radius: 999px;
}
.header-titles .hint {
  font-size: 11px;
  color: var(--ink-soft);
  letter-spacing: 0.01em;
}

/* LEGEND - status only, compact */
.legend {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 18px;
  align-items: center;
  padding: 10px 18px;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 999px;
  margin-bottom: 22px;
}
.legend-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-soft);
  letter-spacing: 0.05em;
  padding: 2px 8px;
  background: rgba(148,163,184,0.08);
  border-radius: 10px;
}
.legend-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--ink);
}
.legend-chip .sw.round {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}

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
  background: var(--paper-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  min-height: 116px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
  transition: transform 0.12s ease, border-color 0.12s ease;
}
.cell:hover { border-color: rgba(148,163,184,0.3); }
.cell.friday {
  background: var(--paper-3);
  border-color: rgba(251,191,36,0.12);
}
.cell.saturday {
  background: var(--paper-4);
  border-color: rgba(251,191,36,0.2);
}
.cell.saturday::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(251,191,36,0.04), transparent 50%);
  pointer-events: none;
  border-radius: 8px;
}
.cell.outside {
  background: transparent;
  border-color: var(--border-soft);
}
.cell.outside .cell-head { opacity: 0.35; }
.cell.outside .cell-body { display: none; }
.cell.outside .cell-head .num { color: var(--ink-faint); }
.cell.outside .cell-head .heb { color: var(--ink-faint); }

/* Holiday: subtle gold corner mark (right edge in RTL) */
.cell.holiday::before {
  content: '';
  position: absolute;
  top: 0; right: 0;
  width: 0; height: 0;
  border-style: solid;
  border-width: 14px 14px 0 0;
  border-color: var(--gold) transparent transparent transparent;
  opacity: 0.85;
  pointer-events: none;
}

/* Pillar accent line on top edge */
.cell-accent {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  border-radius: 8px 8px 0 0;
}

.cell-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
  padding-bottom: 6px;
  margin-top: 2px;
  border-bottom: 1px solid var(--border-soft);
  min-height: 32px;
}
.cell-head .num {
  font-size: 17px;
  font-weight: 700;
  color: var(--accent);
  line-height: 1;
  letter-spacing: -0.01em;
}
.cell-head .heb {
  font-size: 10.5px;
  color: var(--ink-soft);
  font-weight: 500;
  line-height: 1.2;
}
.cell-head .hol {
  width: 100%;
  font-size: 10px;
  font-weight: 600;
  color: var(--gold);
  margin-top: 2px;
  letter-spacing: 0.02em;
}

.cell-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  padding-top: 2px;
}

/* ITEM CHIP */
.item {
  background: rgba(255,255,255,0.025);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  padding: 5px 7px;
  cursor: pointer;
  transition: all 0.12s ease;
}
.item:hover {
  background: rgba(255,255,255,0.06);
  border-color: rgba(148,163,184,0.3);
  transform: translateY(-1px);
}
.item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 3px;
}
.item-top .pill {
  font-size: 9.5px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 10px;
  letter-spacing: 0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: calc(100% - 18px);
}
.item-top .status-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  flex-shrink: 0;
}
.item-title {
  font-size: 11.5px;
  font-weight: 500;
  color: var(--ink);
  line-height: 1.3;
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
  padding: 3px 10px;
  border-radius: 12px;
  display: inline-block;
  margin-bottom: 10px;
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
  background: rgba(148,163,184,0.1);
  border: 1px solid var(--border);
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
  transition: all 0.15s ease;
}
.modal-close:hover { background: rgba(148,163,184,0.2); color: var(--ink); }

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
  background: var(--paper-2);
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
        <span class="modal-pill" style="background:${it.pillar_chip_bg}; color:${it.pillar_accent}; border:1px solid ${it.pillar_accent}40;">${it.pillar_label}</span>
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
    <div class="header-brand">
      {logo_tag}
    </div>
    <div class="header-titles">
      <h1>{html.escape(client)}</h1>
      <div class="period">גאנט {html.escape(period)}</div>
      <div class="count-row">
        <span class="count-pill">{count} תכנים</span>
        <span class="hint">לחץ על תא לפרטים</span>
      </div>
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
