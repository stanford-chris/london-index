#!/usr/bin/env python3
"""
FIRST-PASS PROTOTYPE. Harvests a pool of candidate facts from the nine London
data sources scouted since 29 August 2026, in the shape Seoul Index calls
step 1 of "how a post is built": real numbers, pre-formatted, nothing
curated yet.

This is NOT the bot. There is no selection, no card rendering, no Bluesky
account, no posting. It exists to answer one question: what does a real fact
pulled from each source actually look like? Run it and read the output.

Sources, and why each is here (scouted and verified live 29 August 2026,
dcms_museums added 30 August):
  tfl_bikes     - TfL BikePoint: bikes/docks available right now, citywide.
                  Not TfL line status - tflbot.bsky.social (live since Oct
                  2024, 10k+ posts) already owns that vein. See README once
                  one exists.
  flood         - Environment Agency flood-monitoring: warnings/alerts for
                  London, no key, Open Government Licence.
  river_levels  - Environment Agency river gauges: current level against
                  each station's own published typical range.
  police        - data.police.uk: street-level crime, no key. Monthly, and
                  the API lags roughly two months behind the calendar.
  police_boroughs - the same data.police.uk feed, sampled at 8 curated
                  borough town halls instead of one central point.
  cycle_hires   - London Datastore's own "Number of Bicycle Hires" dataset
                  (a daily-hire count TfL supplies to the Datastore, distinct
                  from the live BikePoint feed above): a periodic XLSX drop,
                  same shape as Seoul's SHEET-type resources.
  laqn          - London Air Quality Network: current per-site air quality
                  band, borough by borough.
  tfl_crowding  - PAUSED 31 August 2026 (see HARVESTERS) - TfL's undocumented
                  /crowding/{naptanId}/Live endpoint, live footfall as a
                  percentage of each station's own typical baseline. Kept
                  here, not deleted: real and working, just not currently
                  harvested, in case a live vein is worth having again.
  station_usage - TfL's own Annual Station Counts (crowding.data.tfl.gov.uk,
                  a periodic XLSX drop, same shape as dcms_museums/
                  cycle_hires): real annualised entry/exit taps per London
                  Underground station, the direct replacement for
                  tfl_crowding above - an absolute headcount "busiest" can
                  actually mean, rather than a percentage of a station's own
                  unknowable normal. File and year discovered from TfL's own
                  S3 listing each run, never hardcoded - see
                  _annual_station_counts_file().
  daily_footfall - TfL's Network Demand "StationFootfall" CSV (same S3
                  bucket as station_usage, discovered the same way - see
                  _daily_footfall_file()): real entry/exit taps for the
                  most recent day TfL has published, typically ~9 days
                  behind. Deliberately wider than station_usage - the
                  whole network (Underground, Overground, DLR, Elizabeth
                  line) rather than Underground only, on Chris's call
                  after asking whether it should be scoped down to match.
                  A per-station outlier guard drops any station reading
                  under 10% of its own trailing-week average before
                  ranking - added after a real case (three consecutive
                  District line stations collapsing to under 1% of normal
                  on the same day, almost certainly a gate/reader fault,
                  not three empty stations) would otherwise have been
                  posted as "Quietest".
  dcms_museums  - DCMS's own "Sponsored museums and galleries: annual
                  performance indicators" release (GOV.UK, a periodic ODS
                  drop, same shape as cycle_hires): per-museum annual
                  visitor figures, filtered to the 13 London-based
                  institutions out of the 18 DCMS sponsors nationally. See
                  LONDON_DCMS_MUSEUMS for which and why. Annual, like
                  police_boroughs is monthly - next update expected 2027.
  stop_search   - data.police.uk again, the Metropolitan Police's stop and
                  search records for the newest populated month: searches,
                  arrests, no-further-action, searches for drugs and weapons.
  house_prices  - HM Land Registry's UK House Price Index, its own linked-
                  data JSON, no key: London's average price and annual
                  change, flats against detached houses, and all 33
                  boroughs ranked. Monthly, about two months behind.
  road_works    - TfL's Road/all/Disruption: everything TfL lists as a
                  disruption on its own roads right now. Live.
  lfb_animals   - London Datastore's "Animal rescue incidents attended by
                  LFB", a monthly XLSX drop: the newest complete month's
                  rescues by kind of animal and borough, and the brigade's
                  own notional cost. The four above were added 12 September
                  2026; see harvest_police_boroughs()'s comment for why.
  rail_departures - Rail Data Marketplace's Live Departure Board (Rail
                  Delivery Group): National Rail trains due in the next 60
                  minutes from 13 London termini, on time, late, cancelled,
                  and the termini ranked. Live. Key in Keychain
                  (london-index / rdm-ldbws-key). Added 12 September 2026.

Usage:
    python3 london_index_harvest.py            # pool as pretty JSON
    python3 london_index_harvest.py --source tfl_bikes
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Every Underground station whose crowding endpoint actually returns live
# data, not a hand-picked subset - widened from the original 12-hub list on
# 31 August 2026 after Chris asked to go as broad as possible. Measured, not
# guessed: enumerated all 270 tube-mode stops via
# StopPoint/Type/NaptanMetroStation (filtered to the 940GZZLU prefix - the
# Underground-specific NaptanMetroStation id, since the HUB id itself and a
# DLR/rail sibling both return dataAvailable:false), then called
# /crowding/{naptanId}/Live against all 270. 226 returned dataAvailable:true
# with no error and no status code on the other 44 - read as "no footfall
# sensor at this platform" rather than a resolvable id problem, since the
# 940GZZLU filter already rules out the wrong-child-stop failure mode.
#
# One of those 226, Paddington (H&C Line) / 940GZZLUPAH, is TfL splitting a
# single station's crowding by line group rather than a second real place -
# its Hammersmith & City / Circle platforms sit within the same Paddington
# complex the plain 'Paddington' entry already covers, and the Tube map
# carries only one "Paddington" node. Dropped, keeping just 'Paddington'.
# Edgware Road and Hammersmith are NOT the same situation despite matching
# the same "(Line)" naming shape: each is genuinely two separate, differently
# located station buildings sharing one name (confirmed by comparing
# StopPoint lat/lon - roughly 150-250m apart, not the same building), so both
# Edgware Road entries are kept with TfL's own disambiguating qualifiers.
# Hammersmith (Dist&Picc Line) has no live data of its own, so only its H&C
# counterpart appears here - kept with its qualifier anyway, so it never
# reads as "the" Hammersmith when a second station of that name exists.
#
# 225 stations total. Station names are TfL's own commonName with the
# " Underground Station" suffix and "St. " periods stripped, and straight
# apostrophes curled to match house style - alt text (london_index_post.py)
# builds directly from these strings with no curly() pass of its own, so an
# uncurled name here ships an uncurled mark to a reader.
TFL_STATIONS = {
    'Acton Town': '940GZZLUACT',
    'Aldgate': '940GZZLUALD',
    'Aldgate East': '940GZZLUADE',
    'Alperton': '940GZZLUALP',
    'Amersham': '940GZZLUAMS',
    'Angel': '940GZZLUAGL',
    'Archway': '940GZZLUACY',
    'Arnos Grove': '940GZZLUASG',
    'Baker Street': '940GZZLUBST',
    'Balham': '940GZZLUBLM',
    'Bank': '940GZZLUBNK',
    'Barbican': '940GZZLUBBN',
    'Barking': '940GZZLUBKG',
    'Barkingside': '940GZZLUBKE',
    'Barons Court': '940GZZLUBSC',
    'Bayswater': '940GZZLUBWT',
    'Becontree': '940GZZLUBEC',
    'Belsize Park': '940GZZLUBZP',
    'Bermondsey': '940GZZLUBMY',
    'Bethnal Green': '940GZZLUBLG',
    'Blackfriars': '940GZZLUBKF',
    'Blackhorse Road': '940GZZLUBLR',
    'Borough': '940GZZLUBOR',
    'Bounds Green': '940GZZLUBDS',
    'Bow Road': '940GZZLUBWR',
    'Brent Cross': '940GZZLUBTX',
    'Brixton': '940GZZLUBXN',
    'Bromley-by-Bow': '940GZZLUBBB',
    'Buckhurst Hill': '940GZZLUBKH',
    'Burnt Oak': '940GZZLUBTK',
    'Camden Town': '940GZZLUCTN',
    'Canada Water': '940GZZLUCWR',
    'Canary Wharf': '940GZZLUCYF',
    'Cannon Street': '940GZZLUCST',
    'Canons Park': '940GZZLUCPK',
    'Chalfont & Latimer': '940GZZLUCAL',
    'Chalk Farm': '940GZZLUCFM',
    'Chancery Lane': '940GZZLUCHL',
    'Charing Cross': '940GZZLUCHX',
    'Chesham': '940GZZLUCSM',
    'Chigwell': '940GZZLUCWL',
    'Chiswick Park': '940GZZLUCWP',
    'Chorleywood': '940GZZLUCYD',
    'Clapham Common': '940GZZLUCPC',
    'Clapham North': '940GZZLUCPN',
    'Clapham South': '940GZZLUCPS',
    'Cockfosters': '940GZZLUCKS',
    'Colliers Wood': '940GZZLUCSD',
    'Covent Garden': '940GZZLUCGN',
    'Croxley': '940GZZLUCXY',
    'Dagenham East': '940GZZLUDGE',
    'Dagenham Heathway': '940GZZLUDGY',
    'Debden': '940GZZLUDBN',
    'Dollis Hill': '940GZZLUDOH',
    'Ealing Broadway': '940GZZLUEBY',
    'Ealing Common': '940GZZLUECM',
    'Earl’s Court': '940GZZLUECT',
    'East Acton': '940GZZLUEAN',
    'East Finchley': '940GZZLUEFY',
    'East Ham': '940GZZLUEHM',
    'East Putney': '940GZZLUEPY',
    'Eastcote': '940GZZLUEAE',
    'Edgware': '940GZZLUEGW',
    'Edgware Road (Bakerloo)': '940GZZLUERB',
    'Edgware Road (Circle Line)': '940GZZLUERC',
    'Elephant & Castle': '940GZZLUEAC',
    'Elm Park': '940GZZLUEPK',
    'Embankment': '940GZZLUEMB',
    'Epping': '940GZZLUEPG',
    'Euston': '940GZZLUEUS',
    'Euston Square': '940GZZLUESQ',
    'Fairlop': '940GZZLUFLP',
    'Farringdon': '940GZZLUFCN',
    'Finchley Central': '940GZZLUFYC',
    'Finchley Road': '940GZZLUFYR',
    'Finsbury Park': '940GZZLUFPK',
    'Fulham Broadway': '940GZZLUFBY',
    'Gants Hill': '940GZZLUGTH',
    'Gloucester Road': '940GZZLUGTR',
    'Golders Green': '940GZZLUGGN',
    'Goldhawk Road': '940GZZLUGHK',
    'Goodge Street': '940GZZLUGDG',
    'Grange Hill': '940GZZLUGGH',
    'Great Portland Street': '940GZZLUGPS',
    'Green Park': '940GZZLUGPK',
    'Greenford': '940GZZLUGFD',
    'Gunnersbury': '940GZZLUGBY',
    'Hainault': '940GZZLUHLT',
    'Hammersmith (H&C Line)': '940GZZLUHSC',
    'Hampstead': '940GZZLUHTD',
    'Hanger Lane': '940GZZLUHGR',
    'Harlesden': '940GZZLUHSN',
    'Harrow & Wealdstone': '940GZZLUHAW',
    'Harrow-on-the-Hill': '940GZZLUHOH',
    'Hatton Cross': '940GZZLUHNX',
    'Heathrow Terminal 4': '940GZZLUHR4',
    'Heathrow Terminals 2 & 3': '940GZZLUHRC',
    'Hendon Central': '940GZZLUHCL',
    'High Barnet': '940GZZLUHBT',
    'High Street Kensington': '940GZZLUHSK',
    'Highbury & Islington': '940GZZLUHAI',
    'Highgate': '940GZZLUHGT',
    'Hillingdon': '940GZZLUHGD',
    'Holborn': '940GZZLUHBN',
    'Holland Park': '940GZZLUHPK',
    'Hornchurch': '940GZZLUHCH',
    'Hounslow Central': '940GZZLUHWC',
    'Hounslow East': '940GZZLUHWE',
    'Hounslow West': '940GZZLUHWT',
    'Hyde Park Corner': '940GZZLUHPC',
    'Ickenham': '940GZZLUICK',
    'Kennington': '940GZZLUKNG',
    'Kensal Green': '940GZZLUKSL',
    'Kentish Town': '940GZZLUKSH',
    'Kenton': '940GZZLUKEN',
    'Kew Gardens': '940GZZLUKWG',
    'Kilburn': '940GZZLUKBN',
    'Kilburn Park': '940GZZLUKPK',
    'Kingsbury': '940GZZLUKBY',
    'King’s Cross St Pancras': '940GZZLUKSX',
    'Knightsbridge': '940GZZLUKNB',
    'Lambeth North': '940GZZLULBN',
    'Lancaster Gate': '940GZZLULGT',
    'Latimer Road': '940GZZLULRD',
    'Leicester Square': '940GZZLULSQ',
    'Leyton': '940GZZLULYN',
    'Liverpool Street': '940GZZLULVT',
    'London Bridge': '940GZZLULNB',
    'Loughton': '940GZZLULGN',
    'Maida Vale': '940GZZLUMVL',
    'Manor House': '940GZZLUMRH',
    'Mansion House': '940GZZLUMSH',
    'Marble Arch': '940GZZLUMBA',
    'Mile End': '940GZZLUMED',
    'Mill Hill East': '940GZZLUMHL',
    'Monument': '940GZZLUMMT',
    'Moor Park': '940GZZLUMPK',
    'Moorgate': '940GZZLUMGT',
    'Morden': '940GZZLUMDN',
    'Mornington Crescent': '940GZZLUMTC',
    'Newbury Park': '940GZZLUNBP',
    'North Acton': '940GZZLUNAN',
    'North Ealing': '940GZZLUNEN',
    'North Greenwich': '940GZZLUNGW',
    'North Harrow': '940GZZLUNHA',
    'North Wembley': '940GZZLUNWY',
    'Northfields': '940GZZLUNFD',
    'Northolt': '940GZZLUNHT',
    'Northwick Park': '940GZZLUNKP',
    'Northwood': '940GZZLUNOW',
    'Northwood Hills': '940GZZLUNWH',
    'Notting Hill Gate': '940GZZLUNHG',
    'Oakwood': '940GZZLUOAK',
    'Old Street': '940GZZLUODS',
    'Osterley': '940GZZLUOSY',
    'Oval': '940GZZLUOVL',
    'Oxford Circus': '940GZZLUOXC',
    'Paddington': '940GZZLUPAC',
    'Pinner': '940GZZLUPNR',
    'Putney Bridge': '940GZZLUPYB',
    'Queensbury': '940GZZLUQBY',
    'Queensway': '940GZZLUQWY',
    'Queen’s Park': '940GZZLUQPS',
    'Ravenscourt Park': '940GZZLURVP',
    'Redbridge': '940GZZLURBG',
    'Richmond': '940GZZLURMD',
    'Rickmansworth': '940GZZLURKW',
    'Roding Valley': '940GZZLURVY',
    'Royal Oak': '940GZZLURYO',
    'Ruislip': '940GZZLURSP',
    'Ruislip Gardens': '940GZZLURSG',
    'Shepherd’s Bush (Central)': '940GZZLUSBC',
    'Shepherd’s Bush Market': '940GZZLUSBM',
    'Snaresbrook': '940GZZLUSNB',
    'South Ealing': '940GZZLUSEA',
    'South Harrow': '940GZZLUSHH',
    'South Kensington': '940GZZLUSKS',
    'South Ruislip': '940GZZLUSRP',
    'South Wimbledon': '940GZZLUSWN',
    'Southfields': '940GZZLUSFS',
    'Southgate': '940GZZLUSGT',
    'Southwark': '940GZZLUSWK',
    'St John’s Wood': '940GZZLUSJW',
    'St Paul’s': '940GZZLUSPU',
    'Stamford Brook': '940GZZLUSFB',
    'Stanmore': '940GZZLUSTM',
    'Stepney Green': '940GZZLUSGN',
    'Stockwell': '940GZZLUSKW',
    'Stratford': '940GZZLUSTD',
    'Sudbury Town': '940GZZLUSUT',
    'Swiss Cottage': '940GZZLUSWC',
    'Temple': '940GZZLUTMP',
    'Theydon Bois': '940GZZLUTHB',
    'Tottenham Court Road': '940GZZLUTCR',
    'Tottenham Hale': '940GZZLUTMH',
    'Totteridge & Whetstone': '940GZZLUTAW',
    'Tufnell Park': '940GZZLUTFP',
    'Turnham Green': '940GZZLUTNG',
    'Turnpike Lane': '940GZZLUTPN',
    'Upminster': '940GZZLUUPM',
    'Upney': '940GZZLUUPY',
    'Upton Park': '940GZZLUUPK',
    'Uxbridge': '940GZZLUUXB',
    'Victoria': '940GZZLUVIC',
    'Walthamstow Central': '940GZZLUWWL',
    'Warren Street': '940GZZLUWRR',
    'Warwick Avenue': '940GZZLUWKA',
    'Waterloo': '940GZZLUWLO',
    'Watford': '940GZZLUWAF',
    'Wembley Central': '940GZZLUWYC',
    'Wembley Park': '940GZZLUWYP',
    'West Brompton': '940GZZLUWBN',
    'West Ham': '940GZZLUWHM',
    'West Hampstead': '940GZZLUWHP',
    'West Kensington': '940GZZLUWKN',
    'West Ruislip': '940GZZLUWRP',
    'Westbourne Park': '940GZZLUWSP',
    'Westminster': '940GZZLUWSM',
    'White City': '940GZZLUWCY',
    'Whitechapel': '940GZZLUWPL',
    'Wimbledon': '940GZZLUWIM',
    'Wimbledon Park': '940GZZLUWIP',
    'Wood Green': '940GZZLUWOG',
    'Woodford': '940GZZLUWOF',
    'Woodside Park': '940GZZLUWOP',
}

# Seconds between calls to /crowding/*/Live when running WITHOUT a key.
# Verified 29 August 2026: three calls in quick succession, unauthenticated,
# drew a 429 on the third. With TFL_APP_KEY set this delay is skipped
# entirely - 8 rapid back-to-back authenticated calls all came back clean.
STATION_DELAY = 4

# How many stations a ranked-list card shows, shared by tfl_crowding (now
# paused - see HARVESTERS) and station_usage. 4, not 5, so it fits inside
# compose.py's existing MAX_LINES=4 without raising a cap every other
# vein's cards share too.
TOP_RANKED_COUNT = 4


def curl(url, timeout=25):
    """Shell out to curl. See reference_py313_ssl_urllib: this Python's own
    urllib fails certificate verification on this machine."""
    result = subprocess.run(
        ['curl', '-sS', '--max-time', str(timeout), url],
        capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout


def get_json(url, timeout=25):
    body = curl(url, timeout=timeout)
    if body is None:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def _tfl_app_key():
    """The subscription key from Keychain, or None if not configured - every
    TfL harvester here still works key-free, just slower on /crowding (see
    STATION_DELAY). ⚠️ Verified 29 August 2026: the first attempt at storing
    this key silently concatenated the Profile page's primary AND secondary
    keys into one 66-character string with no separator, which TfL rejects
    with a 429 whose body actually reads "Invalid app_key is provided" - not
    a rate limit at all, despite the status code. A real key is 32 lowercase
    hex characters; anything else stored here is almost certainly this same
    mistake and should be re-copied, one key only."""
    result = subprocess.run(
        ['security', 'find-generic-password', '-a', 'london-index', '-s', 'tfl-api-key', '-w'],
        capture_output=True, text=True)
    if result.returncode != 0:
        return None
    key = result.stdout.strip()
    return key or None


TFL_APP_KEY = _tfl_app_key()


def tfl_get_json(url, timeout=25):
    """get_json for api.tfl.gov.uk endpoints, with the app_key appended when
    one is configured in Keychain."""
    if TFL_APP_KEY:
        sep = '&' if '?' in url else '?'
        url = f'{url}{sep}app_key={TFL_APP_KEY}'
    return get_json(url, timeout=timeout)


def fact(value, label, source, url, period=None, pair=None, context_note=None):
    """`pair` tags a fact as part of a pre-detected juxtaposition — a group
    of facts sharing one pair id are offered to the selector as a single
    unit worth building a card around, the same mechanism Seoul Index's
    fact()/pair argument uses. Facts with no pair are still individually
    selectable; pair is purely an extra hint, never a restriction.

    `context_note` is a short clause explaining what a vein's own value
    actually MEANS and/or what sample its extremes or ranking were drawn
    from (e.g. "% of each station's own typical footfall, not a headcount —
    sampled across 225 of London's 270 Underground stations") — compose()
    surfaces it on the source-credit line, never the card image itself, so
    a "busiest"/"quietest"/ranked-list card states both what its metric is
    and what it's the busiest/quietest/highest-ranked OF. Named
    context_note rather than 'pool' so it can't be confused with the fact
    POOL every caller here already passes around (build_pool(),
    compose(sel, pool), select(pool, state) — that word means something
    else throughout this codebase). Added 31 August 2026 for tfl_crowding,
    after two real questions about real cards neither could answer on its
    own: "why these two [stations, out of how many]?" and, once that was
    fixed, "we need a clearer description of 'baseline'" — the pool size
    alone wasn't the whole gap."""
    return {'value': value, 'label': label, 'source': source, 'url': url,
            'period': period, 'pair': pair, 'context_note': context_note}


def pct_of_baseline(fraction):
    """Formats a 0-1 fraction as "31% of baseline" etc, without claiming
    more precision than is true. A bare "0%" reads as a literal, absolute
    claim - "0%" and "0.3%" both round to it, and a reader has no way to
    tell a genuine zero from a rounding artifact. Checked 31 August 2026
    against live data: some stations really were an exact 0 in the API
    response (Chesham, Roding Valley - not rounded down, the field itself
    is 0), others showing the same "0%" were 0.02-0.25% underneath. "<1%"
    for anything nonzero that would otherwise round to 0 keeps "0%" meaning
    only what the API itself reported as exactly zero."""
    pct = fraction * 100
    if 0 < pct < 0.5:
        return '<1% of baseline'
    return f'{pct:.0f}% of baseline'


def dead_heat(values, rel_threshold=0.02):
    """The two (name, value) entries whose values are closest, if within
    rel_threshold of each other (relative gap = |a-b|/max(|a|,|b|)) — the
    same detector Seoul Index's sales_facts() uses to find a genuine near-tie
    out of a larger candidate pool, rather than only ever offering the widest
    possible gap. `values` should hold every sampled reading for a vein, not
    just the extremes, or there is nothing for this to find. Returns
    (name_a, value_a, name_b, value_b) for the closest qualifying pair, or
    None if fewer than 2 values or nothing is close enough to call a tie."""
    best = None
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            na, va = values[i]
            nb, vb = values[j]
            m = max(abs(va), abs(vb))
            if m == 0:
                continue
            gap = abs(va - vb) / m
            if gap <= rel_threshold and (best is None or gap < best[4]):
                best = (na, va, nb, vb, gap)
    return best[:4] if best else None


def harvest_tfl_bikes():
    d = tfl_get_json('https://api.tfl.gov.uk/BikePoint')
    if not isinstance(d, list):
        return [], 'BikePoint fetch failed'

    def prop(bp, key):
        for a in bp.get('additionalProperties', []):
            if a['key'] == key:
                return a['value']
        return None

    total_bikes = sum(int(prop(bp, 'NbBikes') or 0) for bp in d)
    total_docks = sum(int(prop(bp, 'NbDocks') or 0) for bp in d)
    zero_bike = sum(1 for bp in d if int(prop(bp, 'NbBikes') or 0) == 0)
    url = 'https://api.tfl.gov.uk/BikePoint'
    facts = [
        fact(f'{total_bikes:,}', 'Santander Cycles available now',
             'TfL BikePoint', url),
        fact(f'{zero_bike} of {len(d):,}',
             'Docking stations with no bikes', 'TfL BikePoint', url),
        fact(f'{total_docks:,}', 'Docking points across the scheme',
             'TfL BikePoint', url),
    ]
    return facts, None


FLOOD_URL = 'https://environment.data.gov.uk/flood-monitoring/id/floods?county=London'


def flood_facts(items, url=FLOOD_URL):
    """Warnings and alerts counted separately, from the feed's own
    severityLevel (1 severe warning, 2 warning, 3 alert, 4 no longer in
    force, per the Environment Agency's API reference). Until 12 September
    2026 this vein was one fact, the combined count, which kept it under
    STARVE_MIN_FACTS and out of rotation for ever; the split is the second
    comparable figure SESSION_SUMMARY.md said would bring it back. Items
    with no usable severityLevel fall back to the old single fact rather
    than publishing two confident zeros over a changed schema."""
    levels = []
    for i in items:
        lvl = i.get('severityLevel')
        try:
            levels.append(int(lvl))
        except (TypeError, ValueError):
            pass
    active = [i for i in items if 'no longer in force' not in (i.get('description') or '').lower()
              and (i.get('severity') or '').lower() != 'warning no longer in force']
    if len(levels) != len(items):
        return [fact(str(len(active)), 'Active flood warnings or alerts',
                     'Environment Agency', url)]
    warnings = sum(1 for l in levels if l in (1, 2))
    alerts = sum(1 for l in levels if l == 3)
    return [
        fact(str(warnings), 'Warnings in force', 'Environment Agency', url,
             pair='flood_gap'),
        fact(str(alerts), 'Alerts in force', 'Environment Agency', url,
             pair='flood_gap'),
    ]


def harvest_flood():
    d = get_json(FLOOD_URL)
    if not isinstance(d, dict) or 'items' not in d:
        return [], 'flood-monitoring fetch failed'
    return flood_facts(d['items']), None


# Curated London river gauges with a published typical range, found 29 August
# 2026 via a real /stations?parameter=level&lat=...&long=...&dist=15 query
# (NOT guessed from plausible-looking ids - an earlier attempt to hand-pick
# ids for "Richmond", "Chelsea" and "Woolwich" from memory returned Reading,
# Boveney Lock and a 404 instead, because those ids belong to other stations
# entirely). The three tidal Thames gauges in central London (Westminster,
# Tower Pier, Richmond - 0006/0007/0009) publish level but no typical range,
# since a tidal reading swings with the tide rather than sitting in a band,
# so they're excluded here rather than forced into a comparison they can't
# support.
RIVER_STATIONS = {
    'Thames at Kingston': '3400TH',
    'Wandle at Beddington': '4150TH',
    'Ravensbourne at Catford': '4370TH',
    'Roding at Wanstead': '5480TH',
    'Brent at Golders Green': '3820TH',
    'Quaggy at Hither Green': '4389TH',
}


def harvest_river_levels():
    readings = []
    failed = []
    for name, station_id in RIVER_STATIONS.items():
        meta = get_json(f'https://environment.data.gov.uk/flood-monitoring/id/stations/{station_id}.json')
        if not isinstance(meta, dict) or 'items' not in meta:
            failed.append(f'{name} (metadata fetch failed)')
            continue
        item = meta['items']
        if isinstance(item, list):
            item = item[0] if item else {}
        scale = item.get('stageScale', {})
        low, high = scale.get('typicalRangeLow'), scale.get('typicalRangeHigh')
        if low is None or high is None:
            failed.append(f'{name} (no typical range published)')
            continue
        r = get_json(f'https://environment.data.gov.uk/flood-monitoring/id/stations/'
                     f'{station_id}/readings?_sorted&_limit=1&parameter=level')
        items = r.get('items') if isinstance(r, dict) else None
        if not items:
            failed.append(f'{name} (no current reading)')
            continue
        value, when = items[0]['value'], items[0].get('dateTime')
        pct = (value - low) / (high - low) * 100
        readings.append((name, value, low, high, pct, when))

    if not readings:
        return [], f'no station returned a usable reading; failed: {failed}'

    url = 'https://environment.data.gov.uk/flood-monitoring/id/stations/{id}/readings'

    def _val(value, pct):
        # Unlike tfl_crowding's own value string ("31% of baseline"), this
        # used to ship a bare "(55%)" with no referent at all - a reader
        # asked "on this card, it's 55% of what?" on 31 August 2026, and
        # nothing on the post could have answered them. "of range" matches
        # the term already used for this stat elsewhere (see
        # london_index_select.py's cross-vein rule, "a river's '% of
        # range'"), so it stays consistent with how the account talks about
        # this vein rather than inventing a second name for the same idea.
        if pct < 0:
            return f'{value}m (below range)'
        if pct > 100:
            return f'{value}m (above range)'
        return f'{value}m ({pct:.0f}% of range)'

    highest = max(readings, key=lambda r: r[4])
    lowest = min(readings, key=lambda r: r[4])
    facts = []
    for prefix, r in [('Fullest', highest), ('Driest', lowest)]:
        name, value, low, high, pct, when = r
        # Label kept to "Word: name" (no "river", no range bounds) so it
        # never wraps even for the longest curated names (Ravensbourne at
        # Catford, Brent at Golders Green) alongside a value and a leader
        # on one line -- see CARD_WIDTH's own comment on the same trade.
        facts.append(fact(_val(value, pct), f'{prefix}: {name}',
                           'Environment Agency', url, period=when,
                           pair='river_gap'))
    # Dead-heat: two of the 6 sampled gauges whose fullness (as % of typical
    # range) happens to land on nearly the same reading, out of the whole
    # curated set rather than just the extremes above.
    heat = dead_heat([(r[0], r[4]) for r in readings])
    if heat:
        name_a, _, name_b, _ = heat
        by_name = {r[0]: r for r in readings}
        for name in (name_a, name_b):
            _, value, low, high, pct, when = by_name[name]
            facts.append(fact(_val(value, pct), f'Level: {name}',
                               'Environment Agency', url, period=when,
                               pair='river_heat'))
    if failed:
        facts[0]['note'] = f'{len(failed)} of {len(RIVER_STATIONS)} curated gauges unusable: {failed}'
    return facts, None


def _shift_month(ym, back):
    """"2026-07" shifted `back` calendar months: _shift_month("2026-07", 1)
    is "2026-06", _shift_month("2026-01", 1) is "2025-12". Real month
    arithmetic, replacing the old `today - 30 days * back` walk, which
    could land on the same month twice or skip one across a 31-day month."""
    y, m = (int(x) for x in ym.split('-'))
    idx = y * 12 + (m - 1) - back
    return f'{idx // 12:04d}-{idx % 12 + 1:02d}'


def _readable_month(ym):
    return datetime.strptime(ym, '%Y-%m').strftime('%B')


def _police_month(lat, lng, ym):
    url = f'https://data.police.uk/api/crimes-street/all-crime?lat={lat}&lng={lng}&date={ym}'
    d = get_json(url)
    return d if isinstance(d, list) else None


def _latest_police_month(lat, lng):
    """The API lags roughly two months; walk backwards from today until a
    non-empty response comes back, rather than guessing the lag. Returns
    (year_month, records) or (None, None) if nothing populated in 4 tries."""
    this_month = datetime.now(timezone.utc).strftime('%Y-%m')
    for back in range(1, 5):
        ym = _shift_month(this_month, back)
        d = _police_month(lat, lng, ym)
        if d:
            return ym, d
    return None, None


def _pct_change(now, before):
    """Signed whole-percent change as a card value: "+7%", "−3%", "0%".
    A typographic minus, not a hyphen — this string reaches a reader on
    the card and in the alt text. None when there is no base to divide by."""
    if not before:
        return None
    pct = round((now - before) / before * 100)
    if pct > 0:
        return f'+{pct}%'
    if pct < 0:
        return f'−{abs(pct)}%'
    return '0%'


def _category_name(cat):
    """data.police.uk's slug ("other-theft", "anti-social-behaviour") as
    label prose. "Anti-social behaviour" keeps its hyphen, since the slug
    carries two of them and only the first is a real word-join."""
    if cat == 'anti-social-behaviour':
        return 'Anti-social behaviour'
    return cat.replace('-', ' ').capitalize()


CENTRAL_NOTE = 'Within a mile of Trafalgar Square'
CENTRAL_TOP_N = 4


def central_facts(records, prev_records, ym, url):
    """The central-London card's facts from one month's records and the
    month before. Pure: no network, so test_london_index_harvest.py can
    pin the shapes. Two card shapes come out of one month's data, where
    until 12 September 2026 there was exactly one (total + most common),
    posted byte-identical four times in six days because the data changes
    monthly and nothing else about the card could:
      - unpaired: the total, the most common category, and the change on
        the previous month (when that month is available)
      - "central_top": the CENTRAL_TOP_N most-reported categories, ranked,
        a whole card on its own."""
    cats = {}
    for r in records:
        cats[r['category']] = cats.get(r['category'], 0) + 1
    ranked = sorted(cats.items(), key=lambda kv: -kv[1])
    top = ranked[0]
    facts = [
        fact(f'{len(records):,}', 'Within a mile of central London',
             'data.police.uk', url, period=ym),
        fact(f'{top[1]:,}', f'Most common: {_category_name(top[0])}',
             'data.police.uk', url, period=ym),
    ]
    if prev_records:
        change = _pct_change(len(records), len(prev_records))
        if change is not None:
            prev_ym = _shift_month(ym, 1)
            facts.append(fact(change, f'Change since {_readable_month(prev_ym)}',
                              'data.police.uk', url, period=ym))
    for cat, n in ranked[:CENTRAL_TOP_N]:
        facts.append(fact(f'{n:,}', _category_name(cat), 'data.police.uk', url,
                          period=ym, pair='central_top', context_note=CENTRAL_NOTE))
    return facts


def harvest_police():
    # 1-mile radius around central London (Trafalgar Square).
    lat, lng = 51.5074, -0.1278
    ym, d = _latest_police_month(lat, lng)
    if ym is None:
        return [], 'no populated month found in the last 4 tried'
    prev = _police_month(lat, lng, _shift_month(ym, 1))
    url = f'https://data.police.uk/api/crimes-street/all-crime?lat={lat}&lng={lng}&date={ym}'
    return central_facts(d, prev, ym, url), None


# Eight boroughs spanning the compass, each a real civic-building address -
# NOT hand-recalled coordinates. Geocoded via Nominatim on 29 August 2026 and
# checked against the returned display_name before use, after the Environment
# Agency river-gauge mistake earlier this session (three station ids picked
# from memory turned out to belong to Reading, Boveney Lock and nothing at
# all). Each is a 1-mile-radius point search, same shape as the central-point
# search above - data.police.uk has no per-borough neighbourhood boundary for
# the Met specifically (/forces/metropolitan/neighbourhoods 404s, unlike
# smaller forces), so an exact boundary match isn't available here.
POLICE_BOROUGHS = {
    'Westminster': (51.4976144, -0.1373436),
    'Camden': (51.5290641, -0.1253598),
    'Hackney': (51.5450733, -0.0563731),
    'Newham': (51.5325869, 0.0555381),
    'Croydon': (51.3720529, -0.0987852),
    'Ealing': (51.5131590, -0.3075859),
    'Brent': (51.5589754, -0.2814288),
    'Bromley': (51.4064739, 0.0180213),
}

# ⚠️ Every borough figure is a one-mile sample around the town hall, not the
# borough's total, and until 12 September 2026 no card said so: "Most:
# Camden 3,179" under "Reported crime" read as Camden's monthly total. This
# note rides every borough fact so compose() puts it in the card's footnote.
BOROUGH_NOTE = ('Within a mile of each town hall; eight boroughs sampled: '
                + ', '.join(POLICE_BOROUGHS))
BOROUGH_TOP_N = 4
# The categories worth a "which borough had the most" line, in the order a
# reader expects them. Anti-social behaviour and other-theft are left out
# on purpose: the first is not a crime in the recorded-crime sense and the
# second is a catch-all whose name explains nothing on a card.
BOROUGH_TYPE_CATEGORIES = ('violent-crime', 'shoplifting', 'vehicle-crime',
                           'burglary', 'bicycle-theft', 'robbery')
BOROUGH_TYPES_N = 4


def borough_facts(counts, prev_counts, cats, ym, url):
    """The borough card's facts from this month's per-borough counts, the
    previous month's, and each borough's per-category counts. Pure, like
    central_facts(). Four card shapes from one month's data, where until
    12 September 2026 there were two (the gap, and a near-tie when one
    existed) and the gap alone was posted five times in five days, since
    the busiest and quietest of eight fixed boroughs do not change within a
    month:
      - "police_gap": most and fewest, as before
      - "police_heat": a genuine near-tie, when one exists, as before
      - "police_top": the BOROUGH_TOP_N busiest, ranked, picked whole
      - "police_change": the biggest rise and the biggest fall (or the
        smallest rise, when every borough rose) on the previous month
      - "police_types_top": for each of BOROUGH_TYPE_CATEGORIES, the
        borough with the most of it, ranked by count, picked whole
    Every fact carries BOROUGH_NOTE."""
    note = BOROUGH_NOTE
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    busiest, quietest = ranked[0], ranked[-1]
    facts = [
        fact(f'{busiest[1]:,}', f'Most: {busiest[0]}',
             'data.police.uk', url, period=ym, pair='police_gap', context_note=note),
        fact(f'{quietest[1]:,}', f'Fewest: {quietest[0]}',
             'data.police.uk', url, period=ym, pair='police_gap', context_note=note),
    ]
    # Dead-heat: two of the curated boroughs whose crime counts happen to
    # land on nearly the same number, out of the whole set rather than just
    # the busiest/quietest extremes above.
    heat = dead_heat(list(counts.items()))
    if heat:
        name_a, _, name_b, _ = heat
        for name in (name_a, name_b):
            facts.append(fact(f'{counts[name]:,}', name,
                               'data.police.uk', url, period=ym,
                               pair='police_heat', context_note=note))
    for name, n in ranked[:BOROUGH_TOP_N]:
        facts.append(fact(f'{n:,}', name, 'data.police.uk', url, period=ym,
                          pair='police_top', context_note=note))
    if prev_counts:
        prev_month = _readable_month(_shift_month(ym, 1))
        changes = [(name, (n - prev_counts[name]) / prev_counts[name])
                   for name, n in counts.items()
                   if prev_counts.get(name)]
        if len(changes) >= 2:
            changes.sort(key=lambda t: -t[1])
            rise_name, rise = changes[0]
            fall_name, fall = changes[-1]
            facts.append(fact(_pct_change(counts[rise_name], prev_counts[rise_name]),
                              f'Biggest rise since {prev_month}: {rise_name}',
                              'data.police.uk', url, period=ym,
                              pair='police_change', context_note=note))
            fall_label = 'Biggest fall' if fall < 0 else 'Smallest rise'
            facts.append(fact(_pct_change(counts[fall_name], prev_counts[fall_name]),
                              f'{fall_label} since {prev_month}: {fall_name}',
                              'data.police.uk', url, period=ym,
                              pair='police_change', context_note=note))
    leaders = []
    for cat in BOROUGH_TYPE_CATEGORIES:
        per = {name: c.get(cat, 0) for name, c in cats.items()}
        if not per or max(per.values()) == 0:
            continue
        name = max(per.items(), key=lambda kv: kv[1])[0]
        leaders.append((cat, name, per[name]))
    leaders.sort(key=lambda t: -t[2])
    for cat, name, n in leaders[:BOROUGH_TYPES_N]:
        facts.append(fact(f'{n:,}', f'{_category_name(cat)}: {name}',
                          'data.police.uk', url, period=ym,
                          pair='police_types_top', context_note=note))
    return facts


def harvest_police_boroughs():
    counts = {}
    cats = {}
    prev_counts = {}
    failed = []
    ym_used = None
    for name, (lat, lng) in POLICE_BOROUGHS.items():
        ym, d = _latest_police_month(lat, lng)
        if ym is None:
            failed.append(name)
            continue
        ym_used = ym_used or ym
        if ym != ym_used:
            # a borough landed on a different "latest" month than the rest -
            # report rather than silently compare across two different
            # months, which would just be measuring API lag, not crime.
            failed.append(f'{name} (only {ym} populated, rest are {ym_used})')
            continue
        counts[name] = len(d)
        per = {}
        for r in d:
            per[r['category']] = per.get(r['category'], 0) + 1
        cats[name] = per
        prev = _police_month(lat, lng, _shift_month(ym, 1))
        if prev:
            prev_counts[name] = len(prev)

    if len(counts) < 2:
        return [], f'fewer than 2 comparable boroughs; failed: {failed}'
    # A change pair over a partial previous month would compare eight
    # boroughs against however many happened to answer; all or none.
    if len(prev_counts) != len(counts):
        prev_counts = {}

    url = 'https://data.police.uk/api/crimes-street/all-crime?lat={lat}&lng={lng}&date={date}'
    facts = borough_facts(counts, prev_counts, cats, ym_used, url)
    if failed:
        facts[0]['note'] = f'{len(failed)} of {len(POLICE_BOROUGHS)} curated boroughs unusable: {failed}'
    return facts, None


def harvest_cycle_hires():
    resource_url = ('https://data.london.gov.uk/download/2r84d/'
                     'ac29363e-e0cb-47cc-a97a-e216d900a6b0/tfl-daily-cycle-hires.xlsx')
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'cycle_hires.xlsx'
        result = subprocess.run(
            ['curl', '-sS', '-L', '--max-time', '30', '-o', str(path), resource_url],
            capture_output=True)
        if result.returncode != 0 or not path.exists():
            return [], 'cycle-hires download failed'
        try:
            import openpyxl
        except ImportError:
            return [], 'openpyxl not installed'
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb['Data']
        rows = [r for r in ws.iter_rows(values_only=True)
                if isinstance(r[1], datetime) and isinstance(r[2], (int, float))]
        if not rows:
            return [], 'no dated rows found in cycle-hires sheet'
        rows.sort(key=lambda r: r[1])
        latest_date, latest_count = rows[-1][1], rows[-1][2]
        year_rows = [r for r in rows if r[1].year == latest_date.year]
        avg = sum(r[2] for r in year_rows) / len(year_rows)
        page_url = 'https://data.london.gov.uk/dataset/number-bicycle-hires'
        # This pair mixes a day-level period (the count) with a year-level
        # one (the average), so compose()'s _is_single_day/_is_period_aggregate
        # both read it as "mixed" and give the card no dateline - and since
        # 31 August 2026 the reply no longer restates a mixed period_credit
        # either (post.py's own comment on that change names cycle_hires as
        # a vein this would leave with no visible date at all). A
        # context_note surfaces on the card's own footnote instead, the same
        # route tfl_crowding uses, so the reader isn't left assuming this is
        # today's count - the Datastore feed runs weeks behind, not days.
        context_note = (
            f'Count is for {latest_date.strftime("%-d %B %Y")}; average is '
            f'{latest_date.year} to date')
        facts = [
            fact(f'{int(latest_count):,}', 'Santander Cycles hired',
                 'London Datastore (TfL daily cycle hires)', page_url,
                 period=latest_date.strftime('%Y-%m-%d'), pair='cycle_gap',
                 context_note=context_note),
            fact(f'{int(avg):,}', 'Average daily hires',
                 'London Datastore (TfL daily cycle hires)', page_url, period=str(latest_date.year),
                 pair='cycle_gap', context_note=context_note),
        ]
        return facts, None


def harvest_laqn():
    d = get_json('https://api.erg.ic.ac.uk/AirQuality/Hourly/MonitoringIndex/GroupName=London/Json')
    if not isinstance(d, dict):
        return [], 'LAQN fetch failed'
    las = d.get('HourlyAirQualityIndex', {}).get('LocalAuthority', [])
    if not isinstance(las, list):
        las = [las]
    bands = {}
    readings = []
    for la in las:
        sites = la.get('Site', [])
        if not isinstance(sites, list):
            sites = [sites]
        for s in sites:
            species = s.get('Species', [])
            if not isinstance(species, list):
                species = [species]
            for sp in species:
                if not isinstance(sp, dict):
                    continue
                band = sp.get('@AirQualityBand')
                if band:
                    bands[band] = bands.get(band, 0) + 1
                idx = sp.get('@AirQualityIndex')
                if idx and str(idx).isdigit():
                    readings.append((int(idx), s.get('@SiteName'), sp.get('@SpeciesDescription'), band))
    if not bands:
        return [], 'no site readings found'
    url = 'https://www.londonair.org.uk/'
    facts = [
        fact(str(sum(v for k, v in bands.items() if k not in ('Low', 'No data'))),
             'Readings above "Low" air quality',
             'London Air Quality Network', url),
        fact(f'{len(las)}', 'Boroughs with a monitor',
             'London Air Quality Network', url),
    ]
    if readings:
        readings.sort(reverse=True)
        idx, site, species, band = readings[0]
        facts.append(fact(f'index {idx} ({band})',
                           f'Worst reading: {species} at {site}',
                           'London Air Quality Network', url))
    return facts, None


# NOTED, NOT BUILT - a candidate for a SEPARATE future vein, not a fix for
# this one. Checked 31 August 2026: TfL's /StopPoint/{id}/Crowding/{line}
# (direction required: inbound/outbound/all) is genuinely documented in
# their own Swagger spec, unlike this vein's live endpoint. It returns
# `trainLoadings` (a plain 1-6 scale, TfL's own words: "1 being 'Very quiet'
# and 6 being 'Exceptionally busy'" - no undocumented mystery, unlike
# percentageOfBaseline) and `passengerFlows` (absolute-looking counts per
# 15-minute time slice, e.g. 4 people at 05:30-05:45 vs 282 at 08:45-09:00
# on the Victoria line at King's Cross - genuinely time-of-day-aware).
# BUT it is STATIC/predicted-typical, not live - "what's normally busy at
# this hour", never "what's happening right now" - so it cannot answer the
# same question this vein tries to and would not fix busiest/quietest's own
# problem. It is also structured per line-segment-and-direction rather than
# one figure per station: King's Cross's Victoria-line entry alone carried
# 2,436 passengerFlows rows and 168 trainLoadings rows across directions and
# stop-pairs, so a station-level card would need real new aggregation, not
# a quick reuse of this vein's shape. Worth a genuinely new vein someday
# ("typically busiest time on the Victoria line at King's Cross: 08:45,
# exceptionally busy") - not attempted here.
def harvest_tfl_crowding():
    readings = []
    failed = []
    for i, (name, naptan) in enumerate(TFL_STATIONS.items()):
        if i > 0 and not TFL_APP_KEY:
            time.sleep(STATION_DELAY)
        d = tfl_get_json(f'https://api.tfl.gov.uk/crowding/{naptan}/Live')
        if not isinstance(d, dict):
            failed.append(name)
            continue
        if d.get('statusCode') == 429:
            failed.append(f'{name} (rate limited)')
            continue
        if not d.get('dataAvailable'):
            failed.append(f'{name} (no data)')
            continue
        readings.append((name, naptan, d['percentageOfBaseline'], d.get('timeLocal')))

    if not readings:
        return [], f'no station returned live data; failed: {failed}'

    # A REAL, working per-station URL, not the templated
    # '.../crowding/{naptanId}/Live' this vein used to hand every fact
    # regardless of which station it was about. Checked 31 August 2026: the
    # literal template string resolves (curl gets HTTP 200), which is worse
    # than a 404 - it silently returns {"dataAvailable":false,
    # "percentageOfBaseline":0,...} for a station that doesn't exist, so a
    # reader clicking through to "see the data" would find something that
    # looks like real output and means nothing. Each fact now links to the
    # actual station it's about.
    def station_url(naptan):
        return f'https://api.tfl.gov.uk/crowding/{naptan}/Live'

    # Surfaced as the card's own footnote (see fact()'s context_note arg
    # and compose.py), never the threaded reply - moved there 31 August
    # 2026 on Chris's call that the reply should carry nothing but a link.
    # Two clauses, answering two separate questions that came from two
    # separate real cards: what "% of baseline" actually MEANS (TfL
    # documents it no further than this - see the methodology thread's own
    # CROWDING card, london_index_methodology.py - so nothing more specific
    # may be claimed here either), and busiest/quietest/most congested OF
    # HOW MANY - a reader has no other way to know this samples 225
    # stations, not all 270 or just a handful. len(readings), not
    # len(TFL_STATIONS), for the second clause: states what was actually
    # sampled THIS run, not the dict's static size, so a run with failures
    # doesn't overclaim.
    context_note = (
        "% of each station's own typical footfall, not a headcount — "
        f"sampled across {len(readings)} of London's 270 Underground stations")
    # "Busiest"/"Quietest" were dropped 31 August 2026: this ranks stations
    # by how far each sits above/below ITS OWN typical level, never by
    # actual crowd size (TfL's live endpoint has no headcount to rank by -
    # see the harvest_river_levels-style note above on what's and isn't
    # available). A quiet suburban station having an unusually active
    # moment beats a genuinely packed interchange sitting at an ordinary
    # 60% of its own much bigger typical crowd - confirmed against a
    # session's worth of real runs, where "Busiest" was Bayswater, Barking,
    # Harlesden, Westbourne Park and Harrow & Wealdstone, never King's
    # Cross, Oxford Circus or Bank. "Busiest" promises absolute crowd size
    # the data can't deliver; "most above normal" says what's actually
    # measured.
    busiest = max(readings, key=lambda r: r[2])
    quietest = min(readings, key=lambda r: r[2])
    facts = [
        fact(pct_of_baseline(busiest[2]), f'Most above normal: {busiest[0]}',
             'TfL live crowding', station_url(busiest[1]), period=busiest[3],
             pair='crowd_gap', context_note=context_note),
        fact(pct_of_baseline(quietest[2]), f'Most below normal: {quietest[0]}',
             'TfL live crowding', station_url(quietest[1]), period=quietest[3],
             pair='crowd_gap', context_note=context_note),
    ]
    # No dead-heat pair for this vein - dropped 31 August 2026. At 225
    # sampled stations a qualifying near-tie exists on nearly every run (see
    # dead_heat()'s 2% relative threshold), which made "coincidence" framing
    # the common case rather than the occasional one it was designed for,
    # and Chris's call after seeing a real rendered card was that it still
    # didn't read well even with an opener naming the tie explicitly. Other
    # veins (river_levels) keep their own dead-heat pair - this is scoped to
    # crowding specifically, not a verdict on the mechanism generally.
    #
    # A second card shape instead: the busiest stations as a ranked list,
    # added the same day. TOP_RANKED_COUNT is 4, not 5, so it fits
    # inside the existing MAX_LINES=4 cap in compose.py without raising a
    # limit shared by every other vein's cards for the sake of this one.
    ranked = sorted(readings, key=lambda r: -r[2])[:TOP_RANKED_COUNT]
    for name, naptan, pct, when in ranked:
        facts.append(fact(pct_of_baseline(pct), name,
                           'TfL live crowding', station_url(naptan), period=when,
                           pair='crowd_top', context_note=context_note))
    if failed:
        facts[0]['note'] = f'{len(failed)} of {len(TFL_STATIONS)} curated stations had no reading: {failed}'
    return facts, None


# The 13 London-based institutions among the 18 DCMS-sponsored museums and
# galleries, matched by exact name (after stripping the table's own
# "[Note N]" markers) rather than derived by excluding the non-London ones —
# so an institution DCMS adds later defaults to NOT counted until reviewed,
# instead of silently sliding into a "London" total because nothing named it
# otherwise. Read from every row of Table 1 on 29-30 August 2026. The 5
# excluded: Museum of Science and Industry in Manchester, National Coal
# Mining Museum (Wakefield), National Museums Liverpool, Royal Armouries
# (Leeds-headquartered, though it also runs galleries inside the Tower of
# London and Fort Nelson in Portsmouth - a genuinely borderline call, kept
# as originally scouted rather than re-litigated here) and Tyne and Wear
# Museums (Newcastle/Sunderland). DCMS's own "Total" row in this table
# covers all 18 nationally (42.0m visits in 2024/25) and is never used here
# for that reason - it is not a London figure.
LONDON_DCMS_MUSEUMS = {
    'British Museum', 'Horniman Museum', 'Imperial War Museums',
    'Museum of the Home', 'National Gallery', 'National Portrait Gallery',
    'Natural History Museum', 'Royal Museums Greenwich',
    'Science Museum Group', "Sir John Soane's Museum", 'Tate Gallery Group',
    'Victoria and Albert Museum', 'Wallace Collection',
}

# The live, direct-download attachment on the GOV.UK statistics page below —
# found 30 August 2026 by reading that page, then confirmed against the file
# already in scratch/ by byte-identical Content-Length (80,187 bytes).
DCMS_MUSEUMS_ODS_URL = (
    'https://assets.publishing.service.gov.uk/media/69e8eb88606c20d412163287/'
    'DCMS_sponsored_museums_and_galleries_annual_performance_indicators_2024_25_tables.ods')


def harvest_dcms_museums():
    try:
        import pandas as pd
    except ImportError:
        return [], 'pandas not installed'

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'dcms_museums.ods'
        result = subprocess.run(
            ['curl', '-sS', '-L', '--max-time', '30', '-o', str(path), DCMS_MUSEUMS_ODS_URL],
            capture_output=True)
        if result.returncode != 0 or not path.exists():
            return [], 'DCMS museums download failed'
        try:
            df = pd.read_excel(path, engine='odf', sheet_name='1', header=None)
        except Exception as e:
            return [], f'DCMS museums sheet parse failed: {e}'

    # Found by content, not a hardcoded row number: DCMS has already broken
    # this table's own row numbering once (a 2010/11 and a 2014/15 column
    # both carry a "[b] break in series" marker), so trust the label over a
    # position.
    header_row = None
    for i in range(len(df)):
        if str(df.iloc[i, 0]).strip() == 'Name of museum or gallery':
            header_row = i
            break
    if header_row is None:
        return [], 'DCMS museums header row not found (sheet layout changed?)'

    headers = [str(c).strip() for c in df.iloc[header_row, :]]
    year_cols = [(i, h) for i, h in enumerate(headers) if re.match(r'^\d{4}/\d{2}', h)]
    if not year_cols:
        return [], 'DCMS museums: no year columns found (sheet layout changed?)'
    year_idx, year_label = year_cols[-1]
    year_label = re.sub(r'\s*\[[a-z]\]\s*$', '', year_label)  # strip a trailing "[b]" break-in-series marker
    year_label = year_label.replace('/', '-')  # DCMS's own "2024/25" -> "2024-25" for the card/opener

    counts = {}
    unpublished = []
    for i in range(header_row + 1, len(df)):
        raw_name = df.iloc[i, 0]
        if not isinstance(raw_name, str):
            continue
        name = re.sub(r'\s*\[Note \d+\]\s*$', '', raw_name).strip()
        if name not in LONDON_DCMS_MUSEUMS:
            continue
        v = df.iloc[i, year_idx]
        if not isinstance(v, (int, float)):
            unpublished.append(name)  # DCMS's own "x = data not published"
            continue
        counts[name] = int(v)

    if len(counts) < 2:
        return [], (f'fewer than 2 London museums with a published {year_label} '
                     f'figure; unpublished: {unpublished}')

    url = ('https://www.gov.uk/government/statistics/'
           'dcms-sponsored-museums-and-galleries-annual-performance-indicators-202425')
    busiest = max(counts.items(), key=lambda kv: kv[1])
    quietest = min(counts.items(), key=lambda kv: kv[1])
    facts = [
        fact(f'{busiest[1]:,}', f'Most visited: {busiest[0]}',
             'DCMS', url, period=year_label, pair='museum_gap'),
        fact(f'{quietest[1]:,}', f'Fewest: {quietest[0]}',
             'DCMS', url, period=year_label, pair='museum_gap'),
        fact(f'{sum(counts.values()):,}', 'All London DCMS museums',
             'DCMS', url, period=year_label),
    ]
    # Dead-heat: two of the curated London museums whose annual visitor
    # count happens to land on nearly the same figure, out of the whole
    # curated set rather than just the busiest/quietest extremes above.
    heat = dead_heat(list(counts.items()))
    if heat:
        name_a, _, name_b, _ = heat
        for name in (name_a, name_b):
            facts.append(fact(f'{counts[name]:,}', name,
                               'DCMS', url, period=year_label, pair='museum_heat'))
    if unpublished:
        facts[0]['note'] = (f'{len(unpublished)} of {len(LONDON_DCMS_MUSEUMS)} curated '
                             f'London museums had no published {year_label} figure: {unpublished}')
    return facts, None


def _annual_station_counts_file():
    """Finds the newest year's TfL Annual Station Counts .xlsx by querying
    the S3 bucket behind crowding.data.tfl.gov.uk directly, rather than
    guessing a URL or hardcoding a year - the site itself is a JS file
    browser with no server-rendered listing, but it fetches this exact
    listing API under the hood (found 31 August 2026 by reading its own
    page source), so this needs no browser. TfL adds a new year's folder
    each August and the filename inside isn't perfectly predictable either
    (checked: "AC2025_AnnualisedEntryExit_public.xlsx", lower-case
    "public"), so both the year and the filename are discovered from the
    listing, never assembled from a pattern. Returns (url, year) or
    (None, None) on any failure - a stale cached year would silently
    under-report growth, so this refuses to fall back to a guessed one."""
    import xml.etree.ElementTree as ET
    ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
    base = 'https://s3-eu-west-1.amazonaws.com/crowding.data.tfl.gov.uk/'

    def list_prefix(prefix):
        body = curl(f'{base}?list-type=2&delimiter=/&prefix={urllib.parse.quote(prefix)}')
        if body is None:
            return None
        try:
            return ET.fromstring(body)
        except ET.ParseError:
            return None

    top = list_prefix('Annual Station Counts/')
    if top is None:
        return None, None
    years = []
    for p in top.findall('s3:CommonPrefixes/s3:Prefix', ns):
        m = re.search(r'/(\d{4})/$', p.text or '')
        if m:
            years.append(int(m.group(1)))
    if not years:
        return None, None
    year = max(years)

    year_listing = list_prefix(f'Annual Station Counts/{year}/')
    if year_listing is None:
        return None, None
    for k in year_listing.findall('s3:Contents/s3:Key', ns):
        if k.text and k.text.lower().endswith('.xlsx'):
            return f'https://crowding.data.tfl.gov.uk/{urllib.parse.quote(k.text)}', year
    return None, None


def _clean_station_usage_name(name):
    """This dataset disambiguates 22 of its 270 Underground stations with a
    trailing mode suffix (e.g. "Waterloo LU", "Paddington TfL") because the
    same physical station also has a separate National Rail row elsewhere
    in the same sheet - safe to drop once already filtered to Mode == 'LU'
    rows only, and confirmed (31 August 2026) not to collide: 270 unique
    names before and after stripping it. Straight apostrophes curled and
    "St." de-abbreviated to match TFL_STATIONS' own convention (only
    "King's Cross St. Pancras" carries one here, checked) - nothing
    downstream curls a fact's label before it reaches alt text."""
    n = re.sub(r'\s+(LU|TfL|LO|DLR)$', '', name).strip()
    n = n.replace('St. ', 'St ')
    return n.replace("'", '’')


def harvest_station_usage():
    try:
        import pandas as pd
    except ImportError:
        return [], 'pandas not installed'

    file_url, year = _annual_station_counts_file()
    if not file_url:
        return [], 'Annual Station Counts file not found (TfL S3 listing changed?)'

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'station_usage.xlsx'
        result = subprocess.run(
            ['curl', '-sS', '-L', '--max-time', '30', '-o', str(path), file_url],
            capture_output=True)
        if result.returncode != 0 or not path.exists():
            return [], 'Annual Station Counts download failed'
        try:
            df = pd.read_excel(path, header=None)
        except Exception as e:
            return [], f'Annual Station Counts parse failed: {e}'

    # Found by content, not a fixed row number - same DCMS lesson: this
    # sheet's own header sits under two title/version rows that have moved
    # before (row 5 this year, nothing here trusts that staying put).
    header_row = None
    for i in range(min(len(df), 20)):
        row = {str(x).strip() for x in df.iloc[i].tolist() if isinstance(x, str)}
        if {'Mode', 'Station', 'Coverage', 'Annualised'} <= row:
            header_row = i
            break
    if header_row is None:
        return [], 'Annual Station Counts header row not found (layout changed?)'

    headers = [str(c).strip() for c in df.iloc[header_row, :]]
    needed = ('Mode', 'Station', 'Coverage', 'Annualised')
    if any(headers.count(h) != 1 for h in needed):
        return [], f'Annual Station Counts: expected columns not found exactly once in {headers}'
    col = {h: headers.index(h) for h in needed}

    # Mode == 'LU' only (this sheet also carries London Overground, DLR and
    # Elizabeth line rows - a genuinely broader "London Index" vein
    # someday, not attempted here). Coverage == 'Station entry/exit' drops
    # the sheet's own cross-reference placeholder rows ("---see LU---" for
    # interchanges counted under a different mode's row, "---station
    # closed---"), which read as real data to a naive numeric coercion.
    usage = {}
    for i in range(header_row + 1, len(df)):
        row = df.iloc[i]
        if str(row.iloc[col['Mode']]).strip() != 'LU':
            continue
        if str(row.iloc[col['Coverage']]).strip() != 'Station entry/exit':
            continue
        v = row.iloc[col['Annualised']]
        if not isinstance(v, (int, float)) or pd.isna(v):
            continue
        name = _clean_station_usage_name(str(row.iloc[col['Station']]).strip())
        usage[name] = round(v)

    if len(usage) < 2:
        return [], f'fewer than 2 usable London Underground stations parsed (got {len(usage)})'

    url = file_url
    # "Entries and exits" is TAPS, not journeys or people: a single return
    # trip through one station taps in and out once each, counted as 2
    # here. Stated plainly rather than left implicit, the same reason
    # tfl_crowding's own context_note spells out "not a headcount" - TfL's
    # own column header literally reads "Annualised En/Ex". First wording
    # ("a return trip counts twice") needed Chris to ask what it meant
    # before it landed - "gate taps, in and out, combined" says the same
    # thing without needing the follow-up question. The year isn't
    # repeated here: it's already on the source-credit line via this
    # fact's own `period` (see _period_credit), so it would be redundant.
    # Kept under MAX_FOOTNOTE_CHARS (140) deliberately - an early, fuller
    # wording ran to 219 and compose.py's truncation cut it off mid-
    # sentence ("...so a r"), caught on the first real dry run. Chris's own
    # wording for this clause was 143 - one word ("the" before "numbers")
    # dropped to land at 139, the minimal trim rather than a rewrite.
    context_note = (
        f"TfL counts across {len(usage)} London Underground stations; entries and "
        "exits are counted separately, so numbers are gate taps, in and out, combined")
    busiest = max(usage.items(), key=lambda kv: kv[1])
    quietest = min(usage.items(), key=lambda kv: kv[1])
    facts = [
        fact(f'{busiest[1]:,}', f'Busiest: {busiest[0]}',
             'TfL Annual Station Counts', url, period=str(year), pair='usage_gap',
             context_note=context_note),
        fact(f'{quietest[1]:,}', f'Quietest: {quietest[0]}',
             'TfL Annual Station Counts', url, period=str(year), pair='usage_gap',
             context_note=context_note),
    ]
    # "Busiest"/"Quietest" are honest here in a way tfl_crowding's never
    # were: this ranks real annual taps, an absolute count, not a
    # percentage of each station's own baseline - so the busiest station
    # really is the one with the most people, not merely the one furthest
    # above its own normal. See HARVESTERS' tfl_crowding comment for why
    # that vein was paused rather than fixed the same way.
    heat = dead_heat(list(usage.items()))
    if heat:
        name_a, _, name_b, _ = heat
        for name in (name_a, name_b):
            facts.append(fact(f'{usage[name]:,}', name,
                               'TfL Annual Station Counts', url, period=str(year),
                               pair='usage_heat', context_note=context_note))
    ranked = sorted(usage.items(), key=lambda kv: -kv[1])[:TOP_RANKED_COUNT]
    for name, count in ranked:
        facts.append(fact(f'{count:,}', name,
                           'TfL Annual Station Counts', url, period=str(year),
                           pair='usage_top', context_note=context_note))
    return facts, None


def _daily_footfall_file():
    """Finds the current TfL Network Demand "StationFootfall" CSV by
    LastModified in the same S3 listing _annual_station_counts_file() uses
    - NOT by parsing a year out of the filename, which isn't a stable
    pattern here (StationFootfall_2019.csv through 2022 are single-year,
    2023 on are "_2024_2025 .csv"-style two-year spans - note the trailing
    space before .csv on the newest two files, confirmed 31 August 2026).
    Returns a url or None on any failure."""
    import xml.etree.ElementTree as ET
    ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
    body = curl('https://s3-eu-west-1.amazonaws.com/crowding.data.tfl.gov.uk/'
                '?list-type=2&prefix=Network%20Demand/')
    if body is None:
        return None
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    candidates = []
    for c in root.findall('s3:Contents', ns):
        key_el, mod_el = c.find('s3:Key', ns), c.find('s3:LastModified', ns)
        if key_el is None or mod_el is None:
            continue
        if 'StationFootfall' in (key_el.text or ''):
            candidates.append((mod_el.text, key_el.text))
    if not candidates:
        return None
    candidates.sort()
    _, key = candidates[-1]
    return f'https://crowding.data.tfl.gov.uk/{urllib.parse.quote(key)}'


# This CSV drops most possessive apostrophes outright (checked 31 August
# 2026 against all 437 distinct names across the file's full history:
# "Kings Cross St Pancras", "Earls Court", "Queens Park" etc.) except one -
# "St James's Park" keeps its own - so a blanket "add an apostrophe before
# a trailing s" rule would both miss real cases and double up that one
# correct case. An explicit map, not a heuristic: every station this file
# spells without a needed apostrophe, checked by hand against how the
# other two TfL sources in this file spell the same place.
FOOTFALL_NAME_FIXES = {
    'Earls Court': 'Earl’s Court',
    'Kings Cross St Pancras': 'King’s Cross St Pancras',
    'Queens Park': 'Queen’s Park',
    'Queens Rd Peckham': 'Queen’s Road Peckham',
    'Regents Park': 'Regent’s Park',
    'Shepherds Bush': 'Shepherd’s Bush',
    'Shepherds Bush Market': 'Shepherd’s Bush Market',
    'St Johns Wood': 'St John’s Wood',
    'St Pauls': 'St Paul’s',
}

# Mode-suffix codes this file appends to some (not all - checked, the
# suffixing itself is inconsistent) non-Underground stations. Spelled out
# for a reader who has no reason to know "NR"/"LO" - DLR and Elizabeth
# Line are left as-is, already clear as written.
FOOTFALL_SUFFIX_FIXES = {' NR': ' National Rail', ' LO': ' Overground'}


def _clean_footfall_name(name):
    n = FOOTFALL_NAME_FIXES.get(name, name)
    for old, new in FOOTFALL_SUFFIX_FIXES.items():
        if n.endswith(old):
            n = n[:-len(old)] + new
    return n.replace("'", '’')


# How many trailing days of the same station's own history must be present
# before its latest-day figure can be judged an outlier at all - guards
# against a station with a real 7-day gap (new to the file, or a long
# closure) reading as "no history" rather than being silently skipped.
FOOTFALL_ANOMALY_MIN_TRAILING_DAYS = 4
# A station reading below this fraction of its own trailing average is
# treated as a likely data gap, not a real quiet day. Calibrated 31 August
# 2026 against a genuine live case: East Putney, Parsons Green and Putney
# Bridge (three consecutive District line stations) all collapsed to under
# 1% of their own weekly average on the same day - almost certainly a
# reader/gate fault or closure on that stretch, not empty stations. A
# natural weekend dip on a normal day was ~50% of the weekday average in
# the same window, well clear of this floor.
FOOTFALL_ANOMALY_FRACTION = 0.1


def harvest_daily_footfall():
    import csv
    from collections import defaultdict

    file_url = _daily_footfall_file()
    if not file_url:
        return [], 'Network Demand footfall file not found (TfL S3 listing changed?)'

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'footfall.csv'
        result = subprocess.run(
            ['curl', '-sS', '-L', '--max-time', '60', '-o', str(path), file_url],
            capture_output=True)
        if result.returncode != 0 or not path.exists():
            return [], 'Network Demand footfall download failed'
        rows = []
        try:
            with open(path, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                required = {'TravelDate', 'Station', 'EntryTapCount', 'ExitTapCount'}
                if not reader.fieldnames or not required <= set(reader.fieldnames):
                    return [], f'Network Demand footfall: unexpected columns {reader.fieldnames}'
                rows = list(reader)
        except Exception as e:
            return [], f'Network Demand footfall parse failed: {e}'

    if not rows:
        return [], 'Network Demand footfall: file was empty'

    # Station identity is read BEFORE cleaning, so two raw names that clean
    # to the same thing (none currently do - checked) would still merge
    # correctly rather than silently overwriting one with the other.
    by_station_date = defaultdict(dict)
    for r in rows:
        try:
            total = int(r['EntryTapCount']) + int(r['ExitTapCount'])
        except (ValueError, TypeError):
            continue
        by_station_date[r['Station'].strip()][r['TravelDate']] = total

    dates = sorted({r['TravelDate'] for r in rows})
    if not dates:
        return [], 'Network Demand footfall: no usable dates parsed'
    latest = dates[-1]
    trailing = dates[-8:-1]

    footfall = {}
    anomalies = []
    for station, by_date in by_station_date.items():
        if latest not in by_date:
            continue
        today = by_date[latest]
        hist = [by_date[d] for d in trailing if d in by_date]
        if len(hist) >= FOOTFALL_ANOMALY_MIN_TRAILING_DAYS:
            avg = sum(hist) / len(hist)
            if avg > 0 and today < FOOTFALL_ANOMALY_FRACTION * avg:
                anomalies.append(f'{station} ({today:,} vs a {round(avg):,} trailing average)')
                continue
        footfall[_clean_footfall_name(station)] = today

    if len(footfall) < 2:
        return [], f'fewer than 2 usable stations parsed for {latest} (after excluding likely data gaps)'

    date_obj = datetime.strptime(latest, '%Y%m%d')
    period_str = date_obj.strftime('%Y-%m-%d')

    url = file_url
    # Deliberately says WHICH day, not how many days behind today - a
    # fixed lag stated in the text goes stale the moment the pipeline is
    # ever a day later or earlier, and "X days behind" reads as
    # increasingly wrong on a delayed run in exactly the way a stated date
    # doesn't (same reasoning seoul-transit-art's own daily page uses for
    # its own lag).
    # "The entire TfL network" was judged to say enough on its own - Chris's
    # call, 31 August 2026 - without spelling out every mode by name.
    context_note = (
        "Counts from across the entire TfL network; entries and exits are counted "
        "separately, so the numbers are gate taps, in and out, combined")
    busiest = max(footfall.items(), key=lambda kv: kv[1])
    quietest = min(footfall.items(), key=lambda kv: kv[1])
    facts = [
        fact(f'{busiest[1]:,}', f'Busiest: {busiest[0]}',
             'TfL Network Demand', url, period=period_str, pair='footfall_gap',
             context_note=context_note),
        fact(f'{quietest[1]:,}', f'Quietest: {quietest[0]}',
             'TfL Network Demand', url, period=period_str, pair='footfall_gap',
             context_note=context_note),
    ]
    # No dead-heat pair for this vein - dropped 31 August 2026, Chris's
    # call, and checked against the last 15 real days before removing:
    # dead_heat() found a qualifying tie on EVERY one of them, no
    # exceptions, the same "coincidence is the constant case, not the rare
    # one" failure tfl_crowding's own dead-heat had. Worse here: several of
    # those 15 were two stations tied at 1-2 total taps each ("Alperton 1
    # vs Arnos Grove 1", 19 August) - not a genuine near-tie, almost
    # certainly a data gap the per-station trailing-average guard above
    # can't catch, since it only compares a station against ITS OWN
    # history, not against whether 1 tap at a major interchange is
    # plausible at all. usage_heat on the annual station_usage vein is
    # unaffected - annual totals in the millions produce genuinely rare
    # coincidences, this vein's day-to-day range does not.
    ranked = sorted(footfall.items(), key=lambda kv: -kv[1])[:TOP_RANKED_COUNT]
    for name, count in ranked:
        facts.append(fact(f'{count:,}', name,
                           'TfL Network Demand', url, period=period_str,
                           pair='footfall_top', context_note=context_note))
    if anomalies:
        facts[0]['note'] = (f'{len(anomalies)} station(s) excluded as likely data gaps, '
                             f'under {FOOTFALL_ANOMALY_FRACTION:.0%} of their own trailing '
                             f'7-day average: {anomalies}')
    return facts, None



# --- Stop and search (data.police.uk, Metropolitan Police, monthly) --------
STOPS_NOTE = 'Metropolitan Police, whole force area'


def stop_search_facts(records, ym, url):
    """One month of the Met's stop and search, from data.police.uk's own
    records: how many, how many ended in arrest, how many in no further
    action, how many were for drugs. All four share the pair "stops_all"
    (see SELECT_PROMPT's "_all" rule): any 2 to 4 make a card, under a fixed
    opener."""
    total = len(records)
    arrests = sum(1 for r in records if (r.get('outcome') or '') == 'Arrest')
    nfa = sum(1 for r in records if (r.get('outcome') or '').lower().startswith('a no further action'))
    drugs = sum(1 for r in records if (r.get('object_of_search') or '') == 'Controlled drugs')
    weapons = sum(1 for r in records if (r.get('object_of_search') or '') == 'Offensive weapons')
    mk = lambda v, label: fact(f'{v:,}', label, 'data.police.uk', url, period=ym,
                               pair='stops_all', context_note=STOPS_NOTE)
    return [mk(total, 'Searches'), mk(arrests, 'Ended in arrest'),
            mk(nfa, 'No further action'), mk(drugs, 'For drugs'),
            mk(weapons, 'For weapons')]


def harvest_stop_search():
    this_month = datetime.now(timezone.utc).strftime('%Y-%m')
    for back in range(1, 5):
        ym = _shift_month(this_month, back)
        url = f'https://data.police.uk/api/stops-force?force=metropolitan&date={ym}'
        d = get_json(url, timeout=60)
        if isinstance(d, list) and len(d) >= 1000:
            # The Met records five figures of searches a month; a short
            # list is a month still being loaded, not a quiet month.
            return stop_search_facts(d, ym, url), None
    return [], 'no populated stop-and-search month in the last 4 tried'


# --- House prices (HM Land Registry, UK House Price Index, monthly) --------
# The 32 boroughs plus the City, as the index's own region slugs. Four were
# verified live on 12 September 2026 (camden, kensington-and-chelsea,
# city-of-westminster, barking-and-dagenham); the rest follow the same
# lowercase-hyphenated local-authority naming and are checked on every run:
# a slug that answers nothing is logged, and under HPI_MIN_BOROUGHS answering
# the borough facts are withheld rather than ranking a partial London.
HPI_BOROUGHS = {
    'Barking and Dagenham': 'barking-and-dagenham', 'Barnet': 'barnet',
    'Bexley': 'bexley', 'Brent': 'brent', 'Bromley': 'bromley', 'Camden': 'camden',
    'City of London': 'city-of-london', 'Croydon': 'croydon', 'Ealing': 'ealing',
    'Enfield': 'enfield', 'Greenwich': 'greenwich', 'Hackney': 'hackney',
    'Hammersmith and Fulham': 'hammersmith-and-fulham', 'Haringey': 'haringey',
    'Harrow': 'harrow', 'Havering': 'havering', 'Hillingdon': 'hillingdon',
    'Hounslow': 'hounslow', 'Islington': 'islington',
    'Kensington and Chelsea': 'kensington-and-chelsea',
    'Kingston upon Thames': 'kingston-upon-thames', 'Lambeth': 'lambeth',
    'Lewisham': 'lewisham', 'Merton': 'merton', 'Newham': 'newham',
    'Redbridge': 'redbridge', 'Richmond upon Thames': 'richmond-upon-thames',
    'Southwark': 'southwark', 'Sutton': 'sutton', 'Tower Hamlets': 'tower-hamlets',
    'Waltham Forest': 'waltham-forest', 'Wandsworth': 'wandsworth',
    'Westminster': 'city-of-westminster',
}
HPI_MIN_BOROUGHS = 30
HPI_TOP_N = 4
HPI_SOURCE = 'HM Land Registry (UK House Price Index)'
HPI_PAGE = 'https://landregistry.data.gov.uk/app/ukhpi'
HPI_NOTE = 'Land Registry index averages, all property types; recent months are provisional'


def _hpi_month(slug, ym):
    d = get_json(f'https://landregistry.data.gov.uk/data/ukhpi/region/{slug}/month/{ym}.json')
    if not isinstance(d, dict):
        return None
    topic = (d.get('result') or {}).get('primaryTopic') if isinstance(d.get('result'), dict) else None
    if isinstance(topic, dict) and isinstance(topic.get('averagePrice'), (int, float)):
        return topic
    return None


def _pounds(v):
    return f'£{int(round(v)):,}'


def _signed_pct(v):
    """A published percentage as a card value, one decimal, typographic
    minus: "+1.0%", "−2.5%"."""
    if v is None:
        return None
    return (f'+{v:.1f}%' if v > 0 else f'−{abs(v):.1f}%' if v < 0 else '0.0%')


def house_price_facts(london, boroughs, ym, url=HPI_PAGE):
    """`london` is the London region's month record, `boroughs` a dict of
    borough name -> month record (however many answered). Shapes:
      - unpaired: London's average price, its change on a year earlier and
        on the month
      - "hp_types_gap": the average flat against the average detached house
      - "hp_gap": the most and least expensive boroughs
      - "hp_top": the HPI_TOP_N most expensive boroughs, ranked
      - "hp_change": the biggest annual rise and the biggest annual fall (or
        smallest rise) by borough
    The borough shapes appear only when at least HPI_MIN_BOROUGHS answered."""
    mk = lambda v, label, pair=None: fact(v, label, HPI_SOURCE, url, period=ym,
                                          pair=pair, context_note=HPI_NOTE)
    facts = [mk(_pounds(london['averagePrice']), 'Average price, London')]
    annual = _signed_pct(london.get('percentageAnnualChange'))
    if annual:
        facts.append(mk(annual, 'Change on a year earlier'))
    monthly = _signed_pct(london.get('percentageChange'))
    if monthly:
        facts.append(mk(monthly, 'Change on the month'))
    flat, det = london.get('averagePriceFlatMaisonette'), london.get('averagePriceDetached')
    if flat and det:
        facts.append(mk(_pounds(flat), 'Average flat, London', 'hp_types_gap'))
        facts.append(mk(_pounds(det), 'Average detached house, London', 'hp_types_gap'))
    if len(boroughs) >= HPI_MIN_BOROUGHS:
        ranked = sorted(boroughs.items(), key=lambda kv: -kv[1]['averagePrice'])
        facts.append(mk(_pounds(ranked[0][1]['averagePrice']),
                        f'Most expensive: {ranked[0][0]}', 'hp_gap'))
        facts.append(mk(_pounds(ranked[-1][1]['averagePrice']),
                        f'Least expensive: {ranked[-1][0]}', 'hp_gap'))
        for name, rec in ranked[:HPI_TOP_N]:
            facts.append(mk(_pounds(rec['averagePrice']), name, 'hp_top'))
        changes = [(name, rec['percentageAnnualChange']) for name, rec in boroughs.items()
                   if isinstance(rec.get('percentageAnnualChange'), (int, float))]
        if len(changes) >= HPI_MIN_BOROUGHS:
            changes.sort(key=lambda t: -t[1])
            (rise_name, rise), (fall_name, fall) = changes[0], changes[-1]
            facts.append(mk(_signed_pct(rise), f'Biggest rise on a year earlier: {rise_name}',
                            'hp_change'))
            fall_label = 'Biggest fall' if fall < 0 else 'Smallest rise'
            facts.append(mk(_signed_pct(fall), f'{fall_label} on a year earlier: {fall_name}',
                            'hp_change'))
    return facts


def harvest_house_prices():
    this_month = datetime.now(timezone.utc).strftime('%Y-%m')
    london = ym = None
    for back in range(1, 6):
        ym = _shift_month(this_month, back)
        london = _hpi_month('london', ym)
        if london:
            break
    if not london:
        return [], 'no published UK HPI month for London in the last 5 tried'
    boroughs = {}
    failed = []
    for name, slug in HPI_BOROUGHS.items():
        rec = _hpi_month(slug, ym)
        if rec:
            boroughs[name] = rec
        else:
            failed.append(name)
    facts = house_price_facts(london, boroughs, ym)
    if failed:
        facts[0]['note'] = (f'{len(failed)} of {len(HPI_BOROUGHS)} boroughs did not answer '
                            f'for {ym}: {failed}')
    return facts, None


# --- Roadworks and disruptions on TfL roads (live) -------------------------
ROADS_URL = 'https://api.tfl.gov.uk/Road/all/Disruption'
ROADS_PAGE = 'https://tfl.gov.uk/traffic/status'
ROADS_NOTE = 'The Transport for London Road Network (red routes), not every London street'
SERIOUS = {'moderate', 'serious', 'severe'}


def road_facts(items, url=ROADS_PAGE):
    """Live: everything TfL currently lists as a disruption on its own
    roads, how many it rates moderate or worse, and how many are planned
    works. Pair "roads_all" (see SELECT_PROMPT's "_all" rule)."""
    total = len(items)
    serious = sum(1 for i in items if (i.get('severity') or '').lower() in SERIOUS)
    works = sum(1 for i in items if (i.get('category') or '') == 'Works')
    mk = lambda v, label: fact(f'{v:,}', label, 'TfL Road disruptions', url,
                               pair='roads_all', context_note=ROADS_NOTE)
    return [mk(total, 'Disruptions on TfL roads'), mk(serious, 'Moderate or worse'),
            mk(works, 'Planned roadworks')]


def harvest_road_works():
    d = tfl_get_json(ROADS_URL)
    if not isinstance(d, list):
        return [], 'Road disruption fetch failed'
    return road_facts(d), None


# --- Animal rescues by the London Fire Brigade (London Datastore, monthly) --
ANIMALS_URL = ('https://data.london.gov.uk/download/2ogkn/01007433-55c2-4b8a-b799-626d9e3bc284/'
               'Animal%20Rescue%20incidents%20attended%20by%20LFB%20from%20Jan%202009.csv.xlsx')
ANIMALS_PAGE = 'https://data.london.gov.uk/dataset/animal-rescue-incidents-attended-by-lfb'
ANIMALS_SOURCE = 'London Datastore (LFB animal rescues)'
ANIMALS_NOTE = 'London Fire Brigade callouts to animals trapped or in distress'
ANIMALS_TOP_N = 4
ANIMALS_MIN_ROWS = 10
# The file's AnimalGroupParent is singular ("Cat", "Bird"); a count wants
# the plural. Anything not listed (the file's "Unknown - ..." groups among
# them) is left out of the ranked list rather than pluralised by rule.
ANIMAL_PLURALS = {
    'Cat': 'Cats', 'Dog': 'Dogs', 'Bird': 'Birds', 'Fox': 'Foxes', 'Horse': 'Horses',
    'Deer': 'Deer', 'Squirrel': 'Squirrels', 'Rabbit': 'Rabbits', 'Hamster': 'Hamsters',
    'Cow': 'Cows', 'Sheep': 'Sheep', 'Snake': 'Snakes', 'Ferret': 'Ferrets', 'Goat': 'Goats',
    'Hedgehog': 'Hedgehogs', 'Lizard': 'Lizards', 'Tortoise': 'Tortoises', 'Fish': 'Fish',
    'Bull': 'Bulls', 'Pigeon': 'Pigeons', 'Lamb': 'Lambs', 'Budgie': 'Budgies', 'Rat': 'Rats',
}


def animal_facts(rows, ym, url=ANIMALS_PAGE):
    """`rows` are dicts for one month (keys as the file's header names).
    Shapes: the month's total and the borough with the most (unpaired), the
    ANIMALS_TOP_N most-rescued kinds of animal ranked ("animals_top"), and
    the brigade's own notional cost of it all (unpaired)."""
    mk = lambda v, label, pair=None: fact(v, label, ANIMALS_SOURCE, url, period=ym,
                                          pair=pair, context_note=ANIMALS_NOTE)
    facts = [mk(f'{len(rows):,}', 'Animals rescued')]
    boroughs = {}
    kinds = {}
    cost = 0.0
    for r in rows:
        b = (r.get('Borough') or '').strip()
        if b:
            boroughs[b] = boroughs.get(b, 0) + 1
        k = (r.get('AnimalGroupParent') or '').strip()
        if k in ANIMAL_PLURALS:
            kinds[k] = kinds.get(k, 0) + 1
        c = r.get('IncidentNotionalCost(£)')
        if isinstance(c, (int, float)):
            cost += c
    if boroughs:
        name, n = max(boroughs.items(), key=lambda kv: kv[1])
        facts.append(mk(f'{n:,}', f'Most rescues: {name.title()}'))
    for k, n in sorted(kinds.items(), key=lambda kv: -kv[1])[:ANIMALS_TOP_N]:
        facts.append(mk(f'{n:,}', ANIMAL_PLURALS[k], 'animals_top'))
    if cost:
        facts.append(mk(_pounds(cost), 'Notional cost to the brigade'))
    return facts


def harvest_lfb_animals():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'animals.xlsx'
        result = subprocess.run(['curl', '-sS', '-L', '--max-time', '60', '-o', str(path), ANIMALS_URL],
                                capture_output=True)
        if result.returncode != 0 or not path.exists():
            return [], 'animal-rescue download failed'
        try:
            import openpyxl
        except ImportError:
            return [], 'openpyxl not installed'
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        header = [str(h).strip() if h is not None else '' for h in next(it)]
        if 'DateTimeOfCall' not in header or 'AnimalGroupParent' not in header:
            return [], f'animal-rescue sheet header changed: {header[:8]}'
        by_month = {}
        for row in it:
            rec = dict(zip(header, row))
            when = rec.get('DateTimeOfCall')
            if not isinstance(when, datetime):
                continue
            by_month.setdefault(when.strftime('%Y-%m'), []).append(rec)
    # The newest month that is not the one we are in: the file is a monthly
    # drop of whole months, and a partial month would read as a quiet one.
    this_month = datetime.now(timezone.utc).strftime('%Y-%m')
    months = sorted(m for m in by_month if m < this_month)
    if not months:
        return [], 'no complete month in the animal-rescue file'
    ym = months[-1]
    rows = by_month[ym]
    if len(rows) < ANIMALS_MIN_ROWS:
        return [], f'only {len(rows)} animal rescues in {ym}; refusing a partial month'
    return animal_facts(rows, ym), None



# --- National Rail departures from London's termini (live, RDM LDBWS) ------
# Rail Data Marketplace's Live Departure Board (publisher Rail Delivery
# Group, price 0, licence: attribution required, derived facts may be
# published). Registration approved and the subscription activated on
# 1 September 2026 (the emails are in the iCloud account); the consumer key
# went into the Keychain on 12 September, the day this vein was built.
# The 13 termini were each verified live by the API's own locationName,
# not recalled. Blackfriars is a through station and is left out on purpose.
RAIL_TERMINI = {
    'Paddington': 'PAD', 'King’s Cross': 'KGX', 'Euston': 'EUS', 'Waterloo': 'WAT',
    'Victoria': 'VIC', 'Liverpool Street': 'LST', 'London Bridge': 'LBG',
    'St Pancras': 'STP', 'Charing Cross': 'CHX', 'Cannon Street': 'CST',
    'Fenchurch Street': 'FST', 'Marylebone': 'MYB', 'Moorgate': 'MOG',
}
RAIL_API = ('https://api1.raildata.org.uk/1010-live-departure-board-dep1_2/LDBWS/api/'
            '20220120/GetDepartureBoard/{crs}?numRows=150&timeWindow={window}&timeOffset=0')
RAIL_WINDOW_MIN = 60
RAIL_SOURCE = 'National Rail (Rail Delivery Group)'
RAIL_PAGE = 'https://www.nationalrail.co.uk/'
# "Stations", not "termini", on the card and in this note: Chris's wording,
# 12 September 2026, since termini is railway jargon to most readers.
# "Departing", never "due": Chris read "Trains due within the hour" as
# arrivals (12 September 2026), and the board is GetDepartureBoard.
RAIL_NOTE = (f'National Rail departures in the next {RAIL_WINDOW_MIN} minutes from '
             f'{len(RAIL_TERMINI)} of London’s main stations, as on the live boards')
RAIL_TOP_N = 4
# Under this many departures across every terminus the boards are the
# small hours (9 at 1:36 a.m. on 12 September 2026), not a city, and no
# card is made. Under RAIL_MIN_STATIONS answering, a partial London is not
# ranked at all.
RAIL_MIN_DEPARTURES = 20
RAIL_MIN_STATIONS = 10


def _rdm_key():
    r = subprocess.run(['security', 'find-generic-password', '-a', 'london-index',
                        '-s', 'rdm-ldbws-key', '-w'], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def get_json_with_headers(url, headers, timeout=25):
    cmd = ['curl', '-sS', '--max-time', str(timeout)]
    for k, v in headers.items():
        cmd += ['-H', f'{k}: {v}']
    result = subprocess.run(cmd + [url], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        return None


def classify_departure(svc):
    """'cancelled', 'late', 'on time' or 'other', from the board's own etd:
    "On time", "Cancelled", "Delayed" (no estimate), or an estimated time
    that differs from the scheduled one. An etd equal to the std is on
    time. Anything else ("No report", an empty field) is counted in the
    total and nowhere else."""
    etd = (svc.get('etd') or '').strip()
    if svc.get('isCancelled') or etd == 'Cancelled':
        return 'cancelled'
    if etd == 'On time' or (etd and etd == (svc.get('std') or '').strip()):
        return 'on time'
    if etd == 'Delayed' or re.fullmatch(r'\d\d:\d\d', etd):
        return 'late'
    return 'other'


def rail_facts(boards, url=RAIL_PAGE):
    """`boards` maps terminus name -> list of train services (the board's
    trainServices). Two shapes:
      - "rail_all": trains departing within the hour, on time, running late,
        cancelled (any 2 to 4, fixed opener)
      - "rail_top": the RAIL_TOP_N termini with the most departures,
        ranked"""
    mk = lambda v, label, pair: fact(f'{v:,}', label, RAIL_SOURCE, url, pair=pair,
                                     context_note=RAIL_NOTE)
    counts = {'on time': 0, 'late': 0, 'cancelled': 0, 'other': 0}
    per = {}
    for name, services in boards.items():
        per[name] = len(services)
        for svc in services:
            counts[classify_departure(svc)] += 1
    total = sum(per.values())
    facts = [mk(total, 'Departing within the hour', 'rail_all'),
             mk(counts['on time'], 'On time', 'rail_all'),
             mk(counts['late'], 'Running late', 'rail_all'),
             mk(counts['cancelled'], 'Cancelled', 'rail_all')]
    # A ranked "busiest" list never carries a station with nothing due: at
    # 1:43 a.m. on 12 September 2026 a render bypassing the floor showed
    # King's Cross and Euston at 0 in third and fourth place. The group is
    # made only when RAIL_TOP_N stations have at least one train due.
    busy = [(name, n) for name, n in sorted(per.items(), key=lambda kv: -kv[1]) if n > 0]
    if len(busy) >= RAIL_TOP_N:
        for name, n in busy[:RAIL_TOP_N]:
            facts.append(mk(n, name, 'rail_top'))
    return facts


def harvest_rail_departures():
    key = _rdm_key()
    if not key:
        return [], 'no Rail Data Marketplace key in Keychain (london-index / rdm-ldbws-key)'
    boards = {}
    failed = []
    for name, crs in RAIL_TERMINI.items():
        d = get_json_with_headers(RAIL_API.format(crs=crs, window=RAIL_WINDOW_MIN),
                                  {'x-apikey': key, 'Accept': 'application/json'})
        if not isinstance(d, dict) or d.get('crs') != crs or not d.get('areServicesAvailable', True):
            failed.append(name)
            continue
        boards[name] = d.get('trainServices') or []
    if len(boards) < RAIL_MIN_STATIONS:
        return [], f'only {len(boards)} of {len(RAIL_TERMINI)} termini answered; failed: {failed}'
    total = sum(len(v) for v in boards.values())
    if total < RAIL_MIN_DEPARTURES:
        return [], f'only {total} departures due across the termini; boards too quiet for a card'
    facts = rail_facts(boards)
    if failed:
        facts[0]['note'] = f'{len(failed)} of {len(RAIL_TERMINI)} termini unusable: {failed}'
    return facts, None

HARVESTERS = {
    'tfl_bikes': harvest_tfl_bikes,
    # tfl_crowding PAUSED 31 August 2026, Chris's call: no more Tube posts
    # until there's a genuinely meaningful statistic to build one from.
    # Wording/labelling was fixed the same day (honest "most above/below
    # normal" labels, a real per-station link, an actual explanation on the
    # card, a rounding fix for "0%") - none of that reaches the underlying
    # problem, which is that percentageOfBaseline is relative-to-itself and
    # has no absolute headcount behind it, so "busiest" can never mean what
    # it sounds like it means from this data. See harvest_tfl_crowding()'s
    # own comments for what was tried. Replaced the same day by
    # station_usage below - real annual taps, an absolute count "busiest"
    # can actually mean - rather than fixed in place. Commented out rather
    # than deleted: the function, its FIXED_OPENERS entries in select.py
    # and every fix made to it today are untouched, in case a live vein is
    # ever worth having again. Excluded from build_pool() this way (not a
    # prompt instruction) so nothing relies on the model choosing not to
    # pick it.
    # 'tfl_crowding': harvest_tfl_crowding,
    'station_usage': harvest_station_usage,
    'daily_footfall': harvest_daily_footfall,
    'flood': harvest_flood,
    'river_levels': harvest_river_levels,
    'police': harvest_police,
    'police_boroughs': harvest_police_boroughs,
    'cycle_hires': harvest_cycle_hires,
    'laqn': harvest_laqn,
    'dcms_museums': harvest_dcms_museums,
    # Added 12 September 2026, the morning after the same crime card went
    # out twice in five hours: four veins whose figures change on their own
    # cadence, none needing a key. See each harvester's own comment.
    'stop_search': harvest_stop_search,
    'house_prices': harvest_house_prices,
    'road_works': harvest_road_works,
    'lfb_animals': harvest_lfb_animals,
    'rail_departures': harvest_rail_departures,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--source', choices=sorted(HARVESTERS), help='one source only')
    args = ap.parse_args()

    keys = [args.source] if args.source else sorted(HARVESTERS)
    pool = []
    errors = {}
    for key in keys:
        facts, err = HARVESTERS[key]()
        if err:
            errors[key] = err
        for f in facts:
            f['vein'] = key
            pool.append(f)

    print(json.dumps({'harvested_at': None, 'pool': pool, 'errors': errors}, indent=2))
    if errors:
        print(f'\n{len(errors)} source(s) failed: {list(errors)}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
