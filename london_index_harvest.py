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
  police_boroughs - the same data.police.uk feed for all 33 boroughs as
                  whole boroughs (its poly query, with the ONS outlines the
                  map draws), cached by month; eight one-mile town-hall
                  samples until 12 September 2026.
  police_spotlight - the same whole-borough counts, one borough per card,
                  least recently featured first: its count, most common
                  category, change on the month and rank among the 33. Added 12 September 2026 because a ranking of any set
                  of boroughs is static; a place is not.
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
  house_price_spotlight - the same HPI boroughs, one per card, least
                  recently featured first: its own average price, change
                  on the year and the month, and rank among the boroughs
                  that answered - the choropleth's second vein, added
                  14 September 2026, same shape as police_spotlight.
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
  rail_station  - the same boards, one station per card, least recently
                  featured first: departing, on time, late, cancelled and
                  the destination with the most trains. Live.
  river_gauge   - the same six gauges, one per card, least recently featured
                  first: level now, its typical low and high, and where in
                  that range it sits. Live. Both added 12 September 2026.
  reservoirs, tfl_journeys, congestion_charge, police_strength, arrests,
  unemployment, lift_releases - seven London Datastore series added
                  12 September 2026, each a small CSV or XLSX the Datastore
                  itself serves: reservoir levels (daily), TfL journeys by
                  mode (four-weekly), vehicles in the Congestion Charge zone
                  (monthly), Met headcount (monthly), arrests (monthly),
                  unemployment London against the UK (rolling quarter) and
                  people freed from lifts by the fire brigade (monthly). See
                  the section above HARVESTERS.
  events        - Ticketmaster's Discovery API: what is on sale in London for
                  the next seven days, by segment, plus the next 24 hours
                  and 30 days. Live. Key in Keychain (london-index /
                  ticketmaster-api-key). Added 12 September 2026. The
                  week's listings are also paged for the busiest day and
                  the venues with the most on sale.
  museum_spotlight - the same DCMS release, one of the 13 London museums per
                  card, least recently featured first: visitors, change on
                  the year before, ten years earlier, and for the same year
                  overseas visitors, under-16s, website visits, the share
                  who would recommend a visit and admissions income.
  west_end      - the Society of London Theatre and UK Theatre's annual
                  report: the West End's attendances, box office, change on
                  the year, performances, occupancy and the share of tickets
                  over £250. Transcribed, not parsed (see WEST_END_REPORTS);
                  posts once a year. Added 19 September 2026.
  london_cinema - the BFI Statistical Yearbook's exhibition tables, the
                  London row: admissions, admissions per head, average
                  ticket price, screens, cinemas and share of UK screens.
                  ITV's London region, not Greater London; yearly, two
                  years behind. Added 19 September 2026.
  west_end_shows - SOLT's own "Longest-running shows in West End History"
                  list (solt.co.uk/data-and-research), the productions
                  table: the top four by performances, a running show's
                  count a floor. Updated by SOLT each January on the
                  evidence of one date. Added 20 September 2026.

Usage:
    python3 london_index_harvest.py            # pool as pretty JSON
    python3 london_index_harvest.py --source tfl_bikes
"""

import argparse
import json
import re
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

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


def fact(value, label, source, url, period=None, pair=None, context_note=None,
         dateline_lead=None, fixed_opener=None, map_pin=None, dateline_text=None,
         map_zone=None, emoji=None):
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
    alone wasn't the whole gap.

    `dateline_lead` is the qualifier that rides the card's SECOND line, ahead
    of the date ("Within a mile of each town hall, July 2026"), Seoul Index's
    own convention for its ranked cards and Chris's call for this account on
    12 September 2026 ("move some of the footnote description into the
    second line"). The footnote then keeps only what is left: the source or
    the sample. compose() takes the first pick's lead.

    `fixed_opener` ({'emoji', 'text'}) is a title Python sets because it has
    to name something only Python knows, such as the spotlight borough;
    select() uses it when every pick carries the same one, ahead of the
    FIXED_OPENERS table and the model's own wording.

    `map_pin` ({'name', 'lat', 'lng'}) asks london_index_post.py for a
    threaded map reply (london_index_card.render_borough_map) with that
    borough highlighted and a one-mile circle at those coordinates.

    `dateline_text` is the second line spelled out in full, for a period
    that is neither a calendar month nor a day: TfL's four-week reporting
    periods ("Four weeks to 25 July 2026") and the ONS rolling quarter
    ("April to June 2026"). compose() uses it verbatim, with any
    dateline_lead in front, when every pick carries the same one.

    `map_zone` names a stored boundary (only 'congestion_charge_zone' so
    far) for a threaded map reply drawn by london_index_card.render_zone_map.

    `emoji` puts a leading icon on this fact's own row (london_index_card's
    per-line {'emoji': ...}), left None for every ordinary index-card vein
    per the card's own design note — repeating an icon down a column of
    otherwise-uniform rows read as clutter and was dropped. The animals_top
    rows are the one exception so far: each row names a different species,
    so a per-row icon identifies it rather than merely decorating it, the
    same reasoning behind Seoul Index's own rescue card carrying one per
    species line."""
    return {'value': value, 'label': label, 'source': source, 'url': url,
            'period': period, 'pair': pair, 'context_note': context_note,
            'dateline_lead': dateline_lead, 'fixed_opener': fixed_opener,
            'map_pin': map_pin, 'dateline_text': dateline_text, 'map_zone': map_zone,
            'emoji': emoji}


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


_RIVER_MEMO = {}


def _river_readings():
    """[(name, value, low, high, pct, when)], failed: every curated gauge's
    latest level against its own published typical range, fetched once per
    process for river_levels and river_gauge both."""
    if 'readings' in _RIVER_MEMO:
        return _RIVER_MEMO['readings']
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
    _RIVER_MEMO['readings'] = (readings, failed)
    return readings, failed


# --- River gauge spotlight: one gauge against its own range -----------------
GAUGE_OPENER_PREFIX = 'The '
GAUGE_LEAD = 'River level against its own typical range'
GAUGE_NOTE = 'Environment Agency gauge; the typical range is the band the gauge itself publishes'


def gauge_facts(reading, url):
    """One gauge's card: its level now, the low and high of its typical
    range, and where in that range it sits. `reading` is one
    _river_readings() tuple. Live: the dateline carries the clock."""
    name, value, low, high, pct, when = reading
    opener = {'emoji': '🌊', 'text': GAUGE_OPENER_PREFIX + name}
    mk = lambda v, label: fact(v, label, 'Environment Agency', url, pair='gauge_all',
                               context_note=GAUGE_NOTE, dateline_lead=GAUGE_LEAD,
                               fixed_opener=opener)
    where = ('below its range' if pct < 0 else 'above its range' if pct > 100
             else f'{pct:.0f}% of the way up')
    return [mk(f'{value:.2f}m', 'Level now'), mk(f'{low:.2f}m', 'Typical low'),
            mk(f'{high:.2f}m', 'Typical high'), mk(where, 'Where it sits')]


def harvest_river_gauge():
    readings, failed = _river_readings()
    if not readings:
        return [], f'no station returned a usable reading; failed: {failed}'
    by_name = {r[0]: r for r in readings}
    name = spotlight_pick(list(by_name), last_featured(GAUGE_OPENER_PREFIX, RIVER_STATIONS))
    url = f'https://environment.data.gov.uk/flood-monitoring/id/stations/{RIVER_STATIONS[name]}'
    facts = gauge_facts(by_name[name], url)
    if failed:
        facts[0]['note'] = f'{len(failed)} of {len(RIVER_STATIONS)} curated gauges unusable: {failed}'
    return facts, None


def harvest_river_levels():
    readings, failed = _river_readings()
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


_POLICE_MEMO = {}


def _police_month(lat, lng, ym):
    """Memoised per process: police_boroughs and police_spotlight both read
    the same boroughs' months in one run, and the spotlight's rank needs all
    33, so without this a run would fetch the eight twice over."""
    key = (lat, lng, ym)
    if key not in _POLICE_MEMO:
        url = f'https://data.police.uk/api/crimes-street/all-crime?lat={lat}&lng={lng}&date={ym}'
        d = get_json(url)
        _POLICE_MEMO[key] = d if isinstance(d, list) else None
    return _POLICE_MEMO[key]


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


def _pct_point_change(now_frac, before_frac):
    """Signed whole-percentage-POINT difference between two 0-1 shares, as
    a card value: "+4 pts", "−2 pts", "0 pts". Deliberately distinct from
    _pct_change() — that one is a RELATIVE percent change, which for two
    numbers that are already percentages (an on-time share now against a
    typical one) would mean a move from 92% to 95.5% reads as "+4%", easy
    to misread as a percentage-point move when it is not. His call,
    15 September 2026, choosing point difference over relative change for
    exactly this reason."""
    diff = round((now_frac - before_frac) * 100)
    if diff > 0:
        return f'+{diff} pts'
    if diff < 0:
        return f'−{abs(diff)} pts'
    return '0 pts'


def _category_name(cat):
    """data.police.uk's slug ("other-theft", "anti-social-behaviour") as
    label prose. "Anti-social behaviour" keeps its hyphen, since the slug
    carries two of them and only the first is a real word-join."""
    if cat == 'anti-social-behaviour':
        return 'Anti-social behaviour'
    return cat.replace('-', ' ').capitalize()


CENTRAL_LEAD = 'Within a mile of Trafalgar Square'
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
                          period=ym, pair='central_top', dateline_lead=CENTRAL_LEAD))
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

# Whole-borough counts since 12 September 2026 (see CRIME_CACHE above), so the
# cards need neither a sample qualifier on the second line nor a footnote
# naming the sample: "Most: Westminster 7,212" under "Reported crime / July
# 2026" now means what it says. Both kept as names so borough_facts() need
# not change shape if a qualifier is ever wanted again.
BOROUGH_LEAD = None
BOROUGH_NOTE = None
BOROUGH_TOP_N = 4
# The categories worth a "which borough had the most" line, in the order a
# reader expects them. Anti-social behaviour and other-theft are left out
# on purpose: the first is not a crime in the recorded-crime sense and the
# second is a catch-all whose name explains nothing on a card.
BOROUGH_TYPE_CATEGORIES = ('violent-crime', 'shoplifting', 'vehicle-crime',
                           'burglary', 'bicycle-theft', 'robbery')
BOROUGH_TYPES_N = 4



# --- Whole-borough crime counts, cached by month ---------------------------
# Until 12 September 2026 every borough figure was a one-mile sample around
# the town hall, because data.police.uk has no Met borough boundaries of its
# own. It does take a polygon, and the ONS borough outlines the map draws
# are that polygon: measured that day, Westminster, the busiest, answers in
# one call at 7,212 crimes for July 2026, under the API's 10,000-crime cap,
# and the six multi-part boroughs answer ring by ring. The proxy had been
# understating badly: Barking and Dagenham's whole borough is 2,166 against
# the sample's 921. Counts are cached per month at CRIME_CACHE (gitignored,
# derived), so the 33 boroughs' polygons are fetched once a month, not four
# times a day; a borough whose fetch fails is left out of that month and
# retried next run, never cached as zero.
CRIME_CACHE = Path(__file__).parent / 'data' / 'crime_by_borough.json'
POLY_URL = 'https://data.police.uk/api/crimes-street/all-crime'


def _poly_post(ring, ym):
    """The crimes inside one ring for one month, or None if the API did not
    answer 200 with a list (a 503 is its over-10,000 refusal)."""
    poly = ':'.join(f'{lat:.5f},{lon:.5f}' for lon, lat in ring)
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as fh:
        out = fh.name
    try:
        r = subprocess.run(['curl', '-sS', '--max-time', '90', '-o', out, '-w', '%{http_code}',
                            '-X', 'POST', '--data-urlencode', f'poly={poly}',
                            '--data-urlencode', f'date={ym}', POLY_URL],
                           capture_output=True, text=True)
        if r.returncode != 0 or r.stdout.strip() != '200':
            return None
        try:
            d = json.loads(Path(out).read_text())
        except ValueError:
            return None
        return d if isinstance(d, list) else None
    finally:
        Path(out).unlink(missing_ok=True)


def _read_cache(path=CRIME_CACHE):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def _write_cache(cache, path=CRIME_CACHE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(cache, indent=1, sort_keys=True))
    tmp.replace(path)


def borough_month_whole(name, ym, outers):
    """{'total', 'categories'} for the whole borough, summed over its outer
    rings, or None if any ring failed (a partial borough is not a borough)."""
    total = 0
    cats = {}
    for ring in outers:
        recs = _poly_post(ring, ym)
        if recs is None:
            return None
        total += len(recs)
        for r in recs:
            cats[r['category']] = cats.get(r['category'], 0) + 1
    return {'total': total, 'categories': cats}


def whole_borough_counts(ym, names=None, cache_path=CRIME_CACHE, fetch=borough_month_whole):
    """name -> {'total', 'categories'} for every borough that answered for
    `ym`, from the cache where it has them and the API where it does not.
    `names` defaults to every borough in the boundary file."""
    import london_index_card as card
    outers = card.load_borough_outers()
    names = list(names or outers)
    cache = _read_cache(cache_path)
    month = cache.setdefault(ym, {})
    fetched = 0
    for name in names:
        if name in month or name not in outers:
            continue
        rec = fetch(name, ym, outers[name])
        if rec is not None:
            month[name] = rec
            fetched += 1
    if fetched:
        _write_cache(cache, cache_path)
        # stderr: the harvester's own main() prints the pool as JSON on stdout.
        print(f'Whole-borough crime: fetched {fetched} borough(s) for {ym}; '
              f'{len(month)} of {len(names)} now cached.', file=sys.stderr)
    return {n: month[n] for n in names if n in month}



