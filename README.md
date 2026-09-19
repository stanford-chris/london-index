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

The title names what is measured ("Reported crime", "House prices, by borough"). The second line carries the period or the clock, and a qualifier when the figures need one ("July 2026"; "Within a mile of Trafalgar Square, July 2026"; "Departures in the next hour, 13 main stations, 12 September at 8:00 a.m."). Each row is a label, a dotted leader and the value. A footnote says what is left, the sample or the source, and on every card with a period ends by naming it as the newest published ("August 2026 is the latest month for which data is available"), since the figures run some way behind the calendar. The alt text carries the title, the second line, every row and the footnote.

**Spotlight cards** are about one place, walking through a set in turn, least recently featured first. The spotlight borough gives one borough's reported crime, most common category, change on the month and rank among the 33, and threads a map: every borough in outline, the featured one filled, which is the area counted. The station spotlight gives one main station's own departure board, and the river gauge spotlight one gauge's level against its own typical range.

**Borough crime is the Met's own count.** The borough cards read the Metropolitan Police's Monthly Crime Dashboard data from the London Datastore: total notifiable offences by borough and offence group for the 32 boroughs the Met polices (the City of London has its own force), refreshed in the first week of the following month. The 136 MB file is downloaded only when a new month is due and its ETag has changed, and the borough totals are cached. If the dashboard cannot be read, the cards fall back to data.police.uk's street-level reports counted inside each borough's Office for National Statistics boundary, the outline the map draws. Until 12 September 2026 the borough figures were a one-mile sample around each town hall, which understated some boroughs by more than half and ranked the wrong ones.

## Data sources

| Vein | Source | Cadence |
|---|---|---|
| `tfl_bikes` | TfL BikePoint: Santander Cycles available, empty docks | live |
| `station_usage` | TfL Annual Station Counts: Underground entries and exits by station | yearly |
| `daily_footfall` | TfL Network Demand: the newest published day's taps, whole network | daily, about nine days behind |
| `flood` | Environment Agency flood warnings and alerts for London | live |
| `river_levels` | Environment Agency gauges: six London rivers against their own typical range | live |
| `police` | data.police.uk: reported crime within a mile of Trafalgar Square | monthly, about two months behind |
| `police_boroughs` | Metropolitan Police crime dashboard via the London Datastore: the 32 Met boroughs ranked, the movers on the month, where each offence group was highest | monthly, first week of the next month |
| `police_spotlight` | the same dashboard: one borough per card, with a map | monthly |
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
| `reservoirs` | London Datastore: Thames Water reservoir levels, percent of usable capacity, against a year earlier and the average for the date since 1989 | daily |
| `tfl_journeys` | London Datastore: TfL journeys by mode per four-week period, with the year-on-year change | every four weeks |
| `congestion_charge` | London Datastore: vehicles seen in the Congestion Charge zone in charging hours; threads a map of the zone | monthly |
| `police_strength` | London Datastore: Metropolitan Police officers, staff and PCSOs, full-time equivalent | monthly |
| `arrests` | London Datastore: Met arrests, most common named offence, domestic-abuse flagged | monthly |
| `unemployment` | London Datastore: ONS unemployment rate, London against the UK, rolling quarter | quarterly |
| `lift_releases` | London Datastore: people freed from lifts by the fire brigade, by month and borough | monthly |
| `lfb_incidents` | London Datastore: every London Fire Brigade incident, by month: fires, false alarms, special services, first engine's time to arrive, notional cost | monthly, cached from the 81 MB file |
| `events` | Ticketmaster Discovery API: what is on sale in London for the next seven days, by segment, the busiest day and the venues with most on sale, and the next 24 hours and 30 days | live |
| `museum_spotlight` | the DCMS release: one of the 13 London museums per card, its visitors, change, ten years earlier, overseas and under-16 visitors, website visits, recommendation rate and admissions income | yearly |
| `west_end` | Society of London Theatre and UK Theatre, "Theatre in the UK" annual report: West End attendances, box office, change on the year, performances, occupancy, tickets over £250 | yearly, each March |
| `london_cinema` | BFI Statistical Yearbook, exhibition tables: London's cinema admissions, admissions per head, average ticket price, screens, cinemas, share of UK screens | yearly, about two years behind |

