#!/usr/bin/env python3
"""
London Index (@london-index.bsky.social) — daily weather forecast card.

A standalone companion to london_index_post.py, posting once a day regardless
of the main index's own selection: today's forecast for London from the Met
Office's own Weather DataHub (Site Specific daily forecast) — the UK's
national weather service's own published figures, the same standing KMA's
getVilageFcst has for Seoul Index's own seoul_weather_post.py. This is the
account's first FORECAST card: every other vein here states a figure as
published or observed, and a forecast is a prediction by definition — the
footnote below says so plainly, same as Seoul's.

Unlike Seoul's card there is no bilingual thread (London Index posts English
only, matching every other vein on this account) and no base-time lookup:
DataHub's site-specific forecast is continuously updated rather than
published at fixed run times, so this simply fetches fresh on every run.

Sunrise/sunset come from the `astral` package (a local, offline NOAA-formula
calculation), not a second API — Met Office's daily forecast carries no sun
times at all (confirmed against the DataHub schema before writing this), and
unlike KMA's forecast there is no equivalent easy official UK sun-times API
to register for. Sunrise/sunset are physics, not a disputed published figure,
so a local calculation is the simplest correct answer rather than a second
network dependency.

⚠️ The Met Office field names and the weather-code table below were assembled
from several independently-verified sources (a maintained Home Assistant
integration using the same data.hub.api.metoffice.gov.uk host, and a typed
C# client's field constants) rather than official Met Office prose docs,
which don't publish the schema in fetchable form. They have NOT been checked
against a live response — that needs a real API key, which this account did
not yet have when this was written. Treat the first real --dry-run as the
actual verification, and read its printed fields before trusting the card.

Requires (for actual posting, not --dry-run):
  - a Met Office Weather DataHub account (free tier, registered by hand —
    see the README instructions this was built alongside) subscribed to the
    Site Specific Forecast API, with its API key in the Keychain:
      security add-generic-password -a "london-index" -s "metoffice-datahub-key" -w "<key>"
  - the bot's Bluesky app password in the Keychain, exactly as
    london_index_post.py already requires it (service "londonindex-bluesky")

Usage:
  python3 london_weather_post.py            # post today's forecast card
  python3 london_weather_post.py --dry-run  # fetch, build, print — no post
"""

import fcntl
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import london_index_card as card
from london_index_harvest import curl
from london_index_post import HANDLE, KEYCHAIN_SERVICE, MAX_POST_CHARS, keychain_password, write_json_atomic

HERE = Path(__file__).parent
# One JSONL line per posted card, mirroring card_history.jsonl's convention:
# best-effort, written only on a real post, never fatal if it fails.
WEATHER_LOG = HERE / 'weather_history.jsonl'
LOCK = HERE / '.weather.lock'

MET_OFFICE_KEYCHAIN_SERVICE = 'metoffice-datahub-key'
DATAHUB_URL = 'https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily'
# Trafalgar Square — already the reference point london_index_harvest.py uses
# for the Met Police crime-data vein (_latest_police_month), so this is the
# same "London" the rest of the account already means by that word.
LAT, LON = 51.5074, -0.1278
LONDON_TZ = ZoneInfo('Europe/London')

# The full Met Office DataPoint/DataHub significant-weather-code table
# (0-30), verified against a maintained Home Assistant DataHub integration's
# CONDITION_MAP and an independent typed C# client's WEATHER_CODES — the two
# agree exactly. daySignificantWeatherCode should only ever carry a "(day)"
# or date-agnostic code in practice; the night-only entries are kept for
# completeness rather than left to raise a KeyError on a schema surprise.
WEATHER_TEXT = {
    0: 'Clear', 1: 'Sunny', 2: 'Partly cloudy', 3: 'Partly cloudy',
    4: 'Not used', 5: 'Mist', 6: 'Fog', 7: 'Cloudy', 8: 'Overcast',
    9: 'Light rain showers', 10: 'Light rain showers', 11: 'Drizzle',
    12: 'Light rain', 13: 'Heavy rain showers', 14: 'Heavy rain showers',
    15: 'Heavy rain', 16: 'Sleet showers', 17: 'Sleet showers', 18: 'Sleet',
    19: 'Hail showers', 20: 'Hail showers', 21: 'Hail',
    22: 'Light snow showers', 23: 'Light snow showers', 24: 'Light snow',
    25: 'Heavy snow showers', 26: 'Heavy snow showers', 27: 'Heavy snow',
    28: 'Thunder showers', 29: 'Thunder showers', 30: 'Thunder',
}
WEATHER_EMOJI = {
    0: '🌌', 1: '☀️', 2: '☁️', 3: '⛅', 4: '', 5: '🌫️', 6: '🌫️', 7: '☁️',
    8: '☁️', 9: '🌧️', 10: '🌦️', 11: '🌧️', 12: '🌧️', 13: '🌧️', 14: '🌧️',
    15: '🌧️', 16: '🌨️', 17: '🌨️', 18: '🌨️', 19: '🌨️', 20: '🌨️', 21: '🌨️',
    22: '❄️', 23: '❄️', 24: '❄️', 25: '❄️', 26: '❄️', 27: '❄️',
    28: '🌩️', 29: '🌩️', 30: '🌩️',
}
# A code whose own text already names an active precipitation type — the
# rain-chance percentage is folded into these descriptions differently (see
# build_card_lines) than for a plain sky reading like "Cloudy".
WET_CODES = {9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24,
             25, 26, 27, 28, 29, 30}