# --- The Met's own borough counts: the Monthly Crime Dashboard ------------
# Chris's call, 12 September 2026, offered as "could replace our polygon
# counts with official ones". The London Datastore carries the Met's own
# dashboard data (dataset e5n6w): total notifiable offences by borough and
# offence group, monthly, refreshed by the 6th of the following month, so a
# month fresher than data.police.uk's street-level feed (August 2026 was
# there on 12 September; data.police.uk had July). One 136 MB CSV, 877,000
# rows, most of them ward-level; the 'Borough' rows for the 'Offences'
# measure are what the cards use. Cached at MPS_CACHE (gitignored) and
# re-downloaded only when the month the calendar expects is missing and the
# last attempt is over a day old, so a late Met costs one download a day,
# not four. The polygon counts (CRIME_CACHE) stay as the fallback when the
# dashboard cannot be read at all. ⚠️ TNO counts exclude anti-social
# behaviour, which data.police.uk includes; the two are not comparable, and
# a card names its source.
MPS_DASHBOARD_URL = 'https://data.london.gov.uk/download/e5n6w/hkc/M1045_MonthlyCrimeDashboard_TNOCrimeData.csv'
MPS_DASHBOARD_PAGE = 'https://data.london.gov.uk/dataset/mps-monthly-crime-dahboard-data'
MPS_CACHE = Path(__file__).parent / 'data' / 'mps_dashboard.json'
MPS_SOURCE = 'Metropolitan Police crime dashboard (London Datastore)'
MPS_NOTE = 'Total notifiable offences, the Metropolitan Police’s own monthly count'
MPS_TYPE_GROUPS = ('VIOLENCE AGAINST THE PERSON', 'THEFT', 'VEHICLE OFFENCES', 'BURGLARY',
                   'ROBBERY', 'DRUG OFFENCES')
REFETCH_AFTER_HOURS = 24


def _group_name(g):
    """'VIOLENCE AGAINST THE PERSON' -> 'Violence against the person'."""
    g = g.strip()
    return g[:1].upper() + g[1:].lower() if g else g


def mps_parse(text):
    """The dashboard CSV -> {'refresh': 'YYYY-MM-DD', 'months': {ym: {borough:
    {'total': n, 'groups': {group: n}}}}}, Borough rows and the Offences
    measure only, the 'Other / NK' bucket left out. Raises ValueError on a
    changed header."""
    import csv
    import io
    rows = csv.reader(io.StringIO(text))
    header = [c.strip() for c in next(rows)]
    need = ['Month_Year', 'Area Type', 'Area Name', 'offence group', 'Measure', 'Count', 'Refresh Date']
    if not all(n in header for n in need):
        raise ValueError(f'dashboard header changed: {header}')
    mi, ti, ni, gi, mei, ci, ri = (header.index(n) for n in need)
    months = {}
    refresh = ''
    for r in rows:
        try:
            if r[ti] != 'Borough' or r[mei] != 'Offences':
                continue
            name = r[ni].strip()
            # Only the 33 boroughs: the file also carries 'Other / NK' and, in
            # some months, 'Aviation Policing' (Heathrow) as 'Borough' rows.
            if name not in ALL_BOROUGHS:
                continue
            ym = r[mi][:7]
            n = int(r[ci] or 0)
        except (IndexError, ValueError):
            continue
        refresh = max(refresh, r[ri])
        b = months.setdefault(ym, {}).setdefault(name, {'total': 0, 'groups': {}})
        b['total'] += n
        b['groups'][r[gi]] = b['groups'].get(r[gi], 0) + n
    if not months:
        raise ValueError('no borough offence rows parsed')
    return {'refresh': refresh, 'months': months}


def head_etag(url):
    """The ETag the Datastore serves for a download, or None. Both big files
    carry one (measured 12 September 2026), so a month that is late costs a
    HEAD request a run, not a 136 MB download a day."""
    r = subprocess.run(['curl', '-sSI', '-L', '--max-time', '30', url], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        if line.lower().startswith('etag:'):
            return line.split(':', 1)[1].strip()
    return None


def needs_refetch(cache, now=None, url=None, etag_of=None):
    """True when the month the calendar expects (the previous one) is not
    cached, the last attempt is over REFETCH_AFTER_HOURS old, and, when the
    cache remembers the file's ETag and `url` is given, the file's ETag has
    changed (a file that has not changed cannot hold the missing month)."""
    now = now or datetime.now(timezone.utc)
    expected = _shift_month(now.strftime('%Y-%m'), 1)
    if expected in (cache.get('months') or {}):
        return False
    fetched = cache.get('fetched')
    if fetched:
        try:
            if now - datetime.fromisoformat(fetched) < timedelta(hours=REFETCH_AFTER_HOURS):
                return False
        except ValueError:
            pass
    if url and cache.get('etag'):
        current = (etag_of or head_etag)(url)
        if current and current == cache['etag']:
            return False
    return True


def mps_borough_months(cache_path=MPS_CACHE, download=None):
    """ym -> {borough -> {'total', 'groups'}} from the cache, refreshed from
    the Datastore when needs_refetch() says so. A failed download leaves the
    cache as it was (with its attempt time stamped) and returns it."""
    cache = _read_cache(cache_path)
    if needs_refetch(cache, url=MPS_DASHBOARD_URL):
        text = (download or _download_text)(MPS_DASHBOARD_URL, timeout=600)
        cache['fetched'] = datetime.now(timezone.utc).isoformat()
        if text:
            try:
                parsed = mps_parse(text)
                cache['months'] = parsed['months']
                cache['refresh'] = parsed['refresh']
                cache['etag'] = head_etag(MPS_DASHBOARD_URL)
                print(f'Met dashboard: fetched, {len(parsed["months"])} months, refresh {parsed["refresh"]}.',
                      file=sys.stderr)
            except ValueError as e:
                print(f'Met dashboard: {e}', file=sys.stderr)
        else:
            print('Met dashboard: download failed; using the cache as it stands.', file=sys.stderr)
        _write_cache(cache, cache_path)
    return cache.get('months') or {}


def borough_source():
    """(ym, now, prev, cats, source, url, note, type_groups, name_fn) for the
    borough cards: the Met dashboard when it has a month, else the polygon
    counts from data.police.uk. `now` and `prev` map borough -> total, `cats`
    borough -> {category: n}. None when neither source has a month."""
    months = mps_borough_months()
    if months:
        ym = max(months)
        now = {n: r['total'] for n, r in months[ym].items()}
        cats = {n: r['groups'] for n, r in months[ym].items()}
        prev_m = months.get(_shift_month(ym, 1)) or {}
        prev = {n: r['total'] for n, r in prev_m.items()}
        return ym, now, prev, cats, MPS_SOURCE, MPS_DASHBOARD_PAGE, MPS_NOTE, MPS_TYPE_GROUPS, _group_name
    ym, _ = _latest_police_month(51.5074, -0.1278)
    if ym is None:
        return None
    w = whole_borough_counts(ym)
    now = {n: r['total'] for n, r in w.items()}
    cats = {n: r['categories'] for n, r in w.items()}
    prev = {n: r['total'] for n, r in whole_borough_counts(_shift_month(ym, 1), names=list(w)).items()}
    url = f'{POLY_URL}?poly=<borough outline>&date={ym}'
    return ym, now, prev, cats, 'data.police.uk', url, None, BOROUGH_TYPE_CATEGORIES, _category_name


def borough_facts(counts, prev_counts, cats, ym, url, source='data.police.uk', note=None,
                  type_categories=None, name_fn=None):
    """The borough card's facts from this month's per-borough counts, the
    previous month's, and each borough's per-category counts, for all 33
    boroughs as whole boroughs (since 12 September 2026; eight one-mile
    samples before that). Pure, like central_facts(). Five card shapes from
    one month's data, where until that day there were two (the gap, and a
    near-tie when one existed) and the gap alone was posted five times in
    five days, since the busiest and quietest of eight fixed boroughs do not
    change within a month:
      - "police_gap": most and fewest, as before
      - "police_heat": a genuine near-tie, when one exists, as before
      - "police_top": the BOROUGH_TOP_N busiest, ranked, picked whole
      - "police_change": the biggest rise and the biggest fall (or the
        smallest rise, when every borough rose) on the previous month
      - "police_types_top": for each of BOROUGH_TYPE_CATEGORIES, the
        borough with the most of it, ranked by count, picked whole
    Every fact carries BOROUGH_NOTE."""
    note = note if note is not None else BOROUGH_NOTE
    lead = BOROUGH_LEAD
    type_categories = type_categories or BOROUGH_TYPE_CATEGORIES
    name_fn = name_fn or _category_name
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    busiest, quietest = ranked[0], ranked[-1]
    facts = [
        fact(f'{busiest[1]:,}', f'Most: {busiest[0]}',
             source, url, period=ym, pair='police_gap', context_note=note, dateline_lead=lead),
        fact(f'{quietest[1]:,}', f'Fewest: {quietest[0]}',
             source, url, period=ym, pair='police_gap', context_note=note, dateline_lead=lead),
    ]
    # Dead-heat: two of the curated boroughs whose crime counts happen to
    # land on nearly the same number, out of the whole set rather than just
    # the busiest/quietest extremes above.
    heat = dead_heat(list(counts.items()))
    if heat:
        name_a, _, name_b, _ = heat
        for name in (name_a, name_b):
            facts.append(fact(f'{counts[name]:,}', name,
                               source, url, period=ym,
                               pair='police_heat', context_note=note, dateline_lead=lead))
    for name, n in ranked[:BOROUGH_TOP_N]:
        facts.append(fact(f'{n:,}', name, source, url, period=ym,
                          pair='police_top', context_note=note, dateline_lead=lead))
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
                              source, url, period=ym,
                              pair='police_change', context_note=note, dateline_lead=lead))
            fall_label = 'Biggest fall' if fall < 0 else 'Smallest rise'
            facts.append(fact(_pct_change(counts[fall_name], prev_counts[fall_name]),
                              f'{fall_label} since {prev_month}: {fall_name}',
                              source, url, period=ym,
                              pair='police_change', context_note=note, dateline_lead=lead))
    leaders = []
    for cat in type_categories:
        per = {name: c.get(cat, 0) for name, c in cats.items()}
        if not per or max(per.values()) == 0:
            continue
        name = max(per.items(), key=lambda kv: kv[1])[0]
        leaders.append((cat, name, per[name]))
    leaders.sort(key=lambda t: -t[2])
    for cat, name, n in leaders[:BOROUGH_TYPES_N]:
        facts.append(fact(f'{n:,}', f'{name_fn(cat)}: {name}',
                          source, url, period=ym,
                          pair='police_types_top', context_note=note, dateline_lead=lead))
    return facts


def harvest_police_boroughs():
    src = borough_source()
    if src is None:
        return [], 'no populated month found in the last 4 tried'
    ym, counts, prev_counts, cats, source, url, note, type_groups, name_fn = src
    if len(counts) < 2:
        return [], f'fewer than 2 boroughs answered for {ym}'
    # A change pair over a partial previous month would compare the boroughs
    # against however many happened to answer; all or none.
    if set(prev_counts) != set(counts):
        prev_counts = {}
    facts = borough_facts(counts, prev_counts, cats, ym, url, source=source, note=note,
                          type_categories=type_groups, name_fn=name_fn)
    missing = sorted(set(ALL_BOROUGHS) - set(counts))
    if missing:
        facts[0]['note'] = f'{len(missing)} of {len(ALL_BOROUGHS)} boroughs missing for {ym}: {missing}'
    return facts, None



# --- Spotlight borough: one of 33, a different one each card ---------------
# Chris's worry on 12 September 2026, offered a 33-borough ranking: "I worry
# that's going to be very static." He was right: whatever the set, the same
# names top a crime ranking month after month. This card is about a PLACE,
# not a league table, and walks through all 33 (32 boroughs plus the City),
# least recently featured first, so no name repeats until every borough has
# had a card. The eight in POLICE_BOROUGHS keep the ranked shapes; these 25
# were geocoded via Nominatim on 12 September 2026, one civic building each,
# and every returned display_name was read before the coordinate was kept
# (Havering and Sutton needed a second query; Richmond's is the Civic Centre
# at 44 York Street, not the first hit, York House, 150 m away). Same
# one-mile sample as POLICE_BOROUGHS, so the rank is like against like.
ALL_BOROUGHS = dict(POLICE_BOROUGHS)
ALL_BOROUGHS.update({
    'Barking and Dagenham': (51.5357947, 0.0783323),
    'Barnet': (51.5875152, -0.2295466),
    'Bexley': (51.4556675, 0.1535181),
    'City of London': (51.5159067, -0.0920239),
    'Enfield': (51.6544039, -0.0806629),
    'Greenwich': (51.4898943, 0.0646427),
    'Hammersmith and Fulham': (51.4917715, -0.2338351),
    'Haringey': (51.5993866, -0.1123576),
    'Harrow': (51.5896111, -0.3328771),
    'Havering': (51.5813489, 0.1839732),
    'Hillingdon': (51.5436846, -0.4768893),
    'Hounslow': (51.4686286, -0.3674574),
    'Islington': (51.5422362, -0.1029387),
    'Kensington and Chelsea': (51.5021491, -0.1950748),
    'Kingston upon Thames': (51.4083581, -0.3059372),
    'Lambeth': (51.4606347, -0.1170681),
    'Lewisham': (51.4451556, -0.0207568),
    'Merton': (51.4013156, -0.1961441),
    'Redbridge': (51.5588663, 0.0741985),
    'Richmond upon Thames': (51.4478600, -0.3257800),
    'Southwark': (51.5032011, -0.0806807),
    'Sutton': (51.3616413, -0.1949320),
    'Tower Hamlets': (51.5185663, -0.0601574),
    'Waltham Forest': (51.5908779, -0.0135681),
    'Wandsworth': (51.4566514, -0.1909077),
})
SPOTLIGHT_OPENER_PREFIX = 'Reported crime in '
SPOTLIGHT_LEAD = None   # whole-borough counts since 12 September 2026; the dateline is the month
# No footnote, his call 12 September 2026 ("I'm not sure I see the value"):
# the rank value already says "of 33" and the threaded map shows the sample.
SPOTLIGHT_NOTE = None
SPOTLIGHT_MIN_RANKED = 20
CARD_HISTORY_PATH = Path(__file__).parent / 'card_history.jsonl'


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


def last_featured(prefix, names, history_path=CARD_HISTORY_PATH):
    """name -> the `at` string of the most recent card whose opener was
    `prefix` + name, for names in `names`, read from the card log. The
    rotation mechanism every spotlight-style card shares (boroughs,
    stations, river gauges). Unreadable lines are skipped."""
    seen = {}
    names = set(names)
    if not Path(history_path).exists():
        return seen
    for line in Path(history_path).read_text(encoding='utf-8').splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        opener = rec.get('opener') or ''
        if opener.startswith(prefix):
            name = opener[len(prefix):]
            if name in names and rec.get('at', '') > seen.get(name, ''):
                seen[name] = rec['at']
    return seen