A daily weather card (`london_weather_post.py`) uses the Met Office Weather DataHub and posts separately. A second, `london_wxday_post.py`, posts yesterday's *observed* readings: High/Low from the same DataHub's Land Observations API (a separate subscription and key from the forecast card's own, which carries no rain, sunshine or snow field at all), plus a Rain line — shown only when it actually rained — from a second, different UK government source, the Environment Agency's real-time flood-monitoring API (real tipping-bucket gauges, no key needed). No Conditions, Humidity, Wind, Sunshine or Snow row, his call.

The events figures are Ticketmaster's own listings for London from its Discovery API, counted by segment with the API's exact segment filter. A listing is one performance or timed entry, so a West End theatre contributes eight a week and an attraction its timed slots; the card's footnote says so. Only counts are published, never listing content, and the key stays in the Keychain.

**Ticket sales are two annual cards.** The Society of London Theatre's weekly box office data is members-only, and West End weekly grosses are published nowhere, so the West End card reads the annual "Theatre in the UK" report SOLT publishes with UK Theatre each March, which licenses quotation with a credit. Its figures are transcribed into `WEST_END_REPORTS`, not parsed: the report is prose, and a test pins every value against the sentences read out of the PDF. The card posts once per report; the harvester probes for the next year's report and refuses to post the old year once one exists, so a report waiting to be transcribed is a loud failure rather than a quiet one. The cinema card reads the London row of the BFI Statistical Yearbook's exhibition tables, found on the yearbook page by its filename and cached for a week. That "London" is ITV's London television region, 13.6 million people, wider than Greater London, and the footnote says so; the newest edition listed describes 2023, so the card's "latest year" sentence names a year two behind, which is the truth. The BFI's weekly box office file is UK-wide with no regional split and is deliberately not used.

Borough boundaries on the map are the Office for National Statistics' Local Authority Districts (December 2024), Open Government Licence v3.0, and contain OS data, Crown copyright and database right 2024; the map reply says so. The Congestion Charge zone boundary is TfL's, from the London Datastore's central ULEZ dataset (the same area), Open Government Licence, reprojected once from British National Grid and stored under `data/`. Every publisher is credited with a link in each thread and in the account's pinned thread.

## Files

- `london_index_harvest.py`: the veins, one function each, and the pure builders that turn fetched records into facts.
- `london_index_select.py`: the guards, the vein rotation and the `claude -p` call.
- `london_index_compose.py`: lines, second line, footnote, source credit.
- `london_index_card.py`: the card and map renderers.
- `london_index_post.py`: the poster; `--dry-run` harvests, selects, composes and renders without posting or changing state.
- `london_index_methodology.py`: the pinned "about this account" thread.
- `london_weather_post.py`: the daily forecast card.
- `london_wxday_post.py`: yesterday's observed weather (Met Office Land Observations for High/Low, Environment Agency for Rain), not a forecast.
- `data/london_boroughs.geojson`: the borough outlines.
- `test_*.py`: the tests, run by file (`python3 test_london_index_harvest.py`).
- `SESSION_SUMMARY.md`: the working record, with the reasoning behind each decision and the dates they were made.

## Setup

Credentials live in the macOS Keychain, never in this repository: the Bluesky app password, a long-lived `claude` token, a TfL subscription key, the Rail Data Marketplace consumer key, the Ticketmaster Discovery API key and the Met Office DataHub key. Each harvester falls back or refuses plainly when its key is missing. Posting is scheduled with launchd, four times a day at 8:00 a.m., 12:30 p.m., 5:30 p.m. and 8:30 p.m. London time.

## Licence

This code is released under the [MIT License](LICENSE). The figures belong to their publishers and are reproduced under their own licences, most of them the Open Government Licence.
