# London Index

The source code behind **London Index**, [**@london-index.bsky.social**](https://bsky.app/profile/london-index.bsky.social), a Bluesky bot. Each post is a short set of real figures about London, drawn from the city's own open data and rendered as a card image, in the manner of Harper's Index. A post goes out as a thread: the card, sometimes a map, then a reply carrying a clickable link to every source used.

The account is written by A.I. and says so in its profile. This repository is published for transparency: the code here is exactly what composes and sends the posts. It is the sister of [Seoul Index](https://github.com/stanford-chris/seoul-index), and most of its design was carried over from there.

## Design principle: accuracy over wit

**Python owns every number.** The harvesters fetch the data, format every value and detect the sharp juxtapositions (the widest gap, a genuine near-tie, a ranked list). A `claude -p` step only curates: which lines, in what order, and a neutral opener. It runs with no tools at all and never emits a value; the card reuses Python's exact value string. Where a title has to be exact (a recurring card shape, or a card named after a borough), Python fixes it and the model's wording is ignored.

Every figure is published as its publisher published it. Nothing is estimated or modelled by this account, and a figure whose source could not be read is left out rather than guessed.

## How a post is built

1. **Harvest** (`london_index_harvest.py`). Every vein fetches its source and returns facts: a value string, a label, a source, a period, and optionally a pair tag, a second-line qualifier and a footnote.
2. **Select** (`london_index_select.py`). The pool is narrowed before the model sees it (see *Never the same card twice*), then `claude -p` picks 2 to 4 facts from one vein and writes an opener.
3. **Compose** (`london_index_compose.py`). The card's lines, its second line (the qualifier and the period or the clock), its footnote and its source credit.
4. **Render** (`london_index_card.py`). Headless Chrome draws the card from an HTML template and crops it to content. The same file draws the borough map.
5. **Post** (`london_index_post.py`). The card as an image with full alt text and no caption, a map reply when the card asks for one, then the source link. A failed render falls back to a plain-text post rather than silence.

### Never the same card twice

The bot posts four times a day, and most of its data changes monthly or yearly. Three guards keep that from producing repeats:

- **Spent facts.** A fact already posted with the same label and value leaves the pool, and any pair group with a spent member goes with it. A live vein's values change every run, so it is never spent; a monthly vein's facts are spent for the rest of the month. If nothing fresh is left, the slot is skipped, and the log says so.
- **Cooldowns.** Any vein that led a card within 20 hours is withheld, and two groups of near-static veins are withheld for four days after leading. A cooldown that would leave nothing to post is not applied.
- **The last line.** Before posting, the card's lines are compared with every card in the history, and an identical card is refused whatever the selector did.

A vein that has gone two days without leading is given a card to itself, so nothing starves.

## The cards

The title names what is measured ("Reported crime", "House prices, by borough"). The second line carries the period or the clock, and a qualifier when the figures need one ("July 2026"; "Within a mile of Trafalgar Square, July 2026"; "Departures in the next hour, 13 main stations, 12 September at 8:00 a.m."). Each row is a label, a dotted leader and the value. A footnote, when there is one, says only what is left: the sample or the source. The alt text carries the title, the second line, every row and the footnote.

**Spotlight cards** are about one place, walking through a set in turn, least recently featured first. The spotlight borough gives one borough's reported crime, most common category, change on the month and rank among the 33, and threads a map: every borough in outline, the featured one filled, which is the area counted. The station spotlight gives one main station's own departure board, and the river gauge spotlight one gauge's level against its own typical range.

**Borough crime is counted whole.** data.police.uk publishes street-level reports and takes a polygon; each borough's polygon is its Office for National Statistics boundary, the same outline the map draws. The 33 counts are fetched once a month and cached, since the data changes monthly. Until 12 September 2026 the borough figures were a one-mile sample around each town hall, which understated some boroughs by more than half and ranked the wrong ones.

## Data sources

| Vein | Source | Cadence |
|---|---|---|
| `tfl_bikes` | TfL BikePoint: Santander Cycles available, empty docks | live |
| `station_usage` | TfL Annual Station Counts: Underground entries and exits by station | yearly |
| `daily_footfall` | TfL Network Demand: the newest published day's taps, whole network | daily, about nine days behind |
| `flood` | Environment Agency flood warnings and alerts for London | live |
| `river_levels` | Environment Agency gauges: six London rivers against their own typical range | live |
| `police` | data.police.uk: reported crime within a mile of Trafalgar Square | monthly, about two months behind |
| `police_boroughs` | data.police.uk: all 33 boroughs counted whole, ranked, the movers on the month, where each crime type was highest | monthly |
| `police_spotlight` | data.police.uk: one of the 33 boroughs per card, counted whole, with a map | monthly |
| `stop_search` | data.police.uk: Metropolitan Police stop and search | monthly |
| `cycle_hires` | London Datastore: daily Santander Cycles hires | periodic |
| `laqn` | London Air Quality Network: current readings by borough | live |
| `dcms_museums` | DCMS sponsored museums: annual visitors, the 13 London institutions | yearly |
| `house_prices` | HM Land Registry UK House Price Index: London and all 33 boroughs | monthly, about two months behind |
| `road_works` | TfL Road disruptions on the Transport for London Road Network | live |
| `lfb_animals` | London Datastore: London Fire Brigade animal rescues | monthly |
| `rail_departures` | Rail Data Marketplace Live Departure Board (Rail Delivery Group): trains departing 13 main stations in the next hour, on time, late and cancelled; the stations ranked; late trains by operator | live |
| `rail_station` | the same boards: one station per card, its own departures | live |
| `river_gauge` | Environment Agency: one of the six gauges per card against its own typical range | live |

A daily weather card (`london_weather_post.py`) uses the Met Office Weather DataHub and posts separately.

Borough boundaries on the map are the Office for National Statistics' Local Authority Districts (December 2024), Open Government Licence v3.0, and contain OS data, Crown copyright and database right 2024; the map reply says so. Every publisher is credited with a link in each thread and in the account's pinned thread.

## Files

- `london_index_harvest.py`: the veins, one function each, and the pure builders that turn fetched records into facts.
- `london_index_select.py`: the guards, the vein rotation and the `claude -p` call.
- `london_index_compose.py`: lines, second line, footnote, source credit.
- `london_index_card.py`: the card and map renderers.
- `london_index_post.py`: the poster; `--dry-run` harvests, selects, composes and renders without posting or changing state.
- `london_index_methodology.py`: the pinned "about this account" thread.
- `london_weather_post.py`: the daily forecast card.
- `data/london_boroughs.geojson`: the borough outlines.
- `test_*.py`: the tests, run by file (`python3 test_london_index_harvest.py`).
- `SESSION_SUMMARY.md`: the working record, with the reasoning behind each decision and the dates they were made.

## Setup

Credentials live in the macOS Keychain, never in this repository: the Bluesky app password, a long-lived `claude` token, a TfL subscription key, the Rail Data Marketplace consumer key and the Met Office DataHub key. Each harvester falls back or refuses plainly when its key is missing. Posting is scheduled with launchd, four times a day at 8:00 a.m., 12:30 p.m., 5:30 p.m. and 8:30 p.m. London time.

## Licence

This code is released under the [MIT License](LICENSE). The figures belong to their publishers and are reproduced under their own licences, most of them the Open Government Licence.