def spotlight_last_featured(history_path=CARD_HISTORY_PATH):
    return last_featured(SPOTLIGHT_OPENER_PREFIX, ALL_BOROUGHS, history_path)


def spotlight_pick(candidates, last_featured):
    """The candidate never featured, else the one featured longest ago;
    alphabetical on a tie so the walk is deterministic."""
    return sorted(candidates, key=lambda n: (n in last_featured, last_featured.get(n, ''), n))[0]


def spotlight_facts(name, total, categories, prev_total, all_counts, ym, url,
                    source='data.police.uk', note=None, name_fn=None):
    """One borough's card, from its whole-borough total and per-category
    counts for the month, the previous month's total (or None) and every
    answering borough's total for the rank; under SPOTLIGHT_MIN_RANKED
    answering, no rank line. The map pin names the borough and carries no
    coordinates: the fill is the area counted, so no circle. Under the
    same SPOTLIGHT_MIN_RANKED threshold that withholds the "Nth highest"
    line, the pin also carries every answering borough's count as
    `ranks`, so london_index_card.render_borough_map can shade the whole
    map by it — the map and the card text either both carry the
    comparison or neither does. Added 14 September 2026, his call."""
    opener = {'emoji': '🚓', 'text': SPOTLIGHT_OPENER_PREFIX + name}
    pin = {'name': name, 'lat': None, 'lng': None}
    ranked = len(all_counts) >= SPOTLIGHT_MIN_RANKED and name in all_counts
    if ranked:
        pin['ranks'] = dict(all_counts)
    name_fn = name_fn or _category_name
    mk = lambda v, label: fact(v, label, source, url, period=ym, pair='spot_all',
                               context_note=note if note is not None else SPOTLIGHT_NOTE,
                               dateline_lead=SPOTLIGHT_LEAD, fixed_opener=opener, map_pin=pin)
    top = max(categories.items(), key=lambda kv: kv[1])
    facts = [mk(f'{total:,}', 'Reported crimes'),
             mk(f'{top[1]:,}', f'Most common: {name_fn(top[0])}')]
    if prev_total:
        change = _pct_change(total, prev_total)
        if change is not None:
            facts.append(mk(change, f'Change since {_readable_month(_shift_month(ym, 1))}'))
    if ranked:
        rank = 1 + sum(1 for n in all_counts.values() if n > all_counts[name])
        # The value explains itself ("16th highest of 33"): a bare "16th" reads
        # either way, and "most first" on the label did not read at all. His
        # call, 12 September 2026.
        facts.append(mk(f'{_ordinal(rank)} highest of {len(all_counts)}', 'Rank among boroughs'))
    return facts


def harvest_police_spotlight():
    src = borough_source()
    if src is None:
        return [], 'no populated month found in the last 4 tried'
    ym, counts, prev_counts, cats, source, url, note, _groups, name_fn = src
    if not counts:
        return [], f'no borough answered for {ym}'
    name = spotlight_pick(list(counts), spotlight_last_featured())
    facts = spotlight_facts(name, counts[name], cats[name], prev_counts.get(name), counts, ym, url,
                            source=source, note=note, name_fn=name_fn)
    missing = sorted(set(ALL_BOROUGHS) - set(counts))
    if missing:
        facts[0]['note'] = f'{len(missing)} of {len(ALL_BOROUGHS)} boroughs missing for {ym}: {missing}'
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
        # one (the average). Until 18 September 2026 that made compose()'s
        # _is_single_day/_is_period_aggregate both read it as "mixed" and
        # give the card no dateline at all, with the count's own date
        # buried in this context_note as the card's only footnote - caught
        # when he pointed at the live card and said a date belongs on the
        # second line under the title, not in the footnote:
        # https://bsky.app/profile/london-index.bsky.social/post/3mvqfhjc3wh24.
        # compose()'s _mixed_period_day now resolves this exact shape to
        # the one day-level period among the two (the count's date), which
        # rides the dateline - so this note only needs to state the
        # average's own, less specific span; restating the count's date
        # here too would just repeat the dateline.
        context_note = f'Average is {latest_date.year} to date'
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


_DCMS_MEMO = {}
# The tables the museum spotlight reads beside Table 1 (total visitors):
# sheet name -> (label, formatter). Only a value for the SAME year as the
# museum's latest published total is used, so one card is one year.
DCMS_SPOTLIGHT_TABLES = {
    '4': ('Overseas visitors', lambda v: f'{int(round(v)):,}'),
    '3': ('Under-16s', lambda v: f'{int(round(v)):,}'),
    '5': ('Website visits', lambda v: f'{int(round(v)):,}'),
    '6': ('Would recommend a visit', lambda v: f'{v * 100:.0f}%'),
    '10': ('Admissions income', lambda v: f'£{v / 1e6:.1f} million'),
}


def dcms_table(sheet):
    """One DCMS sheet as {museum: {year_label: value}} for the London
    museums, plus the ordered list of year labels ('2024-25'). Downloads the
    ODS once per process. None if the sheet cannot be read."""
    if 'path' not in _DCMS_MEMO:
        td = tempfile.mkdtemp()
        path = Path(td) / 'dcms_museums.ods'
        result = subprocess.run(
            ['curl', '-sS', '-L', '--max-time', '30', '-o', str(path), DCMS_MUSEUMS_ODS_URL],
            capture_output=True)
        _DCMS_MEMO['path'] = path if result.returncode == 0 and path.exists() else None
    path = _DCMS_MEMO['path']
    if path is None:
        return None
    if sheet in _DCMS_MEMO:
        return _DCMS_MEMO[sheet]
    try:
        import pandas as pd
        df = pd.read_excel(path, engine='odf', sheet_name=sheet, header=None)
    except Exception:  # noqa: BLE001 - a missing sheet or engine is "cannot read"
        _DCMS_MEMO[sheet] = None
        return None
    header_row = None
    for i in range(len(df)):
        if str(df.iloc[i, 0]).strip() == 'Name of museum or gallery':
            header_row = i
            break
    if header_row is None:
        _DCMS_MEMO[sheet] = None
        return None
    headers = [str(c).strip() for c in df.iloc[header_row, :]]
    years = []
    for i, hd in enumerate(headers):
        m = re.match(r'^(\d{4})/(\d{2})', hd)
        if m:
            years.append((i, f'{m.group(1)}-{m.group(2)}'))
    table = {}
    for i in range(header_row + 1, len(df)):
        raw = df.iloc[i, 0]
        if not isinstance(raw, str):
            continue
        name = re.sub(r'\s*\[Note \d+\]\s*$', '', raw).strip()
        if name not in LONDON_DCMS_MUSEUMS:
            continue
        row = {}
        for idx, label in years:
            v = df.iloc[i, idx]
            if isinstance(v, (int, float)) and v == v:   # a number, not NaN
                row[label] = float(v)
        table[name] = row
    _DCMS_MEMO[sheet] = (table, [label for _, label in years])
    return _DCMS_MEMO[sheet]


# Spelled out, his call 12 September 2026 ("what is dcms"): the same objection
# as MOPAC, an acronym a reader may not know.
# His call, later the same day: the year alone under the title, the
# sponsorship in the footnote. Groups (Tate, Science Museum Group, Imperial
# War Museums, Royal Museums Greenwich) get the sites clause instead of the
# "one of 13", so the footnote stays one line either way.
MUSEUM_LEAD = None
# His wording, 12 September 2026.
MUSEUM_NOTE = 'One of 13 London museums funded by the Department for Culture, Media and Sport'
MUSEUM_NOTE_GROUP = MUSEUM_NOTE + '; all its sites counted'   # no full stop: footnotes here carry none
DCMS_PAGE = ('https://www.gov.uk/government/statistics/'
             'dcms-sponsored-museums-and-galleries-annual-performance-indicators-202425')


def museum_facts(name, visitors, years, extras, url=DCMS_PAGE):
    """One museum's card. `visitors` is its {year: value} from Table 1,
    `years` the ordered year labels, `extras` {label: value string} for the
    same year from the other tables. Pair "museum_all", opener the museum's
    published name."""
    published = [y for y in years if y in visitors]
    if not published:
        raise ValueError(f'no published visitor figure for {name}')
    year = published[-1]
    opener = {'emoji': '🏛️', 'text': name}
    note = MUSEUM_NOTE_GROUP if ('Group' in name or 'Museums' in name) else MUSEUM_NOTE
    mk = lambda v, label: fact(v, label, 'DCMS', url, period=year, pair='museum_all',
                               context_note=note, dateline_lead=MUSEUM_LEAD, fixed_opener=opener)
    facts = [mk(f'{int(visitors[year]):,}', 'Visitors')]
    i = years.index(year)
    if i >= 1 and years[i - 1] in visitors:
        change = _pct_change(visitors[year], visitors[years[i - 1]])
        if change is not None:
            facts.append(mk(change, f'Change on {years[i - 1]}'))
    if i >= 10 and years[i - 10] in visitors:
        facts.append(mk(f'{int(visitors[years[i - 10]]):,}', f'Visitors in {years[i - 10]}'))
    for label, value in extras.items():
        facts.append(mk(value, label))
    return facts


def harvest_museum_spotlight():
    t1 = dcms_table('1')
    if not t1:
        return [], 'DCMS museums table 1 could not be read'
    table, years = t1
    candidates = [n for n, row in table.items() if row]
    if not candidates:
        return [], 'no London museum has a published visitor figure'
    name = spotlight_pick(candidates, last_featured('', LONDON_DCMS_MUSEUMS))
    year = [y for y in years if y in table[name]][-1]
    extras = {}
    for sheet, (label, fmt) in DCMS_SPOTLIGHT_TABLES.items():
        tb = dcms_table(sheet)
        if tb and name in tb[0] and year in tb[0][name]:
            extras[label] = fmt(tb[0][name][year])
    return museum_facts(name, table[name], years, extras), None


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
STOPS_LEAD = 'Metropolitan Police'


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
                               pair='stops_all', dateline_lead=STOPS_LEAD)
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
HPI_LEAD = 'Land Registry index averages'
HPI_NOTE = 'All property types; recent months are provisional'


_HPI_MEMO = {}


def _hpi_month(slug, ym):
    """Memoised per process: house_prices and house_price_spotlight both
    read the same boroughs' months in one run, and the spotlight's rank
    needs all of them, so without this a run would fetch every borough
    twice over - the same reason _police_month is memoised."""
    key = (slug, ym)
    if key not in _HPI_MEMO:
        d = get_json(f'https://landregistry.data.gov.uk/data/ukhpi/region/{slug}/month/{ym}.json')
        rec = None
        if isinstance(d, dict):
            topic = (d.get('result') or {}).get('primaryTopic') if isinstance(d.get('result'), dict) else None
            if isinstance(topic, dict) and isinstance(topic.get('averagePrice'), (int, float)):
                rec = topic
        _HPI_MEMO[key] = rec
    return _HPI_MEMO[key]


def _hpi_current_month():
    """The latest month with a published London HPI figure, walking back
    up to 5 months. Shared by house_prices and house_price_spotlight so
    both land on the same month in one run."""
    this_month = datetime.now(timezone.utc).strftime('%Y-%m')
    for back in range(1, 6):
        ym = _shift_month(this_month, back)
        if _hpi_month('london', ym):
            return ym
    return None


def _hpi_boroughs(ym):
    """Every HPI_BOROUGHS borough's record for `ym` that answered, and the
    names that did not."""
    boroughs, failed = {}, []
    for name, slug in HPI_BOROUGHS.items():
        rec = _hpi_month(slug, ym)
        if rec:
            boroughs[name] = rec
        else:
            failed.append(name)
    return boroughs, failed


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
                                          pair=pair, context_note=HPI_NOTE,
                                          dateline_lead=HPI_LEAD)
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
    ym = _hpi_current_month()
    if ym is None:
        return [], 'no published UK HPI month for London in the last 5 tried'
    london = _hpi_month('london', ym)
    boroughs, failed = _hpi_boroughs(ym)
    facts = house_price_facts(london, boroughs, ym)
    if failed:
        facts[0]['note'] = (f'{len(failed)} of {len(HPI_BOROUGHS)} boroughs did not answer '
                            f'for {ym}: {failed}')
    return facts, None


# --- House price spotlight: one borough, its own price and rank ------------
# The choropleth's second vein, added 14 September 2026 (police_spotlight
# was the first). Same rotation shape as spotlight_facts() above: reads
# HPI_BOROUGHS through the memoised _hpi_month(), so a run building both
# house_prices and this vein fetches each borough once, not twice.
HP_SPOTLIGHT_OPENER_PREFIX = 'House prices in '


def hp_spotlight_last_featured(history_path=CARD_HISTORY_PATH):
    return last_featured(HP_SPOTLIGHT_OPENER_PREFIX, HPI_BOROUGHS, history_path)


def house_price_spotlight_facts(name, boroughs, ym, url=HPI_PAGE):
    """One borough's own average price, change on the year and the month,
    and its rank among the boroughs that answered - the same shape
    spotlight_facts() builds for crime. `boroughs` is every HPI_BOROUGHS
    borough that answered `ym` (from _hpi_boroughs()), `name`'s own record
    among them. Under HPI_MIN_BOROUGHS answering, no rank line and no
    `ranks` on the map pin - the same threshold house_price_facts() uses
    for its own borough shapes, so the spotlight and those facts either
    both carry the comparison or neither does."""
    rec = boroughs[name]
    opener = {'emoji': '🏠', 'text': HP_SPOTLIGHT_OPENER_PREFIX + name}
    pin = {'name': name, 'lat': None, 'lng': None}
    ranked = len(boroughs) >= HPI_MIN_BOROUGHS
    if ranked:
        pin['ranks'] = {n: r['averagePrice'] for n, r in boroughs.items()}
    mk = lambda v, label: fact(v, label, HPI_SOURCE, url, period=ym, pair='hp_spot',
                               context_note=HPI_NOTE, fixed_opener=opener, map_pin=pin)
    facts = [mk(_pounds(rec['averagePrice']), 'Average price')]
    annual = _signed_pct(rec.get('percentageAnnualChange'))
    if annual:
        facts.append(mk(annual, 'Change on a year earlier'))
    monthly = _signed_pct(rec.get('percentageChange'))
    if monthly:
        facts.append(mk(monthly, 'Change on the month'))
    if ranked:
        prices = pin['ranks']
        rank = 1 + sum(1 for v in prices.values() if v > prices[name])
        facts.append(mk(f'{_ordinal(rank)} highest of {len(prices)}', 'Rank among boroughs'))
    return facts


