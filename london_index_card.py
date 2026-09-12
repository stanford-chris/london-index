#!/usr/bin/env python3
"""
Card renderer for London Index (@london-index.bsky.social).

Renders one post's index as a monospace "markdown on cream" PNG card, matching
the account avatar's cream background and Underground-roundel navy
(`#00247d`). Headless Google Chrome does the type/emoji layout so colour
emoji Just Work via system fonts; Pillow crops the result to the content, the
same sentinel-background trick Seoul Index's renderer uses so a 3-line and a
5-line card both come out tight with no guessed height.

Visual design fixed by the agreed mockup (`sample_card_1.html`): a dateline,
a bold opener (its emoji the only one on the card — repeating it on every
line below read as cluttered and was dropped), one row per line (label,
dotted leader, right-aligned bold value), then a muted footnote — no rule
above the handle, dropped 30 August 2026 as an unwanted divider.
Unlike Seoul Index's card, the footnote here is reserved for a genuine
caveat on the numbers ("Annual figures, not live") rather than the source
name or hashtags — the source stays real, clickable text in the reply post,
and hashtags ride the card post's own caption, following the lesson Seoul
Index's own docstring states plainly: neither belongs baked into an image.

Public API:
    render_card(opener, lines, out_path, footnote="", dateline="")
        opener:   {"emoji": "🚇" or "", "text": "London on the move right now"}
        lines:    [{"label": "Busiest station: Euston",
                    "value": "11% of typical"}, ...]
                  {"emoji": "🔺"} adds a leading emoji to that one row — the
                  index card's own veins never set this (the opener carries
                  the card's only emoji there, deliberately, per the design
                  note below), but a data-dense card like the weather one
                  uses a per-row icon the way Seoul Index's own renderer
                  does, and this is that same mechanism copied across.
                  {"value_lead": "🌙 Sunset "} prints that text in REGULAR
                  weight immediately before the (still bold) value, and
                  {"no_leader": True} drops the dotted leader for that row —
                  both matching seoul_index_card.py exactly, for a row like
                  sunrise/sunset that packs a second label+value pair into
                  the value slot rather than stating one figure for its own
                  label.
        footnote: a caveat on the numbers, or "" for none
        dateline: the date this card was posted, shown under the title — a
                  bare date, or "29 August at 11:53" when any of the picks
                  is a live "right now" reading with no timestamp of its own

Raises CardRenderError on any failure so the poster can fall back to plaintext.
"""

import math
import re
import subprocess
import tempfile
from pathlib import Path

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
SENTINEL = 'FF00FF'          # page background; cropped away. Never appears in art.
SENTINEL_RGB = (255, 0, 255)
CARD_WIDTH = 860             # CSS px, widened from 680 (sample_card_1.html) to 820 for the
                              # crowding vein's longest label + value ("Busiest: King's Cross St
                              # Pancras" at "31% of baseline"), then to 860 on 31 August 2026 when
                              # river_levels' "% of range" fix (see harvest.py's _val()) pushed its
                              # own longest line ("Driest: Ravensbourne at Catford" at "0.072m (0%
                              # of range)") past 820 and it silently wrapped to two lines — 820 was
                              # measured against crowding's worst case only, never re-checked
                              # against river's after a later change to river's value format. Every
                              # entry must stay single-line, so labels were also shortened where
                              # they could be (river labels dropped "river" and their range bounds).
                              # Device-scale 2 renders at 1720px.
RENDER_HEIGHT = 1000         # generous CSS height; cropped to content after.
CREAM = '#f5f0e6'
INK = '#00247d'              # Underground-roundel navy, matching the avatar.
RED = '#d70000'              # the site's AA red, for the town-hall dot and circle
FONT_STACK = "'SF Mono', 'Menlo', 'Consolas', monospace"


class CardRenderError(RuntimeError):
    """Rendering failed — caller should fall back to a plaintext post."""