# WHO/Met Office UV Index advisory bands — a standard published scale, not
# this account's own judgement call.
UV_BANDS = ((0, 'Low'), (3, 'Moderate'), (6, 'High'), (8, 'Very high'), (11, 'Extreme'))


def uv_band(uv):
    band = UV_BANDS[0][1]
    for threshold, label in UV_BANDS:
        if uv >= threshold:
            band = label
    return band


def fmt_c(celsius):
    """31.4 -> '31°C' — Celsius only, no Fahrenheit: this account keeps full
    British convention (see CLAUDE.md), and UK weather reporting (BBC, the
    Met Office's own site) is Celsius-only, unlike Seoul Index's English
    card, which pairs both units for a mixed international audience."""
    return f'{round(celsius)}°C'


def format_ampm(hour, minute):
    """(5, 0) -> '5 a.m.'; (18, 56) -> '6:56 p.m.' — house style is always
    a.m./p.m., lowercase, with periods; never a bare 24-hour clock."""
    period = 'a.m.' if hour < 12 else 'p.m.'
    hour_12 = hour % 12 or 12
    return f'{hour_12} {period}' if minute == 0 else f'{hour_12}:{minute:02d} {period}'


def keychain_metoffice_key():
    r = subprocess.run(
        ['security', 'find-generic-password', '-a', 'london-index',
         '-s', MET_OFFICE_KEYCHAIN_SERVICE, '-w'],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def fetch_daily_forecast(api_key, lat=LAT, lon=LON, timeout=25):
    """Raw list of daily timeSeries entries from DataHub, or None on any
    failure — the caller decides whether that is worth aborting the post
    over. A single `apikey` header, confirmed against a maintained Home
    Assistant DataHub integration that uses the same host."""
    url = (f'{DATAHUB_URL}?latitude={lat}&longitude={lon}'
           f'&excludeParameterMetadata=true&includeLocationName=true')
    result = subprocess.run(
        ['curl', '-sS', '--max-time', str(timeout), '-H', f'apikey: {api_key}', url],
        capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        data = json.loads(result.stdout)
    except ValueError:
        return None
    try:
        return data['features'][0]['properties']['timeSeries']
    except (KeyError, IndexError, TypeError):
        return None


def todays_entry(time_series, target_date):
    """The one daily timeSeries entry whose own 'time' falls on target_date
    (a date object) — or None if the response doesn't carry it, which must
    never crash the post over a schema surprise."""
    for entry in time_series or []:
        t = entry.get('time', '')
        if t[:10] == target_date.isoformat():
            return entry
    return None


def sun_times(target_date):
    """(sunrise_str, sunset_str) for London on target_date, both already
    house-style formatted — a local astral calculation, not a network call.
    See the module docstring for why this isn't a second API."""
    from astral import LocationInfo
    from astral.sun import sun
    loc = LocationInfo('London', 'England', 'Europe/London', LAT, LON)
    s = sun(loc.observer, date=target_date, tzinfo=LONDON_TZ)
    sunrise, sunset = s['sunrise'], s['sunset']
    return (format_ampm(sunrise.hour, sunrise.minute),
            format_ampm(sunset.hour, sunset.minute))


def conditions_text(code, pop):
    """Combine daySignificantWeatherCode and dayProbabilityOfPrecipitation
    into one row's worth of text — matching seoul_weather_post.py's own
    "Conditions" row, which folds sky and rain chance together rather than
    splitting them into two lines. Met Office's single code already names an
    active precipitation type where one exists (Met Office has no separate
    sky/precipitation-type split the way KMA's SKY/PTY do), so a wet code's
    own description is never overwritten — only a plain-sky reading gets the
    "with a chance of rain" wording appended."""
    text = WEATHER_TEXT.get(code, '')
    if not text or text == 'Not used':
        return f'{pop}% chance of rain' if pop is not None else ''
    if pop is None:
        return text
    if code in WET_CODES:
        return f'{text}, {pop}% chance of rain'
    return f'{text} with a {pop}% chance of rain'


def build_card_lines(entry, sunrise=None, sunset=None):
    """(opener, lines, footnote) from one daily timeSeries entry's dict.
    Card text only — dateline and posting are the caller's job. Any field
    Met Office's response doesn't carry is simply omitted from the card
    rather than guessed at, matching the house rule this whole codebase
    follows for a best-effort reading.

    Per-row emoji and the merged sunrise/sunset row match Seoul Index's own
    weather card exactly (seoul_weather_post.py's build_card_lines) — his
    call, 5 September 2026, pointing at a live Seoul post as the reference.
    That includes the row's dropped dotted leader: a leader between "Sunrise
    6:19 a.m." and "🌙 Sunset 7:37 p.m." would read as "here's the value for
    Sunrise", which misdescribes a row whose right side is a second,
    unrelated reading rather than the left label's own figure — the same
    fix applied to Seoul's card the same day, not just copied from it."""
    code = entry.get('daySignificantWeatherCode')
    pop = entry.get('dayProbabilityOfPrecipitation')
    hi = entry.get('dayMaxScreenTemperature')
    lo = entry.get('nightMinScreenTemperature')
    uv = entry.get('maxUvIndex')
    humidity = entry.get('middayRelativeHumidity')

    lines = []
    if hi is not None:
        lines.append({'emoji': '🔺', 'label': 'High', 'value': fmt_c(hi)})
    if lo is not None:
        lines.append({'emoji': '🔻', 'label': 'Low', 'value': fmt_c(lo)})
    cond = conditions_text(code, pop)
    if cond:
        cond_emoji = WEATHER_EMOJI.get(code, '') if code is not None else ''
        lines.append({'emoji': cond_emoji, 'label': 'Conditions', 'value': cond})
    if uv is not None:
        lines.append({'emoji': '🔆', 'label': 'UV index',
                      'value': f'{round(uv)} ({uv_band(uv)})'})
    if humidity is not None:
        lines.append({'emoji': '💧', 'label': 'Humidity', 'value': f'{round(humidity)}%'})
    if sunrise and sunset:
        lines.append({'emoji': '☀️', 'label': f'Sunrise {sunrise}', 'emph': sunrise,
                      'value_lead': '🌙 Sunset ', 'value': sunset, 'no_leader': True,
                      'alt': f'Sunrise {sunrise}, Sunset {sunset}'})

    emoji = WEATHER_EMOJI.get(code, '') if code is not None else ''
    opener = {'emoji': emoji, 'text': "London's forecast for today"}
    footnote = "Met Office's forecast: not an observed reading"
    return opener, lines, footnote


def build_alt(opener, lines, footnote):
    """Plain-text rendering of one card's content, for its image ALT text —
    matching london_index_card.py's own label/value convention. A line
    carrying its own 'alt' (the merged sunrise/sunset row) uses that instead
    of the default "{label}: {value}" template, which would otherwise print
    the sunset reading with no word saying what it is."""
    parts = [card.curly(f"{opener['emoji']} {opener['text']}".strip())]
    for l in lines:
        if 'alt' in l:
            parts.append(card.curly(l['alt']))
        else:
            parts.append(card.curly(f"{l['label']}: {l['value']}"))
    if footnote:
        parts.append(card.curly(footnote))
    return '\n'.join(parts)


def already_posted(target_date):
    """True if WEATHER_LOG already holds a successful post for target_date
    (an ISO 'YYYY-MM-DD' string) — what makes the safety-net launchd fire
    safe to add alongside the primary one, matching Seoul Index's own
    weather job exactly (see com.chrisstanford.seoulweather.plist)."""
    if not WEATHER_LOG.exists():
        return False
    with open(WEATHER_LOG) as f:
        for line in f:
            try:
                if json.loads(line).get('target_date') == target_date:
                    return True
            except json.JSONDecodeError:
                continue
    return False


def main():
    lock = open(LOCK, 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit('Another london_weather_post run is in progress; bowing out.')

    now = datetime.now(LONDON_TZ)
    print(f'--- run at {now:%Y-%m-%d %H:%M:%S} {now:%Z} ---')

    target_date = now.date()
    target_str = target_date.isoformat()
    dry_run = '--dry-run' in sys.argv
    if not dry_run and already_posted(target_str):
        print(f'Already posted for {target_str}; nothing to do '
              f'(safety-net rerun after an earlier success).')
        return

    api_key = keychain_metoffice_key()
    if not api_key:
        sys.exit(f'No Keychain password for account="london-index" '
                 f'service="{MET_OFFICE_KEYCHAIN_SERVICE}".\n'
                 f'Add it with:\n'
                 f'  security add-generic-password -a "london-index" '
                 f'-s "{MET_OFFICE_KEYCHAIN_SERVICE}" -w "<key>"')

    time_series = fetch_daily_forecast(api_key)
    if time_series is None:
        sys.exit('Met Office DataHub daily forecast call failed.')
    entry = todays_entry(time_series, target_date)
    if entry is None:
        sys.exit(f'No forecast entry for {target_str} in the DataHub response '
                 f'— schema may have changed.')
    print(f'Raw entry for {target_str}: {json.dumps(entry, indent=2)}')

    sunrise, sunset = sun_times(target_date)
    opener, lines, footnote = build_card_lines(entry, sunrise, sunset)
    if not lines:
        sys.exit('No usable fields in the forecast entry; nothing to post.')

    dateline = f'{now:%-d %B %Y}'
    alt = build_alt(opener, lines, footnote)
    print(f"\n{opener['emoji']} {opener['text']}")
    for l in lines:
        print(f"  {l['label']}: {l['value']}")
    print(f'  ({footnote})')
    print(f'\nAlt ({len(alt)} chars):\n{"-"*46}\n{alt}\n{"-"*46}')

    fallback = False
    try:
        out_path, size = card.render_card(opener, lines, HERE / 'weather_card.png',
                                          footnote=footnote, dateline=dateline)
        image_bytes = Path(out_path).read_bytes()
    except card.CardRenderError as e:
        print(f'Card render failed ({e}); falling back to plaintext.', file=sys.stderr)
        fallback = True
        image_bytes = None
        size = None

    if dry_run:
        if not fallback:
            print(f'\n(dry run — wrote {out_path} at {size[0]}x{size[1]}, not posting)')
        else:
            print('\n(dry run — not posting)')
        return

    password = keychain_password(HANDLE, KEYCHAIN_SERVICE)
    from atproto import Client, client_utils, models
    bsky = Client()
    bsky.login(HANDLE, password)

    if not fallback:
        ar = models.AppBskyEmbedDefs.AspectRatio(width=size[0], height=size[1])
        p1 = bsky.send_image(text='', image=image_bytes, image_alt=alt,
                             langs=['en'], image_aspect_ratio=ar)
        root_ref = models.create_strong_ref(p1)
        tb = client_utils.TextBuilder()
        tb.link('Met Office', 'https://www.metoffice.gov.uk')
        bsky.send_post(text=tb, reply_to=models.AppBskyFeedPost.ReplyRef(
            parent=root_ref, root=root_ref), langs=['en'])
        print('\nPosted (2-post thread: card, source reply).')
    else:
        body = f"{opener['text']}\n" + '\n'.join(f"{l['label']}: {l['value']}" for l in lines)
        body += f'\nSource: Met Office'
        if len(body) > MAX_POST_CHARS:
            sys.exit(f'Plaintext-fallback post too long ({len(body)} chars, max {MAX_POST_CHARS}).')
        p1 = bsky.send_post(text=body, langs=['en'])
        print('\nPosted (plaintext fallback, render failed).')

    try:
        with open(WEATHER_LOG, 'a') as f:
            f.write(json.dumps({
                'posted_at': now.isoformat(), 'target_date': target_str,
                'high': entry.get('dayMaxScreenTemperature'),
                'low': entry.get('nightMinScreenTemperature'),
                'code': entry.get('daySignificantWeatherCode'),
                'uri': p1.uri,
            }) + '\n')
    except OSError:
        pass  # best-effort — the post is already out


if __name__ == '__main__':
    main()