def harvest_house_price_spotlight():
    ym = _hpi_current_month()
    if ym is None:
        return [], 'no published UK HPI month for London in the last 5 tried'
    boroughs, failed = _hpi_boroughs(ym)
    if not boroughs:
        return [], f'no borough answered for {ym}'
    name = spotlight_pick(list(boroughs), hp_spotlight_last_featured())
    facts = house_price_spotlight_facts(name, boroughs, ym)
    if failed:
        facts[0]['note'] = (f'{len(failed)} of {len(HPI_BOROUGHS)} boroughs did not answer '
                            f'for {ym}: {failed}')
    return facts, None


# --- Roadworks and disruptions on TfL roads (live) -------------------------
ROADS_URL = 'https://api.tfl.gov.uk/Road/all/Disruption'
ROADS_PAGE = 'https://tfl.gov.uk/traffic/status'
ROADS_LEAD = 'TfL’s red routes'
ROADS_NOTE = 'The Transport for London Road Network, not every London street'
SERIOUS = {'moderate', 'serious', 'severe'}


def road_facts(items, url=ROADS_PAGE):
    """Live: everything TfL currently lists as a disruption on its own
    roads, how many it rates moderate or worse, and how many are planned
    works. Pair "roads_all" (see SELECT_PROMPT's "_all" rule)."""
    total = len(items)
    serious = sum(1 for i in items if (i.get('severity') or '').lower() in SERIOUS)
    works = sum(1 for i in items if (i.get('category') or '') == 'Works')
    mk = lambda v, label: fact(f'{v:,}', label, 'TfL Road disruptions', url,
                               pair='roads_all', context_note=ROADS_NOTE,
                               dateline_lead=ROADS_LEAD)
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
ANIMALS_LEAD = 'Callouts to animals trapped or in distress'
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
# A per-row icon for the animals_top ranked lines — see fact()'s own
# 'emoji' note for why this vein carries one and the rest of the index
# card's veins deliberately do not. No entry for 'Ferret': there is no
# distinct ferret emoji as of this writing, and a wrong-animal icon is
# worse than a bare row.
ANIMAL_EMOJI = {
    'Cat': '🐈', 'Dog': '🐕', 'Bird': '🐦', 'Fox': '🦊', 'Horse': '🐴',
    'Deer': '🦌', 'Squirrel': '🐿️', 'Rabbit': '🐇', 'Hamster': '🐹',
    'Cow': '🐄', 'Sheep': '🐑', 'Snake': '🐍', 'Goat': '🐐',
    'Hedgehog': '🦔', 'Lizard': '🦎', 'Tortoise': '🐢', 'Fish': '🐟',
    'Bull': '🐂', 'Pigeon': '🕊️', 'Lamb': '🐑', 'Budgie': '🐤', 'Rat': '🐀',
}


def animal_facts(rows, ym, url=ANIMALS_PAGE):
    """`rows` are dicts for one month (keys as the file's header names).
    Shapes: the month's total and the borough with the most (unpaired), the
    ANIMALS_TOP_N most-rescued kinds of animal ranked ("animals_top"), and
    the brigade's own notional cost of it all (unpaired)."""
    mk = lambda v, label, pair=None, emoji=None: fact(v, label, ANIMALS_SOURCE, url, period=ym,
                                                      pair=pair, dateline_lead=ANIMALS_LEAD,
                                                      emoji=emoji)
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
        facts.append(mk(f'{n:,}', ANIMAL_PLURALS[k], 'animals_top', ANIMAL_EMOJI.get(k)))
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
# Short enough for one line on the card: "…from 13 main stations, 12 September
# at 1:52 a.m." wrapped, orphaning "a.m." (seen on a render, 12 September 2026).
RAIL_LEAD = f'Departures in the next hour, {len(RAIL_TERMINI)} main stations'
RAIL_NOTE = 'National Rail, as on the live boards'
RAIL_TOP_N = 4
# "Running late, by operator": the boards name the operator of every train,
# so the late ones can be counted by company. At least RAIL_OPS_MIN
# operators must have a late train before the ranked group is made, or
# one late Thameslink is a league table of one. Added 12 September 2026.
#
# ⚠️ Ranked by SHARE of that operator's own departures, not raw count,
# since 15 September 2026 — Chris's own point: a raw-count ranking always
# favours whichever operator runs the most trains out of London, which is
# a fact about its timetable, not its punctuality. RAIL_OPS_MIN_SERVICES is
# the floor an operator's own total departures in the window must clear
# before its share counts as a real reading rather than a small sample
# reading 100% off one late train — a judgement call, not yet measured
# against a real distribution of operator volumes; revisit once there is
# a season of real cards to look at.
RAIL_OPS_MIN = 3
RAIL_OPS_MIN_SERVICES = 4
RAIL_OPS_NOTE = (f'Percent of that operator’s own departures running late, not a raw count '
                 f'— operators with fewer than {RAIL_OPS_MIN_SERVICES} trains due in the '
                 f'window are left out')
# Under this many departures across every terminus the boards are the
# small hours (9 at 1:36 a.m. on 12 September 2026), not a city, and no
# card is made. Under RAIL_MIN_STATIONS answering, a partial London is not
# ranked at all.
RAIL_MIN_DEPARTURES = 20
RAIL_MIN_STATIONS = 10

# --- Rail departures: our own history, for a same-hour baseline ------------
# National Rail publishes no "typical" figure for a station's departure
# board the way TfL does for Underground crowding (tfl_crowding's own
# baseline), so the only baseline available is one built from this
# account's own past readings. Added 15 September 2026, after Chris judged
# a bare live snapshot "not very interesting" on its own — see the vs-typical
# fact in rail_facts() below.
#
# ⚠️ Matched on LONDON weekday + hour, not an exact time-of-week: this
# account has no fixed posting clock, so a reading "at the same time last
# week" essentially never exists — the closest available comparison is the
# same weekday and the same hour, mirroring Seoul Index's own "a typical
# Tuesday" baseline (median of past same-weekday readings, minimum 3,
# up to 8). RAIL_BASELINE_MIN_SAMPLES/MAX_SAMPLES are that same pair of
# numbers, kept for the same reason: too few samples is a guess dressed as
# a fact, and there is no reason to look further back than eight weeks of
# a London commute.
RAIL_HISTORY_PATH = Path(__file__).parent / 'rail_history.jsonl'
RAIL_BASELINE_MIN_SAMPLES = 3
RAIL_BASELINE_MAX_SAMPLES = 8
LONDON_TZ = ZoneInfo('Europe/London')


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


def _rail_counts(boards):
    """One pass over every board's services: the aggregate on-time/late/
    cancelled/other counts, each station's own departure count, each
    operator's own late count against its own total departures in the
    window, and — across every board combined, not per station — how
    many distinct places these services are bound for and how many go to
    each. Shared by rail_facts() (the card), harvest_rail_departures()
    (the history snapshot) and rail_baseline() (indirectly, via the
    snapshot it reads back) — one counting rule, not three."""
    counts = {'on time': 0, 'late': 0, 'cancelled': 0, 'other': 0}
    per = {}
    late_by_operator = {}
    total_by_operator = {}
    dests = {}
    for name, services in boards.items():
        per[name] = len(services)
        for svc in services:
            state = classify_departure(svc)
            counts[state] += 1
            op = (svc.get('operator') or '').strip()
            if op:
                total_by_operator[op] = total_by_operator.get(op, 0) + 1
                if state == 'late':
                    late_by_operator[op] = late_by_operator.get(op, 0) + 1
            for d in svc.get('destination') or []:
                dn = (d.get('locationName') or '').strip()
                if dn:
                    dests[dn] = dests.get(dn, 0) + 1
    return {'counts': counts, 'per': per, 'late_by_operator': late_by_operator,
            'total_by_operator': total_by_operator, 'dests': dests}


def _share_pct(numerator, denominator):
    """Whole-percent share as a card value ("38%"), or "<1%" for anything
    nonzero that would otherwise round down to a literal-looking "0%" —
    the same ambiguity pct_of_baseline() was written to avoid for
    tfl_crowding. None when there is nothing to divide by."""
    if not denominator:
        return None
    pct = numerator / denominator * 100
    if 0 < pct < 0.5:
        return '<1%'
    return f'{pct:.0f}%'


def rail_facts(boards, url=RAIL_PAGE, baseline_total=None, baseline_on_time_share=None, now=None):
    """`boards` maps terminus name -> list of train services (the board's
    trainServices). Shapes:
      - "rail_all": trains departing within the hour, on time, running late,
        cancelled (any 2 to 4, fixed opener), plus — when given —
        how that departure count and how the on-time share each compare
        with a typical reading for this weekday and hour (see
        rail_baseline() and rail_baseline_on_time_share())
      - "rail_top": the RAIL_TOP_N termini with the most departures,
        ranked
      - "rail_ops_top": operators ranked by the SHARE of their own
        departures running late, when RAIL_OPS_MIN or more clear the
        RAIL_OPS_MIN_SERVICES floor and have at least one late train

    `baseline_total`, `baseline_on_time_share` and `now` are supplied by
    the caller (harvest_rail_departures reads the history file and the
    clock; tests pass fixed values directly) so this function stays a
    pure read of `boards` plus whatever comparisons it is handed — it
    does no file I/O and no clock reads of its own.

    Where these trains are actually going is deliberately NOT a fifth
    label/value row — his call, 15 September 2026, after "I do not want
    the equivalent of a departures board" made it clear that bolting
    another line onto the same table wasn't the fix. It reads as a
    sentence in the footnote instead, folded into RAIL_NOTE for the
    rail_all pair only (rail_top's own context_note is unaffected)."""
    agg = _rail_counts(boards)
    counts, per, dests = agg['counts'], agg['per'], agg['dests']
    total = sum(per.values())
    all_note = RAIL_NOTE
    if total > 0 and dests:
        leader, _n = max(dests.items(), key=lambda kv: (kv[1], kv[0]))
        all_note = (f'{RAIL_NOTE}. Bound for {len(dests)} different places, '
                   f'more to {leader} than anywhere else.')
    mk_top = lambda v, label: fact(f'{v:,}', label, RAIL_SOURCE, url, pair='rail_top',
                                   context_note=RAIL_NOTE, dateline_lead=RAIL_LEAD)
    mk_all = lambda v, label: fact(f'{v:,}', label, RAIL_SOURCE, url, pair='rail_all',
                                   context_note=all_note, dateline_lead=RAIL_LEAD)
    mk_cmp = lambda v, label: fact(v, label, RAIL_SOURCE, url, pair='rail_all',
                                   context_note=all_note, dateline_lead=RAIL_LEAD)
    mk_ops = lambda v, label: fact(v, label, RAIL_SOURCE, url, pair='rail_ops_top',
                                   context_note=RAIL_OPS_NOTE, dateline_lead=RAIL_LEAD)
    facts = [mk_all(total, 'Departing within the hour'),
             mk_all(counts['on time'], 'On time'),
             mk_all(counts['late'], 'Running late'),
             mk_all(counts['cancelled'], 'Cancelled')]
    weekday = (now or datetime.now(LONDON_TZ)).strftime('%A')
    if baseline_total is not None:
        change = _pct_change(total, baseline_total)
        if change is not None:
            # "Change from a typical <weekday>", matching spotlight_facts()'s
            # own "Change since <month>" shape rather than inventing a new
            # one. No trailing ", this hour": the dateline (RAIL_LEAD) already
            # says "Departures in the next hour", so the label repeating it
            # would be the exact redundancy the account's own house style
            # (no word the title already carries) rules out elsewhere.
            facts.append(mk_cmp(change, f'Change from a typical {weekday}'))
    if baseline_on_time_share is not None and total > 0:
        # A signed PERCENTAGE-POINT difference, not _pct_change()'s relative
        # percent — see _pct_point_change()'s own note on why, for a metric
        # that is already a percentage, the two read as easily confused but
        # different numbers. Labelled "On time, ..." to read as the
        # comparison version of the "On time" line above it, the same
        # relationship "Change from a typical <weekday>" has to "Departing
        # within the hour".
        facts.append(mk_cmp(_pct_point_change(counts['on time'] / total, baseline_on_time_share),
                            f'On time, change from a typical {weekday}'))
    # A ranked "busiest" list never carries a station with nothing due: at
    # 1:43 a.m. on 12 September 2026 a render bypassing the floor showed
    # King's Cross and Euston at 0 in third and fourth place. The group is
    # made only when RAIL_TOP_N stations have at least one train due.
    busy = [(name, n) for name, n in sorted(per.items(), key=lambda kv: -kv[1]) if n > 0]
    if len(busy) >= RAIL_TOP_N:
        for name, n in busy[:RAIL_TOP_N]:
            facts.append(mk_top(n, name))
    late_by_operator, total_by_operator = agg['late_by_operator'], agg['total_by_operator']
    qualifying = [(op, late_by_operator[op], total_by_operator[op]) for op in late_by_operator
                  if total_by_operator[op] >= RAIL_OPS_MIN_SERVICES]
    if len(qualifying) >= RAIL_OPS_MIN:
        ranked = sorted(qualifying, key=lambda t: (-(t[1] / t[2]), -t[1], t[0]))[:RAIL_TOP_N]
        for op, late, total_op in ranked:
            facts.append(mk_ops(_share_pct(late, total_op), op))
    return facts


def _rail_snapshot_rows():
    """Every readable row in RAIL_HISTORY_PATH, file order (oldest first).
    An unreadable line is skipped, never fatal — this is a best-effort
    archive of our own past readings, not a source of truth anything else
    depends on existing. Reads the module attribute directly (not a
    default-argument capture of it) so a test that patches
    H.RAIL_HISTORY_PATH is actually honoured."""
    if not RAIL_HISTORY_PATH.exists():
        return []
    rows = []
    for line in RAIL_HISTORY_PATH.read_text(encoding='utf-8').splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _log_rail_snapshot(total, on_time, late, cancelled, now=None):
    """Append one reading to RAIL_HISTORY_PATH. Called only for a clean,
    full-coverage read (see harvest_rail_departures) — a partial one would
    quietly bias every future baseline low for no reason connected to
    real service levels."""
    now = now or datetime.now(LONDON_TZ)
    row = {'ts': now.isoformat(), 'total': total, 'on_time': on_time,
           'late': late, 'cancelled': cancelled}
    with open(RAIL_HISTORY_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(row) + '\n')


