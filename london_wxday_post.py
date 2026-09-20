#!/usr/bin/env python3
"""
London Index (@london-index.bsky.social) — yesterday's observed weather.

A second standalone weather companion, alongside london_weather_post.py's
forecast card: this one reads yesterday's ACTUAL readings from the Met
Office's own Weather DataHub Land Observations API, the UK national
service's own ground-truth data — the same standing KMA's station-108 daily
row has for Seoul Index's own wxday card in seoul_index_post.py. Where the
forecast card states a prediction, this one states what was measured.

⚠️ THE CARD IS HIGH/LOW ONLY, AND THAT IS THE DATA, NOT A STYLE CHOICE. KMA
hands Seoul a finished daily row carrying high, low, rain, sunshine and
snow. Confirmed against the Land Observations API's own live OpenAPI spec
(pulled from datahub.metoffice.gov.uk on 14 September 2026) and a real
response: its 9 fields are datetime, humidity, mslp, pressure_tendency,
temperature, visibility, weather_code, wind_direction, wind_gust,
wind_speed — 24 hourly points, no daily aggregate, and no rain, sunshine or
snow field at all. His instruction, 14 September 2026, after Conditions,
Humidity and Wind were tried and shown to him: no Conditions line at all;
a Rain line only if a real total could be sourced, which it can't be —
there is no precipitation field anywhere in this API and no forecast
percentage counts as an observed total — so "otherwise high and low are
sufficient" is the whole card. A same-day offer to fill the gap with
Open-Meteo's historical archive (a third-party reanalysis model, not an
observed Met Office reading — the same distinction that already ruled
Open-Meteo out of the forecast card) was explicitly declined. The title
glyph still reflects the day's weather_code (see build_card_lines) even
though no Conditions text is printed — matching Seoul's own wxday card,
which carries a title glyph from wx_day_emoji() with no Conditions row
either.

⚠️ RAIN COMES FROM A SECOND, DIFFERENT AGENCY, ADDED 14 September 2026. His
question ("there's seriously no previous day's rainfall measurement?") sent
this back to check further than Met Office DataHub, and the UK Environment
Agency's real-time flood-monitoring API (environment.data.gov.uk) has one:
real tipping-bucket rain gauges, 15-minute readings, no API key at all. It
is a different UK government body from the Met Office, but a real measured
government reading rather than a model, so it does not carry the objection
that ruled Open-Meteo out of both cards. A Rain line appears ONLY when the
day's total is greater than zero — his own wording, "if there was rain, we
should mention the total, otherwise high and low are sufficient" — so a dry
day shows no Rain row at all, deliberately unlike Seoul's wxday, which
always shows Rain and prints "None" on a dry day.

⚠️⚠️ THE API'S OWN "NEAREST" RESULT CAN 404. Confirmed live, twice, through
two different clients (curl and Met Office's own "Try It" console): querying
/nearest for Trafalgar Square returns a geohash for "Greater London" that
then 404s at /{geohash} — not a schema surprise, a station in their own
nearest-index that currently carries no live data. Asking for 5 candidates
instead of 1, the next four all answer; the nearest that actually works
(nearest_working_geohash, below) decodes to about 20 km northwest of
Trafalgar Square, not central London, still labelled "Greater London" by
Met Office's own area field. So this walks the candidate list and posts
from whichever one actually has data — and the footnote says how far that
station really is, rather than implying a central-London reading the way
"London's weather yesterday" alone would.

The title glyph reuses london_weather_post.py's own WEATHER_EMOJI code
table (0-30) rather than a second copy — the same Met Office
significant-weather-code scheme, and the live observation responses seen
while building this (weather_code 8 = Overcast on an actually-overcast
reading) are consistent with it, though the table itself was assembled for
the forecast product and has not been independently re-verified against
Met Office's own prose docs for the observations one.

The glyph's own code comes from ONE representative hourly reading (midday,
the hour closest to 12:00 Europe/London — Met Office's own convention for
a single representative-of-the-day reading, per the forecast product's own
middayRelativeHumidity field name) rather than all 24. High/Low are the
true max/min across whichever hourly readings yesterday actually has, not
just the midday one.

No bilingual thread (English only, matching every other vein on this
account) and no "latest available" footnote sentence: yesterday is always
exactly one day behind today by construction, which is the threshold this
account's own latest_is_notable()-style rule (see CLAUDE.md, 13 September
2026) already treats as never worth stating — wxday carries the identical
exemption on the Seoul side for the identical reason.

Requires (for actual posting, not --dry-run):
  - a Met Office Weather DataHub account subscribed to the Land
    Observations API (free tier, registered by hand — see the README),
    with its API key in the Keychain, kept separate from the forecast
    card's own key (a different DataHub product/subscription):
      security add-generic-password -a "london-index" -s "metoffice-datahub-land-obs-key" -w "<key>"
  - the bot's Bluesky app password in the Keychain, exactly as
    london_index_post.py already requires it (service "londonindex-bluesky")
  - nothing for the rain figure: the Environment Agency's API is public,
    no registration or key of any kind

Usage:
  python3 london_wxday_post.py            # post yesterday's observed card
  python3 london_wxday_post.py --dry-run  # fetch, build, print — no post
"""