def curly(s):
    """Typographer's quotes: straight ' and " become curly. Applied to every
    piece of card text via _esc, matching Seoul Index's own curly() exactly —
    so it holds no matter where the text came from (a hardcoded label or the
    claude -p selector's own opener wording), rather than relying on every
    caller to have typed a curly mark by hand."""
    if not s:
        return s or ''
    s = re.sub(r"(?<=\w)'(?=\w)", '’', s)   # contractions: King’s
    s = re.sub(r"'(?=\d\d)", '’', s)        # decade elision: '90s
    s = re.sub(r"(?<=\w)'", '’', s)         # trailing possessive: rivers'
    s = re.sub(r"'(?=\S)", '‘', s)          # opening single quote
    s = s.replace("'", '’')                 # anything left closes
    s = re.sub(r'(?<=\S)"(?=[\s.,;:!?)\]]|$)', '”', s)  # closing double
    s = re.sub(r'"(?=\S)', '“', s)          # opening double
    s = s.replace('"', '”')
    return s


def _esc(s):
    import html
    return html.escape(curly(str(s)), quote=True)


def _line_html(line):
    if 'subhead' in line:
        return f'<div class="sub">{_esc(line["subhead"])}</div>'
    emoji = line.get('emoji') or ''
    lead = f'{_esc(emoji)} ' if emoji else ''
    lab = _esc(line['label'])
    emph = line.get('emph')
    if emph:
        # Bolds just the run named by 'emph' inside an otherwise-regular
        # label — e.g. the time inside "Sunrise 6:05 a.m." — same rule as
        # seoul_index_card.py's _row_html. A miss is silently fine: the run
        # is matched as a plain substring on the escaped label, and if it
        # is not there the label just renders unbolded.
        run = _esc(emph)
        if run:
            lab = lab.replace(run, f'<b>{run}</b>', 1)
    val_lead = line.get('value_lead') or ''
    val_lead_html = f'<span class="valreg">{_esc(val_lead)}</span>' if val_lead else ''
    leader_class = 'leader plain' if line.get('no_leader') else 'leader'
    return (f'<div class="line"><span class="label">{lead}{lab}</span>'
            f'<span class="{leader_class}"></span>'
            f'<span class="value">{val_lead_html}{_esc(line["value"])}</span></div>')


HANDLE_WATERMARK = '@london-index.bsky.social'