def _matching_rail_history(now=None):
    """Up to RAIL_BASELINE_MAX_SAMPLES past history rows sharing this
    moment's London weekday and hour, most recent first — a row whose
    timestamp doesn't parse is skipped and never occupies a slot. Shared
    by rail_baseline() and rail_baseline_on_time_share() so both read the
    history under one matching rule rather than two that could drift."""
    now = now or datetime.now(LONDON_TZ)
    weekday, hour = now.weekday(), now.hour
    matches = []
    for row in reversed(_rail_snapshot_rows()):
        try:
            ts = datetime.fromisoformat(row['ts'])
        except (KeyError, ValueError, TypeError):
            continue
        if ts.tzinfo is None:
            continue
        ts = ts.astimezone(LONDON_TZ)
        if ts.weekday() == weekday and ts.hour == hour:
            matches.append(row)
            if len(matches) >= RAIL_BASELINE_MAX_SAMPLES:
                break
    return matches


def rail_baseline(now=None):
    """Median total departures from up to RAIL_BASELINE_MAX_SAMPLES past
    readings sharing this moment's London weekday and hour; None under
    RAIL_BASELINE_MIN_SAMPLES usable readings — see the module note above
    RAIL_HISTORY_PATH for why weekday+hour and not an exact time-of-week."""
    totals = [r['total'] for r in _matching_rail_history(now) if isinstance(r.get('total'), (int, float))]
    if len(totals) < RAIL_BASELINE_MIN_SAMPLES:
        return None
    return statistics.median(totals)


def rail_baseline_on_time_share(now=None):
    """Median on-time SHARE (on_time / total, a 0-1 fraction) over the
    same matching readings rail_baseline() draws on — the median of each
    reading's OWN share, not the ratio of the two medians, so one
    unusually quiet or unusually cancelled reading can't distort the
    comparison by moving only one side of a fraction. None under
    RAIL_BASELINE_MIN_SAMPLES usable readings. A reading with a zero
    total is excluded rather than dividing by it — should never happen
    given harvest_rail_departures' own RAIL_MIN_DEPARTURES floor, but
    this must not crash if it somehow did."""
    shares = []
    for row in _matching_rail_history(now):
        total, on_time = row.get('total'), row.get('on_time')
        if isinstance(total, (int, float)) and isinstance(on_time, (int, float)) and total > 0:
            shares.append(on_time / total)
    if len(shares) < RAIL_BASELINE_MIN_SAMPLES:
        return None
    return statistics.median(shares)


_RAIL_MEMO = {}


def _rail_boards():
    """(boards, failed, error): every terminus's trainServices for the
    window, fetched once per process, since rail_departures and
    rail_station both read the same 13 boards in one run."""
    if 'boards' not in _RAIL_MEMO:
        key = _rdm_key()
        if not key:   # not memoised: a missing key is a fact about this call, not the boards
            return {}, [], 'no Rail Data Marketplace key in Keychain (london-index / rdm-ldbws-key)'
        boards = {}
        failed = []
        for name, crs in RAIL_TERMINI.items():
            d = get_json_with_headers(RAIL_API.format(crs=crs, window=RAIL_WINDOW_MIN),
                                      {'x-apikey': key, 'Accept': 'application/json'})
            if not isinstance(d, dict) or d.get('crs') != crs or not d.get('areServicesAvailable', True):
                failed.append(name)
                continue
            boards[name] = d.get('trainServices') or []
        _RAIL_MEMO['boards'] = (boards, failed, None)
    return _RAIL_MEMO['boards']


# --- Station spotlight: one of the 13, its own board ------------------------
STATION_OPENER_PREFIX = 'Trains from '
STATION_LEAD = 'Departures in the next hour'
STATION_NOTE = 'National Rail, as on the live board'
STATION_MIN_DEPARTURES = 8


def station_facts(name, services, url=RAIL_PAGE):
    """One station's card from its own board: departing within the hour, on
    time, late, cancelled, and the destination with the most trains. All
    share the pair "station_all" and a fixed opener naming the station;
    the opener prefix is what last_featured() reads back for the rotation."""
    opener = {'emoji': '🚆', 'text': STATION_OPENER_PREFIX + name}
    mk = lambda v, label: fact(f'{v:,}', label, RAIL_SOURCE, url, pair='station_all',
                               context_note=STATION_NOTE, dateline_lead=STATION_LEAD,
                               fixed_opener=opener)
    counts = {'on time': 0, 'late': 0, 'cancelled': 0, 'other': 0}
    dests = {}
    for svc in services:
        counts[classify_departure(svc)] += 1
        for d in svc.get('destination') or []:
            dn = (d.get('locationName') or '').strip()
            if dn:
                dests[dn] = dests.get(dn, 0) + 1
    facts = [mk(len(services), 'Departing within the hour'), mk(counts['on time'], 'On time'),
             mk(counts['late'], 'Running late'), mk(counts['cancelled'], 'Cancelled')]
    if dests:
        dn, n = max(dests.items(), key=lambda kv: (kv[1], kv[0]))
        facts.append(mk(n, f'Most trains to: {dn}'))
    return facts


def harvest_rail_station():
    boards, failed, err = _rail_boards()
    if err:
        return [], err
    candidates = [n for n, s in boards.items() if len(s) >= STATION_MIN_DEPARTURES]
    if not candidates:
        return [], (f'no station has {STATION_MIN_DEPARTURES} departures due; '
                    f'boards too quiet for a station card')
    name = spotlight_pick(candidates, last_featured(STATION_OPENER_PREFIX, RAIL_TERMINI))
    return station_facts(name, boards[name]), None


def harvest_rail_departures():
    boards, failed, err = _rail_boards()
    if err:
        return [], err
    if len(boards) < RAIL_MIN_STATIONS:
        return [], f'only {len(boards)} of {len(RAIL_TERMINI)} termini answered; failed: {failed}'
    total = sum(len(v) for v in boards.values())
    if total < RAIL_MIN_DEPARTURES:
        return [], f'only {total} departures due across the termini; boards too quiet for a card'
    now = datetime.now(LONDON_TZ)
    facts = rail_facts(boards, baseline_total=rail_baseline(now=now),
                       baseline_on_time_share=rail_baseline_on_time_share(now=now), now=now)
    if failed:
        facts[0]['note'] = f'{len(failed)} of {len(RAIL_TERMINI)} termini unusable: {failed}'
    else:
        # Only a full-coverage read is archived — see _log_rail_snapshot's
        # own note on why a partial one must not become a baseline sample.
        agg = _rail_counts(boards)
        _log_rail_snapshot(total, agg['counts']['on time'], agg['counts']['late'],
                           agg['counts']['cancelled'], now=now)
    return facts, None


# --- Seven London Datastore series (12 September 2026) ----------------------
# Chris: "Is there not something more we could use? Seems like a good source
# of material." A survey of the 145 datasets updated since March found these
# seven regular numeric series with small machine-readable files, each read
# here from the Datastore's own download URL every run (the largest is
# 2.3 MB). Every builder is pure and tested on the file's real header shape;
# every harvester refuses plainly on a changed header or an empty series
# rather than posting a zero. Publisher credit stays data.london.gov.uk,
# already on every source line and in the pinned thread.
DATASTORE = 'London Datastore'


def _download_text(url, timeout=60):
    body = curl(url, timeout=timeout)
    return body.lstrip('﻿') if body else None


def _download_xlsx_rows(url, sheet=None, timeout=90):
    """Rows of one sheet (the first, or `sheet` by name) as tuples, or None."""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'f.xlsx'
        r = subprocess.run(['curl', '-sS', '-L', '--max-time', str(timeout), '-o', str(path), url],
                           capture_output=True)
        if r.returncode != 0 or not path.exists():
            return None
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        except Exception:  # noqa: BLE001 - a bad download is a refusal, not a crash
            return None
        ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb.worksheets[0]
        return [row for row in ws.iter_rows(values_only=True) if any(v is not None for v in row)]


def _csv_rows(text):
    import csv
    import io
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    return rows


def _harvest_csv(url, facts_fn, label):
    """Download `url` as CSV and hand its rows to `facts_fn`, the shared
    shape behind the Datastore CSV harvesters below."""
    text = _download_text(url)
    if not text:
        return [], f'{label} download failed'
    try:
        return facts_fn(_csv_rows(text)), None
    except ValueError as e:
        return [], str(e)


def _harvest_xlsx(url, facts_fn, label, sheet=None):
    """Download `url` as XLSX and hand one sheet's rows to `facts_fn`, the
    shared shape behind the Datastore XLSX harvesters below."""
    rows = _download_xlsx_rows(url, sheet=sheet)
    if not rows:
        return [], f'{label} download failed'
    try:
        return facts_fn(rows), None
    except ValueError as e:
        return [], str(e)


def _month_label(s):
    """'Jul-26' -> '2026-07'."""
    return datetime.strptime(s.strip(), '%b-%y').strftime('%Y-%m')


def _day_label(s):
    """'31-Aug-26' -> '2026-08-31'."""
    return datetime.strptime(s.strip(), '%d-%b-%y').strftime('%Y-%m-%d')


def _num(s):
    return float(str(s).replace(',', '').strip())


def _points(now, before):
    d = round(now - before)
    return f'+{d} points' if d > 0 else f'−{abs(d)} points' if d < 0 else 'unchanged'


# 1. Reservoir levels: daily since 1989, percent of usable capacity.
RESERVOIR_URL = 'https://data.london.gov.uk/download/24ry5/778eefb5-8cef-4d16-a4c8-77dee7ce7e81/london_reservoir_levels.csv'
RESERVOIR_PAGE = 'https://data.london.gov.uk/dataset/london-reservoir-levels'
RESERVOIR_NOTE = ('Thames Water’s Lower Thames and Lower Lee reservoir groups; usable capacity '
                  'leaves out water kept back for the environment')


def reservoir_facts(rows, url=RESERVOIR_PAGE):
    """`rows` are the CSV rows including the header: date, month, year,
    lower_lee_group, lower_thames_group. The newest day's two levels, each
    against the same date a year earlier, and the Thames group against its
    average for that date over every year in the series."""
    header = [c.strip().lower() for c in rows[0]]
    if header[:5] != ['date', 'month', 'year', 'lower_lee_group', 'lower_thames_group']:
        raise ValueError(f'reservoir header changed: {header}')
    series = {}
    for r in rows[1:]:
        try:
            day = _day_label(r[0])
            series[day] = (_num(r[3]), _num(r[4]))
        except (ValueError, IndexError):
            continue
    if not series:
        raise ValueError('no reservoir rows parsed')
    newest = max(series)
    lee, thames = series[newest]
    y, m, d = newest.split('-')
    year_ago = f'{int(y) - 1}-{m}-{d}'
    same_date = [v[1] for k, v in series.items() if k[5:] == f'{m}-{d}']
    mk = lambda v, label: fact(v, label, f'{DATASTORE} (Thames Water reservoir levels)', url,
                               period=newest, pair='reservoir_all', context_note=RESERVOIR_NOTE,
                               dateline_lead='Percent of usable capacity')
    facts = [mk(f'{thames:.0f}%', 'Lower Thames group'), mk(f'{lee:.0f}%', 'Lower Lee group')]
    if year_ago in series:
        facts.append(mk(_points(thames, series[year_ago][1]), 'Thames group, on a year earlier'))
    if len(same_date) >= 10:
        facts.append(mk(f'{sum(same_date) / len(same_date):.0f}%',
                        f'Thames group, average for the date since {min(series)[:4]}'))
    return facts


def harvest_reservoirs():
    return _harvest_csv(RESERVOIR_URL, reservoir_facts, 'reservoir levels')


# 2. TfL journeys by mode, per four-week reporting period.
JOURNEYS_URL = 'https://data.london.gov.uk/download/ep8ow/06a805f6-77c6-481a-8b08-ddef56afffdd/tfl-journeys-type.csv'
JOURNEYS_PAGE = 'https://data.london.gov.uk/dataset/public-transport-journeys-type-transport'
JOURNEYS_NOTE = 'TfL counts journeys by four-week reporting period'
JOURNEY_MODES = {'Bus journeys (m)': 'Bus', 'Underground journeys (m)': 'Underground',
                 'DLR Journeys (m)': 'DLR', 'Tram Journeys (m)': 'Tram',
                 'Overground Journeys (m)': 'Overground', 'London Cable Car Journeys (m)': 'Cable car',
                 'TfL Rail Journeys (m)': 'Elizabeth line'}
PERIODS_PER_YEAR = 13


def journey_facts(rows, url=JOURNEYS_PAGE):
    """`rows` are the CSV rows including the header. The newest period's
    journeys by mode, ranked (journeys_top), the total, and the total
    against the same period a year earlier (13 periods back)."""
    header = [c.strip() for c in rows[0]]
    idx = {name: header.index(name) for name in JOURNEY_MODES if name in header}
    if len(idx) < 4 or 'Period ending' not in header:
        raise ValueError(f'journeys header changed: {header}')
    end_i = header.index('Period ending')
    begin_i = header.index('Period beginning')
    periods = []
    for r in rows[1:]:
        try:
            end = _day_label(r[end_i]); begin = _day_label(r[begin_i])
        except (ValueError, IndexError):
            continue
        modes = {}
        for name, i in idx.items():
            try:
                modes[JOURNEY_MODES[name]] = _num(r[i])
            except (ValueError, IndexError):
                pass
        if modes:
            periods.append((end, begin, modes))
    if not periods:
        raise ValueError('no journey periods parsed')
    periods.sort()
    end, begin, modes = periods[-1]
    d0 = datetime.strptime(begin, '%Y-%m-%d'); d1 = datetime.strptime(end, '%Y-%m-%d')
    span = (f'{d0.day} {d0.strftime("%B")} to {d1.day} {d1.strftime("%B %Y")}'
            if d0.month != d1.month else f'{d0.day} to {d1.day} {d1.strftime("%B %Y")}')
    text = f'Four weeks, {span}'
    mk = lambda v, label, pair=None: fact(v, label, f'{DATASTORE} (TfL journeys)', url, period=end,
                                          pair=pair, context_note=JOURNEYS_NOTE, dateline_text=text)
    total = sum(modes.values())
    facts = [mk(f'{total:.1f} million', 'All modes')]
    if len(periods) > PERIODS_PER_YEAR:
        prev_total = sum(periods[-1 - PERIODS_PER_YEAR][2].values())
        change = _pct_change(total, prev_total)
        if change is not None:
            facts.append(mk(change, 'Change on the same period a year earlier'))
    for mode, v in sorted(modes.items(), key=lambda kv: -kv[1])[:4]:
        facts.append(mk(f'{v:.1f} million', mode, 'journeys_top'))
    return facts