import fcntl
import json
import math
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import london_index_card as card
from london_index_post import HANDLE, KEYCHAIN_SERVICE, MAX_POST_CHARS, keychain_password
from london_weather_post import LAT, LON, LONDON_TZ, WEATHER_EMOJI, fmt_c

HERE = Path(__file__).parent
# Its own log and lock, separate from weather_history.jsonl/.weather.lock —
# two independent daily jobs (forecast, observed) must never share a
# dedup file or a run of one could block or corrupt the other's.
WXDAY_LOG = HERE / 'wxday_history.jsonl'
LOCK = HERE / '.wxday.lock'

MET_OFFICE_LAND_OBS_KEYCHAIN_SERVICE = 'metoffice-datahub-land-obs-key'
OBS_BASE = 'https://data.hub.api.metoffice.gov.uk/observation-land/1'
NEAREST_CANDIDATES = 5  # walk this many before giving up — see module docstring


def keychain_land_obs_key():
    r = subprocess.run(
        ['security', 'find-generic-password', '-a', 'london-index',
         '-s', MET_OFFICE_LAND_OBS_KEYCHAIN_SERVICE, '-w'],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def _curl_json(url, headers=None, timeout=25):
    """None on any failure — curl exit, a non-JSON body, or (documented
    above, for the Met Office side) a 200-shaped API returning a plain-text
    404 body. The caller decides what a None means; this never raises over
    a live service's own quirks. Shared by both agencies this script talks
    to — the Environment Agency's API needs no header at all, unlike Met
    Office's apikey one, so headers is optional.

    ⚠️ -L is load-bearing: the Environment Agency's own station/measure
    @id links are all plain http://, which 301-redirects to https:// —
    confirmed live, 14 September 2026, after a first version silently
    returned the redirect's HTML body instead of readings and every gauge
    read as 'saw no readings' (indistinguishable from an offline station
    until traced). Met Office's URLs are already https and never redirect,
    so -L is a no-op there."""
    cmd = ['curl', '-sSL', '--max-time', str(timeout)]
    for h in headers or []:
        cmd += ['-H', h]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        return None


def _get_json(url, api_key, timeout=25):
    return _curl_json(url, headers=[f'apikey: {api_key}'], timeout=timeout)


def nearest_candidates(api_key, lat=LAT, lon=LON, max_results=NEAREST_CANDIDATES):
    """Up to max_results {geohash, area, ...} dicts nearest to (lat, lon),
    nearest first — or [] on failure. Deliberately plural: see the module
    docstring for why the single nearest result can be unqueryable.

    ⚠️ /nearest refuses more than 2 decimal places ("Invalid latitude or
    longitude provided", confirmed live) — unlike the forecast card's own
    Site Specific API, which accepts LAT/LON's full 4-decimal precision
    without complaint. Rounded here rather than changing the shared
    constants, since the forecast card's own precision is fine where it is
    used."""
    url = f'{OBS_BASE}/nearest?lat={round(lat, 2)}&lon={round(lon, 2)}&max={max_results}'
    data = _get_json(url, api_key)
    return data if isinstance(data, list) else []


def observations_for(geohash, api_key):
    """The raw list of hourly observation dicts for one geohash, or None if
    this particular geohash has no live data (the 404 case) or the call
    otherwise failed. Distinguishing 'this station is dead' from 'nothing
    for the target date yet' is the caller's job, not this one's."""
    data = _get_json(f'{OBS_BASE}/{geohash}', api_key)
    return data if isinstance(data, list) else None


def first_working_station(api_key):
    """Walk nearest_candidates() in order and return (geohash, area, rows)
    for the first one that actually answers with data — or (None, None,
    None) if every candidate is either unqueryable or the call failed
    outright. This is the fix for the 404-nearest-station quirk: never
    trust the top result blindly."""
    candidates = nearest_candidates(api_key)
    if not candidates:
        return None, None, None
    for c in candidates:
        geohash = c.get('geohash')
        if not geohash:
            continue
        rows = observations_for(geohash, api_key)
        if rows:
            return geohash, c.get('area'), rows
    return None, None, None


def _decode_geohash(geohash):
    """Centre (lat, lon) of a geohash cell — a local decode, not a second
    API call. Verified against two known points while building this: the
    docs' own example 'gcj8ds' decodes to ~(50.74, -3.40), Met Office's
    Exeter headquarters in Devon, matching the spec's own 'area': 'Devon'
    example; 'gcpvj0' (the unqueryable nearest-to-Trafalgar-Square result)
    decodes to ~(51.507, -0.126), correctly on top of Trafalgar Square
    itself. A 6-character geohash cell is roughly 1.2 x 0.6 km, which is
    well inside the rounding this is used for (distance to the nearest km)."""
    base32 = '0123456789bcdefghjkmnpqrstuvwxyz'
    lat_range, lon_range = [-90.0, 90.0], [-180.0, 180.0]
    is_lon = True
    for ch in geohash:
        idx = base32.index(ch)
        for bit in range(4, -1, -1):
            bounds = lon_range if is_lon else lat_range
            mid = sum(bounds) / 2
            if (idx >> bit) & 1:
                bounds[0] = mid
            else:
                bounds[1] = mid
            is_lon = not is_lon
    return sum(lat_range) / 2, sum(lon_range) / 2


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def station_distance_km(geohash):
    lat, lon = _decode_geohash(geohash)
    return haversine_km(LAT, LON, lat, lon)


def _iso_to_london(raw):
    """Any UTC, 'Z'-suffixed ISO datetime string as an aware Europe/London
    datetime, or None if missing/unparseable — shared by both agencies'
    readings, since both serve plain UTC timestamps in the same shape."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None
    return dt.astimezone(LONDON_TZ)


def _row_local_dt(row):
    """A Met Office observation row's 'datetime' as Europe/London local —
    a bad row is dropped rather than crashing the whole card over one bad
    reading."""
    return _iso_to_london(row.get('datetime'))


def yesterdays_rows(rows, target_date):
    """Every hourly row whose Europe/London calendar date is target_date —
    filtering happens in local time, not UTC, because a UTC-day filter
    would cut an hour off each end of the London day (Europe/London runs
    UTC+1 for most of the year)."""
    out = []
    for row in rows or []:
        local = _row_local_dt(row)
        if local is not None and local.date() == target_date:
            out.append(row)
    return out


def midday_row(rows):
    """The row whose Europe/London local hour is closest to 12:00 — Met
    Office's own convention for a single representative-of-the-day reading
    (the forecast product's own 'middayRelativeHumidity' field name), used
    here for Conditions/Humidity/Wind. None if rows is empty. Ties (e.g.
    11:00 and 13:00 both an hour away) favour the earlier hour, arbitrarily
    but deterministically."""
    best, best_diff = None, None
    for row in rows:
        local = _row_local_dt(row)
        if local is None:
            continue
        diff = abs(local.hour - 12)
        if best_diff is None or diff < best_diff:
            best, best_diff = row, diff
    return best


EA_STATIONS_URL = 'https://environment.data.gov.uk/flood-monitoring/id/stations'
EA_SEARCH_DIST_KM = 15  # the API's own `dist` query parameter, kilometres
EA_NEAREST_CANDIDATES = 5  # same reasoning as the Met Office side: a nearby
                            # gauge can be silently offline; walk the list


def ea_nearest_rain_gauges(lat=LAT, lon=LON, search_dist_km=EA_SEARCH_DIST_KM,
                            max_results=EA_NEAREST_CANDIDATES):
    """Rainfall-capable stations within search_dist_km of (lat, lon),
    nearest first, each as {station_ref, distance_km, measure_id} — or []
    on failure. The Environment Agency's own API needs no key or header at
    all. Distance is computed here (haversine against the station's own
    lat/long in the response) since the API itself doesn't return one."""
    url = f'{EA_STATIONS_URL}?parameter=rainfall&lat={lat}&long={lon}&dist={search_dist_km}'
    data = _curl_json(url)
    out = []
    for it in (data or {}).get('items', []):
        measure_id = next((m.get('@id') for m in it.get('measures', [])
                           if m.get('parameter') == 'rainfall'), None)
        if not measure_id or 'lat' not in it or 'long' not in it:
            continue
        out.append({'station_ref': it.get('stationReference'),
                    'distance_km': haversine_km(lat, lon, it['lat'], it['long']),
                    'measure_id': measure_id})
    out.sort(key=lambda s: s['distance_km'])
    return out[:max_results]


def ea_readings_for_utc_date(measure_id, utc_date):
    """Raw EA readings ({dateTime, value, ...} dicts) for one measure on
    one UTC calendar date (a date object), or [] on failure. measure_id is
    already the reading's own full URL from the stations response, so this
    just appends the readings path."""
    data = _curl_json(f'{measure_id}/readings?date={utc_date.isoformat()}')
    items = (data or {}).get('items')
    return items if isinstance(items, list) else []


def ea_daily_total_mm(measure_id, target_date):
    """(total_mm, saw_any_reading) for target_date in Europe/London local
    time. Reads BOTH UTC calendar dates the London day can touch (the
    target date and the one before it — the same reasoning as
    yesterdays_rows() for the Met Office feed) and sums whatever 15-minute
    readings actually fall on target_date once converted to local time.

    saw_any_reading distinguishes 'measured, totalled zero' (a genuinely
    dry day) from 'nothing came back at all' (an offline gauge or a failed
    call) — the caller must never print '0.0mm' for the second case, and
    must never print a Rain row at all for a real zero, per his own rule
    that a dry day shows no Rain line."""
    total, saw_any = 0.0, False
    for utc_date in (target_date - timedelta(days=1), target_date):
        for r in ea_readings_for_utc_date(measure_id, utc_date):
            local = _iso_to_london(r.get('dateTime'))
            value = r.get('value')
            if local is None or local.date() != target_date or value is None:
                continue
            saw_any = True
            total += value
    return round(total, 1), saw_any


def first_working_rain_gauge(target_date):
    """Walk ea_nearest_rain_gauges() and return (station_ref, distance_km,
    total_mm) for the first one that actually answered — or (None, None,
    None) if every candidate was silent. A missing rain figure must never
    abort the whole card: High/Low from Met Office stand on their own."""
    for g in ea_nearest_rain_gauges():
        total, saw_any = ea_daily_total_mm(g['measure_id'], target_date)
        if saw_any:
            return g['station_ref'], g['distance_km'], total
    return None, None, None


def build_card_lines(rows, area, geohash, rain_mm=None, rain_distance_km=None):
    """(opener, lines, footnote) from yesterday's hourly Met Office rows at
    one temperature station, plus an optional Environment Agency rain
    total. His call, 14 September 2026: High/Low always; a Rain row only
    when rain_mm is a real positive total (never for a confirmed-dry
    0.0mm, and never guessed at when rain_mm is None because no gauge
    answered) — "if there was rain, we should mention the total, otherwise
    high and low are sufficient". Matches Seoul's own wxday card in shape:
    a title glyph carries the day's weather, the card itself states only
    what was actually measured. High/Low come from every row that has a
    temperature; a field absent from the data is simply left off, never
    guessed at."""
    temps = [r['temperature'] for r in rows if r.get('temperature') is not None]
    hi = max(temps) if temps else None
    lo = min(temps) if temps else None
    mid = midday_row(rows)
    rained = rain_mm is not None and rain_mm > 0

    lines = []
    if hi is not None:
        lines.append({'emoji': '🔺', 'label': 'High', 'value': fmt_c(hi)})
    if lo is not None:
        lines.append({'emoji': '🔻', 'label': 'Low', 'value': fmt_c(lo)})
    if rained:
        lines.append({'emoji': '🌧️', 'label': 'Rain', 'value': f'{rain_mm:.1f}mm'})

    if rained:
        emoji = '🌧️'  # rain beats the midday cloud reading, matching Seoul's
                        # own wx_day_emoji() precedence
    else:
        code = mid.get('weather_code') if mid else None
        emoji = WEATHER_EMOJI.get(code, '') if code is not None else ''
    opener = {'emoji': emoji, 'text': "London's weather yesterday"}

    distance = round(station_distance_km(geohash))
    station_desc = area or 'nearest reporting station'
    footnote = (f'Met Office observation: {station_desc}, the nearest reporting '
                f'station with data, about {distance} km from central London')
    if rained and rain_distance_km is not None:
        footnote += (f'. Rain: Environment Agency gauge, about '
                     f'{round(rain_distance_km)} km away')
    return opener, lines, footnote


def build_alt(opener, lines, footnote):
    parts = [card.curly(f"{opener['emoji']} {opener['text']}".strip())]
    for l in lines:
        parts.append(card.curly(f"{l['label']}: {l['value']}"))
    if footnote:
        parts.append(card.curly(footnote))
    return '\n'.join(parts)


def already_posted(target_date):
    """True if WXDAY_LOG already holds a successful post for target_date
    (an ISO 'YYYY-MM-DD' string) — matching every other daily card's own
    safety-net-rerun guard on this account."""
    if not WXDAY_LOG.exists():
        return False
    with open(WXDAY_LOG) as f:
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
        sys.exit('Another london_wxday_post run is in progress; bowing out.')

    now = datetime.now(LONDON_TZ)
    print(f'--- run at {now:%Y-%m-%d %H:%M:%S} {now:%Z} ---')

    target_date = now.date() - timedelta(days=1)
    target_str = target_date.isoformat()
    dry_run = '--dry-run' in sys.argv
    if not dry_run and already_posted(target_str):
        print(f'Already posted for {target_str}; nothing to do '
              f'(safety-net rerun after an earlier success).')
        return

    api_key = keychain_land_obs_key()
    if not api_key:
        sys.exit(f'No Keychain password for account="london-index" '
                 f'service="{MET_OFFICE_LAND_OBS_KEYCHAIN_SERVICE}".\n'
                 f'Add it with:\n'
                 f'  security add-generic-password -a "london-index" '
                 f'-s "{MET_OFFICE_LAND_OBS_KEYCHAIN_SERVICE}" -w "<key>"')

    geohash, area, rows = first_working_station(api_key)
    if geohash is None:
        sys.exit('No Land Observations station answered with data '
                 f'(tried {NEAREST_CANDIDATES} nearest candidates).')
    print(f'Using station geohash={geohash!r} area={area!r}, '
          f'about {round(station_distance_km(geohash))} km from central London')

    day_rows = yesterdays_rows(rows, target_date)
    if not day_rows:
        sys.exit(f'No observation rows for {target_str} at station {geohash!r} yet.')
    print(f'{len(day_rows)} hourly rows for {target_str}: '
          f'{json.dumps(day_rows, indent=2)}')

    rain_station, rain_distance_km, rain_mm = first_working_rain_gauge(target_date)
    if rain_station is None:
        print('No Environment Agency rain gauge answered; card will show High/Low only.')
    else:
        print(f'Rain gauge {rain_station!r}, about {round(rain_distance_km)} km away: '
              f'{rain_mm}mm on {target_str}')

    opener, lines, footnote = build_card_lines(day_rows, area, geohash,
                                               rain_mm=rain_mm, rain_distance_km=rain_distance_km)
    if not any(l['label'] in ('High', 'Low') for l in lines):
        sys.exit(f'No usable temperature readings for {target_str}; nothing to post.')

    dateline = f'{target_date:%-d %B %Y}'
    alt = build_alt(opener, lines, footnote)
    print(f"\n{opener['emoji']} {opener['text']}")
    for l in lines:
        print(f"  {l['label']}: {l['value']}")
    print(f'  ({footnote})')
    print(f'\nAlt ({len(alt)} chars):\n{"-"*46}\n{alt}\n{"-"*46}')

    fallback = False
    try:
        out_path, size = card.render_card(opener, lines, HERE / 'wxday_card.png',
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

    # Credit exactly the sources this card actually used — Environment
    # Agency only when a Rain row is actually on the card, matching this
    # codebase's own "extra_src() credits exactly the sources a day used"
    # rule elsewhere (see CLAUDE.md, seoul-transit-art).
    rain_shown = any(l['label'] == 'Rain' for l in lines)

    if not fallback:
        ar = models.AppBskyEmbedDefs.AspectRatio(width=size[0], height=size[1])
        p1 = bsky.send_image(text='', image=image_bytes, image_alt=alt,
                             langs=['en'], image_aspect_ratio=ar)
        root_ref = models.create_strong_ref(p1)
        tb = client_utils.TextBuilder()
        tb.link('Met Office', 'https://www.metoffice.gov.uk')
        if rain_shown:
            tb.text(' · ')
            tb.link('Environment Agency', 'https://www.gov.uk/government/organisations/environment-agency')
        bsky.send_post(text=tb, reply_to=models.AppBskyFeedPost.ReplyRef(
            parent=root_ref, root=root_ref), langs=['en'])
        print('\nPosted (2-post thread: card, source reply).')
    else:
        body = f"{opener['text']}\n" + '\n'.join(f"{l['label']}: {l['value']}" for l in lines)
        body += '\nSource: Met Office, Environment Agency' if rain_shown else '\nSource: Met Office'
        if len(body) > MAX_POST_CHARS:
            sys.exit(f'Plaintext-fallback post too long ({len(body)} chars, max {MAX_POST_CHARS}).')
        p1 = bsky.send_post(text=body, langs=['en'])
        print('\nPosted (plaintext fallback, render failed).')

    try:
        with open(WXDAY_LOG, 'a') as f:
            f.write(json.dumps({
                'posted_at': now.isoformat(), 'target_date': target_str,
                'geohash': geohash, 'area': area,
                'high': max((r['temperature'] for r in day_rows if r.get('temperature') is not None), default=None),
                'low': min((r['temperature'] for r in day_rows if r.get('temperature') is not None), default=None),
                'rain_mm': rain_mm if rain_shown else None,
                'rain_station': rain_station if rain_shown else None,
                'uri': p1.uri,
            }) + '\n')
    except OSError:
        pass  # best-effort — the post is already out


if __name__ == '__main__':
    main()