def _build_html(opener, lines, footnote='', dateline=''):
    op_emoji = opener.get('emoji') or ''
    op_lead = f'{_esc(op_emoji)} ' if op_emoji else ''
    rows = ''.join(_line_html(l) for l in lines)
    dl = f'<div class="dateline">{_esc(dateline)}</div>' if dateline else ''
    foot = f'<div class="footnote">{_esc(footnote)}</div>' if footnote else ''
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body {{ margin:0; background:#{SENTINEL}; }}
  .card {{
    width:{CARD_WIDTH}px; padding:44px 48px 36px;
    font-family:{FONT_STACK};
    background:{CREAM}; color:{INK}; box-sizing:border-box;
  }}
  .opener {{ font-size:26px; font-weight:700; margin-bottom:6px; color:#000; }}
  .opener .md {{ color:{INK}; }}
  .line {{ display:flex; align-items:baseline; gap:14px; font-size:22px; margin-bottom:14px; }}
  .label {{ flex:0 1 auto; }}
  .leader {{ flex:1 0 24px; border-bottom:2px dotted {INK}66; margin:0 2px; }}
  .leader.plain {{ border-bottom:none; }}
  .value {{ font-weight:700; white-space:nowrap; }}
  .value .valreg {{ font-weight:400; }}
  .sub {{ font-size:15px; font-weight:700; letter-spacing:.02em; color:{INK}; margin:22px 0 10px; }}
  .footer {{ margin-top:24px; }}
  .footnote {{ font-size:15px; color:{INK}99; margin-bottom:6px; }}
  .handle {{ font-size:13px; color:{INK}99; letter-spacing:.04em; margin-top:16px; }}
  .dateline {{ font-size:15px; font-weight:700; letter-spacing:.02em; color:{INK}; margin-bottom:22px; }}
</style></head>
<body>
  <div class="card">
    <div class="opener"><span class="md">##</span> {op_lead}{_esc(opener['text'])}</div>
    {dl}
    {rows}
    <div class="footer">
      {foot}
      <div class="handle">{_esc(HANDLE_WATERMARK)}</div>
    </div>
  </div>
</body></html>"""


def _crop_to_content(raw_path, out_path):
    try:
        from PIL import Image, ImageChops
    except ImportError as e:
        raise CardRenderError(f'Pillow not available: {e}')
    with Image.open(raw_path) as im:
        im = im.convert('RGB')
        bg = Image.new('RGB', im.size, SENTINEL_RGB)
        bbox = ImageChops.difference(im, bg).getbbox()
        if not bbox:
            raise CardRenderError('rendered image was entirely background')
        cropped = im.crop(bbox)
        cropped.save(out_path)
        size = cropped.size
    return out_path, size


def _shoot(doc, out_path, width=CARD_WIDTH):
    """Render an HTML doc to a content-cropped PNG. Returns (out_path, (w, h))."""
    if not Path(CHROME).exists():
        raise CardRenderError(f'Chrome not found at {CHROME}')
    out_path = str(out_path)
    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / 'card.html'
        raw_png = Path(td) / 'raw.png'
        html_path.write_text(doc, encoding='utf-8')
        cmd = [
            CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars',
            '--force-device-scale-factor=2',
            f'--window-size={width},{RENDER_HEIGHT}',
            f'--default-background-color={SENTINEL}FF',
            f'--screenshot={raw_png}', f'file://{html_path}',
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if not raw_png.exists():
            raise CardRenderError(
                f'Chrome produced no image (exit {r.returncode}): '
                f'{(r.stderr or r.stdout or "").strip()[:200]}')
        _, size = _crop_to_content(raw_png, out_path)
    return out_path, size


MAP_SIZE = 860   # width in CSS px, the card's own; height follows London's shape
MUTED = '#8a93b8'
BOROUGHS_GEOJSON = Path(__file__).parent / 'data' / 'london_boroughs.geojson'
MILE_M = 1609.344
M_PER_DEG_LAT = 111_320


def load_boroughs(path=BOROUGHS_GEOJSON):
    """name -> list of rings, each a list of (lon, lat). ONS Local Authority
    Districts (December 2024) Boundaries UK BGC, the 33 E09 codes, fetched
    from the Open Geography Portal's FeatureServer as WGS84 GeoJSON on
    12 September 2026 and committed, so no post depends on a live fetch.
    Licence: Open Government Licence v3.0; "Contains OS data © Crown
    copyright and database right 2024", which the map reply states."""
    import json
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    out = {}
    for f in d['features']:
        g = f['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        rings = []
        for poly in polys:
            for ring in poly:            # outer ring and any holes, all drawn
                rings.append([(float(x), float(y)) for x, y in ring])
        out[f['properties']['LAD24NM']] = rings
    return out


def render_borough_map(highlight, town_hall, out_path, title='', caption='', boroughs=None):
    """Greater London's 33 boroughs in outline, `highlight` filled, its town
    hall dotted and a one-mile circle around it: the threaded reply for the
    spotlight card, and the honest picture of what "within a mile of the
    town hall" covers. Chris's call, 12 September 2026. No basemap, no
    tiles: the outlines are the map. `town_hall` is (lat, lng), as the
    harvester stores it. Raises CardRenderError for a borough name the
    boundary file does not carry, rather than drawing a map with nothing
    highlighted."""
    boroughs = boroughs or load_boroughs()
    if highlight not in boroughs:
        raise CardRenderError(f'{highlight!r} is not in the borough boundary file')
    # Landscape, fitted to the city: London is wider than it is tall, and a
    # square frame left a third of the canvas empty above and below it on
    # the first render. Width is fixed; height follows the outlines, plus
    # room for the title above and the caption below.
    width = MAP_SIZE
    pad = width * 0.04
    top, bottom = 56, 44
    pts = [p for rings in boroughs.values() for r in rings for p in r]
    lo0, lo1 = min(p[0] for p in pts), max(p[0] for p in pts)
    la0, la1 = min(p[1] for p in pts), max(p[1] for p in pts)
    k = math.cos(math.radians((la0 + la1) / 2))
    scale = (width - 2 * pad) / ((lo1 - lo0) * k)
    size = int(round((la1 - la0) * scale + 2 * pad + top + bottom))   # the height
    ox = pad
    oy = bottom + pad

    def xy(lon, lat):
        return (ox + (lon - lo0) * k * scale, size - oy - (lat - la0) * scale)

    def path(rings):
        parts = []
        for ring in rings:
            parts.append('M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in (xy(*p) for p in ring)) + 'Z')
        return ''.join(parts)

    body = [f'<path d="{path(rings)}" fill="{INK}" fill-opacity="0.06" stroke="{MUTED}" '
            f'stroke-width="1" fill-rule="evenodd"/>'
            for name, rings in boroughs.items() if name != highlight]
    body.append(f'<path d="{path(boroughs[highlight])}" fill="{INK}" fill-opacity="0.55" '
                f'stroke="{INK}" stroke-width="1.5" fill-rule="evenodd"/>')
    lat, lng = town_hall
    x, y = xy(lng, lat)
    r = MILE_M / M_PER_DEG_LAT * scale   # a degree of latitude is `scale` px
    body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{RED}" fill-opacity="0.18" '
                f'stroke="{RED}" stroke-width="2"/>')
    body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{RED}" stroke="{CREAM}" stroke-width="2"/>')
    title_html = (f'<text x="30" y="34" font-family="Menlo,monospace" font-size="20" '
                  f'font-weight="bold" fill="#000">{_esc(title)}</text>' if title else '')
    caption_html = (f'<text x="30" y="{size - 24}" font-family="Menlo,monospace" '
                    f'font-size="12" fill="{MUTED}">{_esc(caption)}</text>' if caption else '')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{size}" '
           f'viewBox="0 0 {width} {size}">'
           f'<rect width="{width}" height="{size}" fill="{CREAM}"/>'
           f'{"".join(body)}{title_html}{caption_html}</svg>')
    doc = (f'<!doctype html><html><head><meta charset="utf-8"></head>'
           f'<body style="margin:0;background:#{SENTINEL}">{svg}</body></html>')
    return _shoot(doc, out_path, width=width)


def render_card(opener, lines, out_path, footnote='', dateline=''):
    """Render one index card. Returns (path, (w, h))."""
    if not lines:
        raise CardRenderError('no lines to render')
    return _shoot(_build_html(opener, lines, footnote, dateline), out_path)


# Narrower than the index card's 860: that width was widened specifically so a
# long single-line label + value ("Busiest: King's Cross St Pancras" at "31% of
# baseline") never wraps, a constraint wrapped prose doesn't have. Matches
# Seoul Index's own prose-card width (600) closely enough for a shared family
# look without copying its value outright — this card's base font and padding
# differ slightly, and 620 is what reads well against them.
PROSE_CARD_WIDTH = 620


def _prose_paragraph(p):
    return f'<p>{_esc(p)}</p>'


def _build_prose_html(heading, paragraphs, emoji=''):
    lead = f'{_esc(emoji)} ' if emoji else ''
    body = ''.join(_prose_paragraph(p) for p in paragraphs)
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body {{ margin:0; background:#{SENTINEL}; }}
  .card {{
    width:{PROSE_CARD_WIDTH}px; padding:28px 30px; box-sizing:border-box;
    font-family:{FONT_STACK}; background:{CREAM}; color:{INK};
  }}
  .h {{ font-size:17px; font-weight:700; margin-bottom:18px; line-height:1.35; color:#000; }}
  .h .md {{ color:{INK}; }}
  .body {{ font-size:15px; line-height:1.65; }}
  .body p {{ margin:0 0 12px; }}
  .body p:last-child {{ margin-bottom:0; }}
</style></head>
<body>
  <div class="card">
    <div class="h"><span class="md">##</span> {lead}{_esc(heading)}</div>
    <div class="body">{body}</div>
  </div>
</body></html>"""


def render_prose_card(heading, paragraphs, out_path, emoji=''):
    """Render one prose card (heading + wrapped body paragraphs), matching
    Seoul Index's render_prose_card — used only by london_index_methodology.py,
    never by the daily pipeline. Returns (path, (w, h))."""
    if not paragraphs:
        raise CardRenderError('no body text to render')
    return _shoot(_build_prose_html(heading, paragraphs, emoji), out_path, width=PROSE_CARD_WIDTH)


if __name__ == '__main__':
    # Quick manual check against a fixed sample input.
    opener = {'emoji': '🚇', 'text': 'London on the move right now'}
    lines = [
        {'label': 'Busiest station: Euston', 'value': '11% of typical'},
        {'label': 'Quietest: Bank', 'value': '1% of typical'},
        {'label': 'Santander Cycles available now', 'value': '9,504'},
        {'label': 'Docking stations with no bikes', 'value': '84 of 787'},
    ]
    path, size = render_card(opener, lines, 'london_index_card_test.png',
                              dateline='29 August 2026')
    print(f'Rendered {path} at {size[0]}x{size[1]}')