def harvest_tfl_journeys():
    return _harvest_csv(JOURNEYS_URL, journey_facts, 'TfL journeys')


# 3. Congestion Charge zone: vehicles seen in charging hours, monthly.
CCZ_URL = 'https://data.london.gov.uk/download/2r88d/601a15a2-352c-46be-adae-e049556314a3/tfl-vehicles-c-charge-zone.csv'
CCZ_PAGE = 'https://data.london.gov.uk/dataset/camera-captures-and-confirmed-vehicles-seen-congestion-charge-zone-month'
CCZ_NOTE = 'TfL camera counts of vehicles in the zone during charging hours'


def congestion_facts(rows, url=CCZ_PAGE):
    header = [c.strip() for c in rows[0]]
    if not header[0].startswith('Month') or len(header) < 4:
        raise ValueError(f'congestion charge header changed: {header}')
    months = {}
    for r in rows[1:]:
        try:
            ym = _month_label(r[0])
            confirmed = _num(r[2]) if r[2].strip() else None
            days = _num(r[3]) if r[3].strip() else None
        except (ValueError, IndexError):
            continue
        if confirmed:
            months[ym] = (confirmed, days)
    if not months:
        raise ValueError('no congestion charge months parsed')
    ym = max(months)
    confirmed, days = months[ym]
    mk = lambda v, label: fact(v, label, f'{DATASTORE} (TfL Congestion Charge)', url, period=ym,
                               pair='ccz_all', context_note=CCZ_NOTE, map_zone='congestion_charge_zone')
    facts = [mk(f'{confirmed:,.0f}', 'Vehicles seen in charging hours')]
    if days:
        facts.append(mk(f'{confirmed / days:,.0f}', 'Per charging day'))
        facts.append(mk(f'{days:.0f}', 'Charging days'))
    prev = months.get(_shift_month(ym, 12))
    if prev:
        change = _pct_change(confirmed, prev[0])
        if change is not None:
            facts.append(mk(change, 'Change on a year earlier'))
    return facts


def harvest_congestion_charge():
    return _harvest_csv(CCZ_URL, congestion_facts, 'Congestion Charge')


# 4. Police force strength, monthly, full-time equivalents.
STRENGTH_URL = 'https://data.london.gov.uk/download/e7xoj/e442f07c-bc39-4c61-a62b-0e5957ea474f/Police_Force_Strength.csv'
STRENGTH_PAGE = 'https://data.london.gov.uk/dataset/police-force-strength'
STRENGTH_NOTE = 'Full-time equivalents, as the Mayor’s Office for Policing and Crime reports them'


def strength_facts(rows, url=STRENGTH_PAGE):
    header = [c.strip() for c in rows[0]]
    if header[:4] != ['Date', 'Police Officer Strength', 'Police Staff Strength', 'PCSO Strength']:
        raise ValueError(f'police strength header changed: {header}')
    months = {}
    for r in rows[1:]:
        try:
            months[_month_label(r[0])] = (_num(r[1]), _num(r[2]), _num(r[3]))
        except (ValueError, IndexError):
            continue
    if not months:
        raise ValueError('no police strength months parsed')
    ym = max(months)
    officers, staff, pcso = months[ym]
    mk = lambda v, label: fact(v, label, f'{DATASTORE} (MOPAC police strength)', url, period=ym,
                               pair='strength_all', context_note=STRENGTH_NOTE)
    facts = [mk(f'{officers:,.0f}', 'Police officers'), mk(f'{staff:,.0f}', 'Civilian staff'),
             mk(f'{pcso:,.0f}', 'Community support officers')]
    prev = months.get(_shift_month(ym, 12))
    if prev:
        change = _pct_change(officers, prev[0])
        if change is not None:
            facts.append(mk(change, 'Officers, change on a year earlier'))
    return facts


def harvest_police_strength():
    return _harvest_csv(STRENGTH_URL, strength_facts, 'police strength')


# 5. Arrests by the Metropolitan Police, monthly, from the custody dashboard.
ARRESTS_URL = ('https://data.london.gov.uk/download/2r7po/f8f/'
               'MPS%20Custody%20-%20Arrests%20-%202022%2001%20to%202026%2008.xlsx')
ARRESTS_PAGE = 'https://data.london.gov.uk/dataset/mps-custody-arrests-disposals-strip-searches'
ARRESTS_NOTE = 'Metropolitan Police custody records; the offence is the first recorded at arrest'


def arrests_facts(rows, url=ARRESTS_PAGE):
    """`rows` are the sheet's rows including the header: Arrest Year, Arrest
    Month, Arrest Month Name, Gender, Age Group, Ethnicity, First Arrest
    Offence, Domestic Abuse Flag, Arrest Count."""
    header = [str(c).strip() for c in rows[0]]
    need = ['Arrest Year', 'Arrest Month', 'First Arrest Offence', 'Domestic Abuse Flag', 'Arrest Count']
    if not all(n in header for n in need):
        raise ValueError(f'arrests header changed: {header}')
    yi, mi, oi, di, ci = (header.index(n) for n in need)
    months = {}
    for r in rows[1:]:
        try:
            ym = f'{int(r[yi]):04d}-{int(r[mi]):02d}'
            n = int(r[ci])
        except (TypeError, ValueError, IndexError):
            continue
        m = months.setdefault(ym, {'total': 0, 'offences': {}, 'da': 0})
        m['total'] += n
        off = str(r[oi]).strip()
        m['offences'][off] = m['offences'].get(off, 0) + n
        if str(r[di]).strip().lower() == 'yes':
            m['da'] += n
    if not months:
        raise ValueError('no arrest months parsed')
    ym = max(months)
    m = months[ym]
    # The dashboard's largest bucket is "Other Offence", which names nothing;
    # the most common NAMED offence is the fact (measured on August 2026:
    # 4,979 of 12,731 arrests were "Other Offence").
    named = {k: v for k, v in m['offences'].items() if not k.lower().startswith('other')} or m['offences']
    top = max(named.items(), key=lambda kv: kv[1])
    mk = lambda v, label: fact(v, label, f'{DATASTORE} (MPS custody data)', url, period=ym,
                               pair='arrests_all', context_note=ARRESTS_NOTE)
    facts = [mk(f'{m["total"]:,}', 'Arrests'), mk(f'{top[1]:,}', f'Most common offence: {top[0]}'),
             mk(f'{m["da"]:,}', 'Flagged as domestic abuse')]
    prev = months.get(_shift_month(ym, 12))
    if prev:
        change = _pct_change(m['total'], prev['total'])
        if change is not None:
            facts.append(mk(change, 'Change on a year earlier'))
    return facts


def harvest_arrests():
    return _harvest_xlsx(ARRESTS_URL, arrests_facts, 'arrests', sheet='Arrests')


# 6. Unemployment, London against the UK, rolling quarter (ONS via the GLA).
UNEMPLOYMENT_URL = 'https://data.london.gov.uk/download/e5mnw/8a29ec0c-9de3-4777-832f-49ef8c2b4d14/unemployment-region.xlsx'
UNEMPLOYMENT_PAGE = 'https://data.london.gov.uk/dataset/unemployment-rate-region'
UNEMPLOYMENT_NOTE = 'ONS Labour Force Survey estimates, people aged 16 and over'
MONTHS_FULL = {'Jan': 'January', 'Feb': 'February', 'Mar': 'March', 'Apr': 'April', 'May': 'May',
               'Jun': 'June', 'Jul': 'July', 'Aug': 'August', 'Sep': 'September', 'Oct': 'October',
               'Nov': 'November', 'Dec': 'December'}


def _quarter_text(label):
    """'Apr-Jun 2026' -> 'April to June 2026'."""
    m = re.fullmatch(r'([A-Z][a-z]{2})-([A-Z][a-z]{2}) (\d{4})', label.strip())
    if not m:
        raise ValueError(f'unexpected quarter label {label!r}')
    return f'{MONTHS_FULL[m.group(1)]} to {MONTHS_FULL[m.group(2)]} {m.group(3)}'


def unemployment_facts(rows, url=UNEMPLOYMENT_PAGE):
    """`rows` are the 'Long-term trend' sheet: a label column ('Apr-Jun
    2026'), London unemployed and rate, a gap, UK unemployed and rate."""
    data = []
    for r in rows:
        if not r or not isinstance(r[0], str):
            continue
        try:
            text = _quarter_text(r[0])
        except ValueError:
            continue
        try:
            data.append((text, float(r[1]), float(r[2]), float(r[4]), float(r[5])))
        except (TypeError, ValueError, IndexError):
            continue
    if len(data) < 5:
        raise ValueError(f'unemployment sheet shape changed: {len(data)} quarters parsed')
    text, ldn_n, ldn_rate, uk_n, uk_rate = data[-1]
    period = f'{int(text[-4:])}-{list(MONTHS_FULL.values()).index(text.split(" to ")[1].rsplit(" ", 1)[0]) + 1:02d}'
    mk = lambda v, label: fact(v, label, f'{DATASTORE} (ONS unemployment)', url, period=period,
                               pair='jobless_all', context_note=UNEMPLOYMENT_NOTE, dateline_text=text)
    # Bare labels: the opener already says "Unemployment".
    facts = [mk(f'{ldn_rate:.1f}%', 'London rate'), mk(f'{uk_rate:.1f}%', 'U.K. rate'),
             mk(f'{round(ldn_n, -3):,.0f}', 'Londoners unemployed')]
    if len(data) >= 13:   # rolling quarters step by a month, so a year is 12 rows back
        facts.append(mk(_rate_change(ldn_rate, data[-13][2]), 'London rate, on a year earlier'))
    return facts


def _rate_change(now, before):
    d = now - before
    return f'+{d:.1f} points' if d > 0.05 else f'−{abs(d):.1f} points' if d < -0.05 else 'unchanged'


def harvest_unemployment():
    return _harvest_xlsx(UNEMPLOYMENT_URL, unemployment_facts, 'unemployment', sheet='Long-term trend')


# 7. People freed from lifts by the fire brigade, monthly.
LIFTS_URL = ('https://data.london.gov.uk/download/2g980/46561645-a73e-473e-a45c-868b8599a280/'
             'Shut%20in%20lifts%20incidents%20attended%20by%20LFB%20in%20last%2036%20months.xlsx')
LIFTS_PAGE = 'https://data.london.gov.uk/dataset/shut-in-lift-releases-lift-entrapments-attended-by-lfb'
LIFTS_NOTE = 'What the London Fire Brigade calls “shut in lift” releases'
LIFTS_LEAD = 'Freed by the London Fire Brigade'


def lifts_facts(rows, ym, url=LIFTS_PAGE, prev_rows=None):
    """`rows` are one month's records as dicts (the sheet's header names);
    `prev_rows` the same month a year earlier, when the file has it."""
    boroughs = {}
    for r in rows:
        b = str(r.get('Borough') or '').strip()
        if b:
            boroughs[b] = boroughs.get(b, 0) + 1
    y, m = (int(x) for x in ym.split('-'))
    days = (datetime(y + (m == 12), m % 12 + 1, 1) - datetime(y, m, 1)).days
    mk = lambda v, label: fact(v, label, f'{DATASTORE} (LFB lift releases)', url, period=ym,
                               pair='lifts_all', context_note=LIFTS_NOTE, dateline_lead=LIFTS_LEAD)
    facts = [mk(f'{len(rows):,}', 'Callouts'), mk(f'{len(rows) / days:.1f}', 'Per day')]
    if boroughs:
        name, n = max(boroughs.items(), key=lambda kv: kv[1])
        facts.append(mk(f'{n:,}', f'Most: {name.title()}'))
    if prev_rows:
        change = _pct_change(len(rows), len(prev_rows))
        if change is not None:
            facts.append(mk(change, 'Change on a year earlier'))
    return facts


def harvest_lift_releases():
    rows = _download_xlsx_rows(LIFTS_URL)
    if not rows:
        return [], 'lift releases download failed'
    header = [str(h).strip() for h in rows[0]]
    if 'DateTimeOfCall' not in header or 'Borough' not in header:
        return [], f'lift releases header changed: {header[:8]}'
    by_month = {}
    for row in rows[1:]:
        rec = dict(zip(header, row))
        when = rec.get('DateTimeOfCall')
        if isinstance(when, str):
            try:
                when = datetime.fromisoformat(when[:19])
            except ValueError:
                continue
        if not isinstance(when, datetime):
            continue
        by_month.setdefault(when.strftime('%Y-%m'), []).append(rec)
    this_month = datetime.now(timezone.utc).strftime('%Y-%m')
    months = sorted(m for m in by_month if m < this_month)
    if not months:
        return [], 'no complete month in the lift releases file'
    ym = months[-1]
    if len(by_month[ym]) < ANIMALS_MIN_ROWS:
        return [], f'only {len(by_month[ym])} lift releases in {ym}; refusing a partial month'
    return lifts_facts(by_month[ym], ym, prev_rows=by_month.get(_shift_month(ym, 12))), None



# --- London Fire Brigade incidents, monthly, from the full incident file ----
# The 81 MB "LFB Incident data from 2024 onwards" XLSX on the Datastore
# (dataset em8xy, OGL), every incident with its type, borough, first-engine
# attendance time and notional cost. Same monthly cache and refetch rule as
# the Met dashboard: one download when a new month is expected, at most one
# attempt a day while it is late. Measured on July 2026: 14,307 incidents,
# 3,067 fires, 5,549 false alarms, 5,685 special services, first engine on
# scene in 5 min 55 s on average, £9.6 million notional cost.
LFB_URL = 'https://data.london.gov.uk/download/em8xy/58m/LFB%20Incident%20data%20from%202024%20onwards.xlsx'
LFB_PAGE = 'https://data.london.gov.uk/dataset/london-fire-brigade-incident-records'
LFB_CACHE = Path(__file__).parent / 'data' / 'lfb_incidents.json'
LFB_SOURCE = 'London Datastore (LFB incident records)'
LFB_NOTE = 'Every incident the London Fire Brigade attended; special services are rescues, floods, crashes and the like'


def lfb_aggregate(rows):
    """Sheet rows (header first) -> {ym: {'total', 'fires', 'primary_fires',
    'false_alarms', 'special', 'boroughs': {}, 'attendance_s': mean or None,
    'cost': sum}}. Raises ValueError on a changed header."""
    header = [str(h).strip() for h in rows[0]]
    need = ['DateOfCall', 'IncidentGroup', 'StopCodeDescription', 'IncGeo_BoroughName',
            'FirstPumpArriving_AttendanceTime', 'Notional Cost (£)']
    if not all(n in header for n in need):
        raise ValueError(f'LFB header changed: {header[:12]}')
    di, gi, si, bi, ai, ci = (header.index(n) for n in need)
    months = {}
    att = {}
    for r in rows[1:]:
        when = r[di]
        if isinstance(when, str):
            try:
                when = datetime.fromisoformat(when[:19])
            except ValueError:
                continue
        if not isinstance(when, datetime):
            continue
        ym = when.strftime('%Y-%m')
        m = months.setdefault(ym, {'total': 0, 'fires': 0, 'primary_fires': 0, 'false_alarms': 0,
                                   'special': 0, 'boroughs': {}, 'attendance_s': None, 'cost': 0})
        m['total'] += 1
        g = str(r[gi] or '')
        if g == 'Fire':
            m['fires'] += 1
            if str(r[si] or '') == 'Primary Fire':
                m['primary_fires'] += 1
        elif g == 'False Alarm':
            m['false_alarms'] += 1
        elif g == 'Special Service':
            m['special'] += 1
        b = str(r[bi] or '').strip()
        if b:
            m['boroughs'][b] = m['boroughs'].get(b, 0) + 1
        a = r[ai]
        if isinstance(a, (int, float)):
            att.setdefault(ym, []).append(float(a))
        c = r[ci]
        if isinstance(c, (int, float)):
            m['cost'] += float(c)
    for ym, vals in att.items():
        months[ym]['attendance_s'] = sum(vals) / len(vals)
    if not months:
        raise ValueError('no LFB rows parsed')
    return months


def lfb_months(cache_path=LFB_CACHE, load_rows=None):
    """ym -> aggregate from the cache, refreshed when needs_refetch() says so.
    A failed download leaves the cache as it was."""
    cache = _read_cache(cache_path)
    if needs_refetch(cache, url=LFB_URL):
        rows = (load_rows or _download_xlsx_rows)(LFB_URL, timeout=600)
        cache['fetched'] = datetime.now(timezone.utc).isoformat()
        if rows:
            try:
                cache['months'] = lfb_aggregate(rows)
                cache['etag'] = head_etag(LFB_URL)
                print(f'LFB incidents: fetched, {len(cache["months"])} months.', file=sys.stderr)
            except ValueError as e:
                print(f'LFB incidents: {e}', file=sys.stderr)
        else:
            print('LFB incidents: download failed; using the cache as it stands.', file=sys.stderr)
        _write_cache(cache, cache_path)
    return cache.get('months') or {}


def _minutes_seconds(s):
    s = int(round(s))
    return f'{s // 60} min {s % 60} s'


def lfb_facts(m, ym, prev=None, url=LFB_PAGE):
    """One month's fire brigade card, pair "lfb_all": incidents, fires, false
    alarms, special services, the borough with the most, the average first
    engine's time to arrive, the notional cost, and the change on a year
    earlier when the file has it."""
    mk = lambda v, label: fact(v, label, LFB_SOURCE, url, period=ym, pair='lfb_all', context_note=LFB_NOTE)
    facts = [mk(f'{m["total"]:,}', 'Incidents attended'), mk(f'{m["fires"]:,}', 'Fires'),
             mk(f'{m["false_alarms"]:,}', 'False alarms'), mk(f'{m["special"]:,}', 'Special services')]
    if m.get('boroughs'):
        name, n = max(m['boroughs'].items(), key=lambda kv: kv[1])
        facts.append(mk(f'{n:,}', f'Most: {name.title()}'))
    if m.get('attendance_s'):
        facts.append(mk(_minutes_seconds(m['attendance_s']), 'First engine on scene, average'))
    if m.get('cost'):
        facts.append(mk(f'£{m["cost"] / 1e6:.1f} million', 'Notional cost'))
    if prev and prev.get('total'):
        change = _pct_change(m['total'], prev['total'])
        if change is not None:
            facts.append(mk(change, 'Change on a year earlier'))
    return facts


def harvest_lfb_incidents():
    months = lfb_months()
    this_month = datetime.now(timezone.utc).strftime('%Y-%m')
    complete = sorted(m for m in months if m < this_month)
    if not complete:
        return [], 'no complete month in the LFB incident cache'
    ym = complete[-1]
    if months[ym]['total'] < 1000:
        return [], f'only {months[ym]["total"]} LFB incidents in {ym}; refusing a partial month'
    return lfb_facts(months[ym], ym, prev=months.get(_shift_month(ym, 12))), None



# --- What is on sale in London: Ticketmaster's Discovery API (live) --------
# Chosen over Skiddle on 29 August 2026 (see SESSION_SUMMARY.md); the key
# arrived 12 September and is in the Keychain (london-index /
# ticketmaster-api-key), the Consumer Key of the developer account's
# auto-created app, quota 5,000 calls a day. Seven calls a run. Counts only
# are published, never listing content, which keeps clear of the API's
# content terms. ⚠️ A "listing" is one performance or timed entry: a West
# End theatre lists eight a week, and Miscellaneous is mostly attractions
# and family shows, so the labels say so. segmentName is the exact filter
# (measured: the five segments plus 'Undefined' sum to the total);
# classificationName matches genres too and overcounts.
TM_URL = 'https://app.ticketmaster.com/discovery/v2/events.json'
TM_PAGE = 'https://www.ticketmaster.co.uk/'
TM_SOURCE = 'Ticketmaster (Discovery API)'
TM_NOTE = 'Ticketmaster’s own listings; each performance or timed entry counts once'
TM_LEAD = 'Ticketmaster listings, next seven days'
TM_SEGMENTS = (('Arts & Theatre', 'Theatre and arts'), ('Music', 'Music'),
               ('Miscellaneous', 'Attractions and other'), ('Sports', 'Sport'))


def _tm_key():
    r = subprocess.run(['security', 'find-generic-password', '-a', 'london-index',
                        '-s', 'ticketmaster-api-key', '-w'], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _tm_total(key, **params):
    """page.totalElements for a London query, or None."""
    q = dict(apikey=key, city='London', countryCode='GB', size=1, **params)
    d = get_json(TM_URL + '?' + urllib.parse.urlencode(q), timeout=30)
    if not isinstance(d, dict) or 'page' not in d:
        return None
    return d['page'].get('totalElements')


def _tm_listings(key, start, end):
    """Every London listing in the window, paged per segment at 200 a page
    (the API's deep-paging cap is 1,000 items a query, and a week of London
    is over that, but no segment is). Listings flagged `test` are dropped.
    Returns (listings, complete): complete is False if any page failed."""
    listings = []
    complete = True
    for seg in [s for s, _ in TM_SEGMENTS] + ['Film', 'Undefined']:
        page = 0
        while True:
            q = dict(apikey=key, city='London', countryCode='GB', size=200, page=page,
                     startDateTime=start, endDateTime=end, segmentName=seg)
            d = get_json(TM_URL + '?' + urllib.parse.urlencode(q), timeout=30)
            if not isinstance(d, dict) or 'page' not in d:
                complete = False
                break
            listings += [e for e in d.get('_embedded', {}).get('events', []) if not e.get('test')]
            if page + 1 >= d['page'].get('totalPages', 0) or page >= 4:
                break
            page += 1
    return listings, complete


PERFORMING_SEGMENTS = {'Arts & Theatre', 'Music'}


def events_listing_facts(listings, url=TM_PAGE):
    """From the week's PERFORMANCES (Arts & Theatre and Music listings): the
    venues with the most (venues_top, ranked, top four) and the busiest day
    (into events_all). Timed-entry attractions are left out here: on the
    first live render the venue ranking was Twist Museum 243, The View from
    The Shard 160, Marble Arch Place 104, every one an attraction selling
    entry slots, which is not what "most on sale, by venue" promises."""
    venues = {}
    days = {}
    for e in listings:
        seg = (e.get('classifications') or [{}])[0].get('segment', {}).get('name')
        if seg not in PERFORMING_SEGMENTS:
            continue
        v = (e.get('_embedded', {}).get('venues') or [{}])[0].get('name')
        if v:
            venues[v] = venues.get(v, 0) + 1
        day = (e.get('dates', {}).get('start') or {}).get('localDate')
        if day:
            days[day] = days.get(day, 0) + 1
    facts = []
    if days:
        day, n = max(days.items(), key=lambda kv: (kv[1], kv[0]))
        d = datetime.strptime(day, '%Y-%m-%d')
        facts.append(fact(f'{n:,}', f'Most performances: {d.strftime("%A")} {d.day} {d.strftime("%B")}',
                          TM_SOURCE, url, pair='events_all', context_note=TM_NOTE, dateline_lead=TM_LEAD))
    ranked = sorted(venues.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
    if len(ranked) == 4:
        for v, n in ranked:
            facts.append(fact(f'{n:,}', v, TM_SOURCE, url, pair='venues_top', context_note=TM_NOTE,
                              dateline_lead=TM_LEAD))
    return facts


def events_facts(counts, url=TM_PAGE):
    """`counts`: {'week': n, 'day': n, 'month': n, 'segments': {segment: n}}.
    Pair "events_all", fixed opener; live, so the second line carries the
    clock behind TM_LEAD."""
    mk = lambda v, label: fact(f'{v:,}', label, TM_SOURCE, url, pair='events_all',
                               context_note=TM_NOTE, dateline_lead=TM_LEAD)
    facts = [mk(counts['week'], 'All events')]
    if counts.get('day') is not None:
        facts.append(mk(counts['day'], 'Starting in the next 24 hours'))
    for seg, label in TM_SEGMENTS:
        n = counts.get('segments', {}).get(seg)
        if n is not None:
            facts.append(mk(n, label))
    if counts.get('month') is not None:
        facts.append(mk(counts['month'], 'Listed for the next 30 days'))
    return facts


def harvest_events():
    key = _tm_key()
    if not key:
        return [], 'no Ticketmaster key in Keychain (london-index / ticketmaster-api-key)'
    now = datetime.now(timezone.utc).replace(microsecond=0)
    fmt = '%Y-%m-%dT%H:%M:%SZ'
    start = now.strftime(fmt)
    week = _tm_total(key, startDateTime=start, endDateTime=(now + timedelta(days=7)).strftime(fmt))
    if not week:
        return [], 'Ticketmaster answered no seven-day total (bad key, quota, or an outage)'
    counts = {'week': week,
              'day': _tm_total(key, startDateTime=start, endDateTime=(now + timedelta(days=1)).strftime(fmt)),
              'month': _tm_total(key, startDateTime=start, endDateTime=(now + timedelta(days=30)).strftime(fmt)),
              'segments': {}}
    week_end = (now + timedelta(days=7)).strftime(fmt)
    for seg, _label in TM_SEGMENTS:
        n = _tm_total(key, startDateTime=start, endDateTime=week_end, segmentName=seg)
        if n is not None:
            counts['segments'][seg] = n
    facts = events_facts(counts)
    # The week's listings themselves, for the busiest day and the venues:
    # about ten more calls. An incomplete page set drops these shapes rather
    # than ranking venues from part of a week.
    listings, complete = _tm_listings(key, start, week_end)
    if complete and listings:
        facts += events_listing_facts(listings)
    return facts, None


# --- The West End's year: SOLT and UK Theatre's annual report ---------------
# The Society of London Theatre's weekly box office data is members-only
# (solt.co.uk/box-office-sales-data answers with a login wall), but its
# annual report with UK Theatre is a public PDF whose second page licenses
# quotation "for non-commercial purposes provided that the Society of London
# Theatre and UK Theatre are credited as the source". Added 19 September
# 2026, Chris's call, as the one London-specific, licensed ticket-sales
# source found; the BFI weekly box office file is UK-wide, and West End
# weekly grosses are published nowhere (the Broadway League does it for
# Broadway; SOLT does not).
#
# ⚠️ The figures are TRANSCRIBED, not parsed. The report is prose ("The West
# End generated record revenue of £1.084 billion in 2025 (up 4.1%) with
# 17.64 million attendances (up 3.16%)"), the 2026 edition is the only one
# at this URL shape (the 2025 and 2024 guesses 404), so a regex would be
# validated against exactly one document and break silently on the next
# rewording. A dict keyed by the year the figures describe, each value the
# publisher's own string, is the honest shape: test_london_index_harvest.py
# pins every value against the sentences pdftotext read out of the PDF, so a
# typo here fails a test rather than posting. The spent-fact guard posts
# the card once per value, so a year's figures post once and the vein then
# waits for the next report (published each March) to be added here.
# _west_end_newer_report() probes for that report each run and refuses to
# post the old year once a newer one exists, so the omission is loud.
WEST_END_SOURCE = 'Society of London Theatre and UK Theatre'
WEST_END_REPORTS = {
    '2025': {
        'page': 'https://uktheatre.org/theatre-in-the-uk-2026/',
        'report': 'Theatre in the UK 2026',
        'facts': [
            ('Attendances', '17.64 million'),
            ('Attendances, change on 2024', '+3.16%'),
            ('Box office', '£1.084 billion'),
            ('Box office, change on 2024', '+4.1%'),
            ('Performances, change on 2024', '+3.26%'),
            ('Average occupancy', '84%'),
            ('Tickets priced over £250', '0.38%'),
        ],
    },
}
WEST_END_NOTE = ('West End theatres as counted by the Society of London Theatre, '
                 'in “{report}”, its annual report with UK Theatre')


def west_end_facts(year, entry):
    """One year's West End card from its transcribed entry. Pair
    'west_end_all', period the year the figures describe (the card's second
    line), the report named in the footnote."""
    note = WEST_END_NOTE.format(report=entry['report'])
    return [fact(v, label, WEST_END_SOURCE, entry['page'], period=year,
                 pair='west_end_all', context_note=note)
            for label, v in entry['facts']]


def _url_exists(url):
    """HEAD the URL: True on 200, False on anything else or no answer."""
    r = subprocess.run(['curl', '-sIL', '--max-time', '20', '-o', '/dev/null',
                        '-w', '%{http_code}', '-A', 'london-index bot', url],
                       capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == '200'


def _west_end_newer_report(latest_year, exists=None):
    """The page URL of a report newer than the one transcribed, or None. A
    report published in year N describes year N-1, so the report after the
    one for `latest_year` is theatre-in-the-uk-{latest_year + 2}. WordPress
    answers 404 for a slug that does not exist (the 2025 and 2024 guesses
    did on 19 September 2026), so a 200 is a real page. `exists` is looked
    up at call time so a test can stand in for the network."""
    exists = exists or _url_exists
    url = f'https://uktheatre.org/theatre-in-the-uk-{int(latest_year) + 2}/'
    return url if exists(url) else None


# --- The longest-running West End shows: SOLT's own list ------------------
# solt.co.uk/data-and-research carries "Longest-running shows in West End
# History": two ordered lists of 20, productions and musicals, each row
# "<strong>Title</strong> (running since 1952) – Over 29,902 performances"
# or "(1988 production, now closed) – 10,013 performances", closed by
# "Information supplied to Society of London Theatre in January 2025".
# Added 20 September 2026, Chris's call. Only the productions list is read:
# three of the musicals' top four are the same rows, so a second card would
# be the first one again. A running show's count is a floor ("Over"), and
# the value keeps the word; the date the counts were supplied is the card's
# period. The list moves when SOLT updates it (January, on the evidence of
# one date), and the spent-fact guard posts each set of values once.
SOLT_SHOWS_PAGE = 'https://solt.co.uk/data-and-research/'
SOLT_SHOWS_SOURCE = 'Society of London Theatre'
SOLT_SHOWS_HEADING = 'longest-running productions in West End history'
SOLT_SHOWS_NOTE = ('Performances as counted for the Society of London Theatre; '
                   'a show still running has given more since')
SOLT_SHOWS_LEAD = 'Performances counted'
MONTHS = {m: i for i, m in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December'], 1)}


def _strip_tags(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', s).replace('&nbsp;', ' ')
                  .replace('&amp;', '&').replace('&#8217;', '’')).strip()


def parse_solt_shows(html):
    """({'rows': [(title, status, over, count), ...], 'period': 'YYYY-MM'})
    from the productions list, or None when the heading, its list, its
    date or a well-formed row cannot be found. Rows are in the page's own
    order; a list whose counts do not fall rank by rank is refused, since
    a ranked card built from it would be wrong."""
    i = html.lower().find(SOLT_SHOWS_HEADING.lower())
    if i == -1:
        return None
    m = re.search(r'<ol[^>]*>(.*?)</ol>', html[i:], re.S)
    if not m:
        return None
    rows = []
    for li in re.findall(r'<li[^>]*>(.*?)</li>', m.group(1), re.S):
        text = _strip_tags(li)
        r = re.match(r'^(.*?)\s*\(([^)]*)\)\s*[–-]\s*(over\s+)?([\d,]+)\s*performances', text, re.I)
        if not r:
            return None
        title, status, over, count = r.groups()
        rows.append((title.strip(), status.strip(), bool(over), int(count.replace(',', ''))))
    if len(rows) < TOP_RANKED_COUNT:
        return None
    if any(rows[k][3] < rows[k + 1][3] for k in range(len(rows) - 1)):
        return None
    d = re.search(r'supplied to Society of London Theatre in (\w+) (\d{4})', html[i + m.end():i + m.end() + 2000])
    if not d or d.group(1) not in MONTHS:
        return None
    return {'rows': rows, 'period': f'{d.group(2)}-{MONTHS[d.group(1)]:02d}'}


def _show_label(title, status):
    """'The Mousetrap, since 1952' for a running show, 'The Woman in Black,
    1989 production, closed' for one that has closed; the status is SOLT's
    own text with "running" and "now" dropped."""
    if 'closed' in status:
        return f'{title}, {status.replace("running since", "since").replace("now closed", "closed")}'
    return f'{title}, {status.replace("running since", "since")}'


def solt_show_facts(parsed, url=SOLT_SHOWS_PAGE):
    """The top TOP_RANKED_COUNT productions, pair 'shows_top'."""
    facts = []
    for title, status, over, count in parsed['rows'][:TOP_RANKED_COUNT]:
        value = f'Over {count:,}' if over else f'{count:,}'
        facts.append(fact(value, _show_label(title, status), SOLT_SHOWS_SOURCE, url,
                          period=parsed['period'], pair='shows_top',
                          context_note=SOLT_SHOWS_NOTE, dateline_lead=SOLT_SHOWS_LEAD))
    return facts


def harvest_west_end_shows():
    html = curl(SOLT_SHOWS_PAGE, timeout=30)
    if not html:
        return [], 'SOLT data-and-research page could not be read'
    parsed = parse_solt_shows(html)
    if not parsed:
        return [], 'SOLT longest-running productions list not found or not well formed (page changed?)'
    return solt_show_facts(parsed), None


def harvest_west_end():
    year = max(WEST_END_REPORTS)
    newer = _west_end_newer_report(year)
    if newer:
        return [], (f'a newer report exists at {newer}; transcribe it into '
                    f'WEST_END_REPORTS before the {year} figures post again')
    return west_end_facts(year, WEST_END_REPORTS[year]), None


# --- London's cinemas: the BFI Statistical Yearbook's exhibition tables ----
# The BFI's weekly box office file is UK-wide with no regional split, but
# its Statistical Yearbook's exhibition tables carry one London row: Table 1
# gives screens, sites, admissions, admissions per head and the average
# ticket price by ISBA television region. ⚠️ That "London" is ITV's London
# region, 13.6 million people, wider than Greater London (Table 2's ONS
# "London", 8.9 million, has screens and sites but no admissions), and the
# footnote says so. Added 19 September 2026, Chris's call, as the second
# London-specific ticket-sales source; the BFI's footer is "All rights
# reserved", not the Open Government Licence most veins here credit, and
# only bare figures with a credit are published.
#
# The yearbook page lists each edition under its own year heading, newest
# first, as bare core-cms.bfi.org.uk/media/<id>/download links whose
# filenames are only in their Content-Disposition headers, so the newest
# edition's exhibition file is found by HEADing that section's links until
# one is named "-exhibition". The page is 1.1 MB and the section 17 links,
# so the answer is cached at BFI_CACHE for BFI_RECHECK_DAYS, and a page or
# file that cannot be read keeps the cache rather than blanking the vein.
# ⚠️ As of 19 September 2026 the newest edition on the page is Yearbook
# 2024, whose tables describe 2023; no 2025 edition is listed, so the card's
# "latest year" sentence names a two-year-old year, which is the truth.
BFI_YEARBOOK_PAGE = 'https://www.bfi.org.uk/industry-data-insights/statistical-yearbook'
BFI_SOURCE = 'BFI Statistical Yearbook'
BFI_CACHE = Path(__file__).parent / 'data' / 'bfi_exhibition.json'
BFI_RECHECK_DAYS = 7
BFI_TABLE1_HEADER = 'ISBA TV region'
BFI_LONDON_ROW = 'London'
# Column header in Table 1 -> (label, formatter). Population is read too,
# for the footnote, but is not a fact.
BFI_COLUMNS = {
    'Admissions (million)': ('Cinema admissions', lambda v: f'{v:.1f} million'),
    'Admissions per head of population': ('Admissions per head', lambda v: f'{v:.2f}'),
    'Average ticket price (£)': ('Average ticket price', lambda v: f'£{v:.2f}'),
    'Screens': ('Screens', lambda v: f'{int(round(v)):,}'),
    'Sites': ('Cinemas', lambda v: f'{int(round(v)):,}'),
    '% of total screens': ('Share of UK screens', lambda v: f'{v:.1f}%'),
}
# What a London row must look like to be believed: a changed column order
# would otherwise put a screen count where a price goes. Wide bounds,
# checked against the 2023 row (29.8m, 1,031 screens, £9.11).
BFI_BOUNDS = {'Admissions (million)': (5, 100), 'Screens': (200, 3000),
              'Sites': (50, 600), 'Average ticket price (£)': (3, 30),
              'Admissions per head of population': (0.5, 10),
              '% of total screens': (5, 50), 'Population (million)': (5, 20)}


def _bfi_head_filename(url):
    """The filename in the URL's Content-Disposition header, or ''."""
    r = subprocess.run(['curl', '-sIL', '--max-time', '20', '-A', 'london-index bot', url],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return ''
    m = re.search(r'filename=("?)([^";\r\n]+)\1', r.stdout, re.I)
    return m.group(2) if m else ''


def bfi_exhibition_link(html, head=_bfi_head_filename):
    """(edition_year, download_url) for the newest edition's exhibition
    tables, or None. The newest edition is the first year heading on the
    page; its links run to the next heading. `head` returns a URL's
    Content-Disposition filename, injected so tests never touch the
    network."""
    heads = [(m.start(), int(m.group(1)))
             for m in re.finditer(r'<h2[^>]*>(\d{4})</h2>', html)]
    if not heads:
        return None
    start, year = heads[0]
    end = heads[1][0] if len(heads) > 1 else len(html)
    seen = set()
    for m in re.finditer(r'href="(https://core-cms\.bfi\.org\.uk/media/\d+/download)"', html[start:end]):
        url = m.group(1)
        if url in seen:
            continue
        seen.add(url)
        if '-exhibition' in head(url).lower():
            return year, url
    return None


def bfi_london_row(df):
    """Table 1's London row as {column header: float}, plus the year the
    table's own title names: ({...}, '2023'). None when the header row, the
    London row or the year cannot be found, or a value is outside
    BFI_BOUNDS."""
    title_year = None
    header_row = None
    for i in range(len(df)):
        cell = str(df.iloc[i, 0]).strip()
        m = re.search(r'Table 1:.*?, (\d{4}) \(', cell)
        if m:
            title_year = m.group(1)
        if cell == BFI_TABLE1_HEADER:
            header_row = i
            break
    if header_row is None or title_year is None:
        return None
    headers = [str(c).strip() for c in df.iloc[header_row, :]]
    for i in range(header_row + 1, len(df)):
        if str(df.iloc[i, 0]).strip() != BFI_LONDON_ROW:
            continue
        row = {}
        for j, hd in enumerate(headers):
            v = df.iloc[i, j]
            if hd and isinstance(v, (int, float)) and v == v:
                row[hd] = float(v)
        for col, (lo, hi) in BFI_BOUNDS.items():
            if col not in row or not lo <= row[col] <= hi:
                return None
        return row, title_year
    return None


def cinema_facts(row, year, url=BFI_YEARBOOK_PAGE):
    """The London cinema card from Table 1's London row. Pair 'cinema_all',
    period the table's year; the footnote names the region the row counts."""
    note = (f'ITV’s London television region, {row["Population (million)"]:.1f} million '
            f'people, wider than Greater London')
    return [fact(fmt(row[col]), label, BFI_SOURCE, url, period=year,
                 pair='cinema_all', context_note=note)
            for col, (label, fmt) in BFI_COLUMNS.items()]


def _bfi_fetch_row():
    """Read the newest edition's London row off the live site: (row, year,
    edition) or (None, reason)."""
    html = curl(BFI_YEARBOOK_PAGE, timeout=40)
    if not html:
        return None, 'BFI yearbook page could not be read'
    link = bfi_exhibition_link(html)
    if not link:
        return None, 'no exhibition tables link found on the BFI yearbook page (layout changed?)'
    edition, url = link
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'exhibition.ods'
        r = subprocess.run(['curl', '-sS', '-L', '--max-time', '60', '-A', 'london-index bot',
                            '-o', str(path), url], capture_output=True)
        if r.returncode != 0 or not path.exists():
            return None, 'BFI exhibition tables download failed'
        try:
            import pandas as pd
            df = pd.read_excel(path, engine='odf', sheet_name='T1', header=None)
        except Exception as e:  # noqa: BLE001 - a missing sheet or engine is "cannot read"
            return None, f'BFI exhibition tables could not be parsed: {e}'
    parsed = bfi_london_row(df)
    if not parsed:
        return None, 'BFI Table 1 has no readable London row (layout changed?)'
    row, year = parsed
    return (row, year, edition), None


def harvest_london_cinema(cache_path=BFI_CACHE, fetch=_bfi_fetch_row, now=None):
    now = now or datetime.now(timezone.utc)
    cache = None
    try:
        cache = json.loads(Path(cache_path).read_text())
    except (OSError, ValueError):
        cache = None
    fresh = bool(cache) and (now - datetime.fromisoformat(cache['checked'])) < timedelta(days=BFI_RECHECK_DAYS)
    if not fresh:
        got, err = fetch()
        if got:
            row, year, edition = got
            cache = {'row': row, 'year': year, 'edition': edition, 'checked': now.isoformat()}
            tmp = Path(str(cache_path) + '.tmp')
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(cache))
            tmp.replace(cache_path)
        elif not cache:
            return [], err
        else:
            print(f'london_cinema: {err}; using the cached {cache["year"]} row', file=sys.stderr)
    return cinema_facts(cache['row'], cache['year']), None


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
    'police_spotlight': harvest_police_spotlight,
    'cycle_hires': harvest_cycle_hires,
    'laqn': harvest_laqn,
    'dcms_museums': harvest_dcms_museums,
    # Added 12 September 2026, the morning after the same crime card went
    # out twice in five hours: four veins whose figures change on their own
    # cadence, none needing a key. See each harvester's own comment.
    'stop_search': harvest_stop_search,
    'house_prices': harvest_house_prices,
    'house_price_spotlight': harvest_house_price_spotlight,
    'road_works': harvest_road_works,
    'lfb_animals': harvest_lfb_animals,
    'rail_departures': harvest_rail_departures,
    'rail_station': harvest_rail_station,
    'river_gauge': harvest_river_gauge,
    # The seven London Datastore series, 12 September 2026.
    'reservoirs': harvest_reservoirs,
    'tfl_journeys': harvest_tfl_journeys,
    'congestion_charge': harvest_congestion_charge,
    'police_strength': harvest_police_strength,
    'arrests': harvest_arrests,
    'unemployment': harvest_unemployment,
    'lift_releases': harvest_lift_releases,
    'lfb_incidents': harvest_lfb_incidents,
    'events': harvest_events,
    'museum_spotlight': harvest_museum_spotlight,
    # The two ticket-sales veins, 19 September 2026: see each one's comment.
    'west_end': harvest_west_end,
    'london_cinema': harvest_london_cinema,
    'west_end_shows': harvest_west_end_shows,
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
