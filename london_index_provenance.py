"""What each London Index vein counts, where from, and how it is checked.

One entry per key of london_index_harvest.HARVESTERS, no more and no fewer
(test_london_index_provenance.py holds the two in step). Written on 7 October
2026, after an audit of the sister bot (Seoul Index) and then of this one
found figures whose labels said more than the data did: 19 of the 32 veins
were held (london_index_select.HELD_VEINS) the same day.

Each entry:
  source           the publisher, dataset and endpoint read
  counts           what one unit of the figure is, said plainly
  checked_against  the independent figure it was measured against, with the
                   numbers and the date, or why there is none
  complete_fetch   how a whole answer is told from a partial one
  labels           whether the card's wording is true of the count
  verified         the day the entry was last checked against live data
  checks           list of {'kind', 'when', 'what'}:
                     kind  RECONCILE (against an independent figure) or
                           SHAPE (what the raw feed must look like)
                     when  'build': runs in the harvester on every build, a
                           failure withholding the vein (SourceCheckFailed);
                           'audit': too costly or too slow-moving for every
                           build, left to the monthly re-audit;
                           'none': no independent figure exists
                     what  one sentence, with the measured figures and the
                           tolerance

The monthly scheduled task `index-source-audit` reads this file: it re-runs
the 'audit' checks, re-measures the 'build' tolerances against live data,
and updates `verified` (or says what has stopped being true). An entry whose
code has changed must be rewritten in the same commit as the code.
"""

PROVENANCE = {
    'tfl_bikes': {
        'source': 'TfL Unified API /BikePoint (api.tfl.gov.uk), every Santander Cycles docking station',
        'counts': 'Docked bikes (NbBikes, standard plus e-bikes) summed over stations; installed docking '
                  'points (NbDocks), which include docks out of use; stations with no docked bike. Bikes '
                  'on hire or in vans are in no field.',
        'checked_against': 'TfL’s separate live cycle-hire XML feed (livecyclehireupdates.xml), 7 October '
                           '2026, three paired fetches: stations 799 = 799 and docks 21,016 = 21,016 every '
                           'time; bikes 8,649 against 8,656 at worst (0.08%), bikes moving between fetches.',
        'complete_fetch': 'One unpaged list, 799 stations, no duplicate ids.',
        'labels': 'True: “Available now”, “Docking stations with no bikes”, “Docking points across the '
                  'scheme” (installed points, about 1,585 of them neither holding a bike nor free).',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'RECONCILE', 'when': 'build',
             'what': 'Station count and dock total equal the live XML exactly (799, 21,016); docked bikes '
                     'within 1% of it (0.08% apart at worst over three fetches).'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'No duplicate station id, and NbBikes equals NbStandardBikes plus NbEBikes at every '
                     'station (all 799 on 7 October 2026).'},
        ],
    },
    'station_usage': {
        'source': 'TfL Annual Station Counts, AC2025_AnnualisedEntryExit_public.xlsx, found by listing the '
                  'crowding.data.tfl.gov.uk S3 bucket; Mode = LU, Coverage = “Station entry/exit” rows',
        'counts': 'Annualised entries plus exits per Underground station, modelled from a typical autumn '
                  'week, not a counted year. Where gates are shared, the LU row also carries other modes’ '
                  'taps: 35 rows of other modes read “---see LU---”.',
        'checked_against': 'TfL Network Demand daily footfall summed over 2025, 197 stations: median ratio '
                           'to the annualised figure 1.027; Paddington 31.8 million LU plus 24.0 million '
                           'Elizabeth line against its LU row’s 58.0 million; Waterloo 62.9 million summed '
                           'against 74.5 million annualised (measured by the audit, 7 October 2026).',
        'complete_fetch': 'One sheet, 269 LU rows, names unique after cleaning; the S3 listing must say '
                          'IsTruncated false.',
        'labels': 'Overstated (held): “Busiest Tube stations” includes Elizabeth line, DLR and Overground '
                  'taps at shared stations, and an annualised estimate reads as a counted total.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'No station a card names has another mode’s row reading “---see LU---”; fails on '
                     '7 October 2026 (Tottenham Court Road on the card), the fault the vein is held for.'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'The S3 listings that find the file are complete (IsTruncated false).'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'Each card station’s year of daily footfall (two 12 MB files) over its annualised '
                     'figure in 0.80 to 1.25, and the median over all stations in 0.95 to 1.10 (1.027 '
                     'measured; Paddington 0.55 and Chorleywood 0.57 the outliers).'},
        ],
    },
    'daily_footfall': {
        'source': 'TfL Network Demand StationFootfall CSV (the newest by LastModified in the S3 bucket, '
                  '“StationFootfall_2025_2026 .csv” on 7 October 2026)',
        'counts': 'EntryTapCount plus ExitTapCount per station for the newest TravelDate, Underground, '
                  'Overground, DLR and Elizabeth line; a station under 10% of its own trailing 7-day '
                  'average is dropped as a data gap. “Quietest” is drawn only from stations at least half '
                  'their usual for that weekday (the median of their last four same weekdays), and the '
                  'pair’s footnote counts any left out.',
        'checked_against': 'The same stations’ annualised 2025 figures in Annual Station Counts: daily sum '
                           'over annual, median 1.027 over 197 stations (audit, 7 October 2026). The day '
                           'itself has no second publisher.',
        'complete_fetch': 'One CSV; no (date, station) pair twice; 433 stations on the newest day '
                          '(3 October 2026) against a trailing median of 433.',
        'labels': 'True since 8 October 2026 (released): “Quietest” can no longer be a part-closed station '
                  '(Roding Valley 124 against about 491 on 26 September 2026, posted 4 October). Same '
                  'weekday, not a 7-day average: 103 ordinary stations read “under half” a 7-day average on '
                  '27 September (a Sunday), 39 under half their own Sundays.',
        'verified': '2026-10-08',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'The newest day has at least 95% of the trailing 7-day median station count (100% '
                     'on 3 October 2026; 96% on 26 September, 73% on a strike day, 11% on Christmas Day).'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'No (date, station) pair repeats.'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'The S3 Network Demand listing is complete (IsTruncated false; 17 keys).'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'Median of a year of daily sums over Annual Station Counts in 0.95 to 1.10 (1.027).'},
        ],
    },
    'flood': {
        'source': 'Environment Agency flood-monitoring API, /id/floods?county=London',
        'counts': 'Flood warnings in force (severityLevel 1 or 2) and alerts (3); level 4, no longer in '
                  'force, is left out. The county match is a substring match, so areas such as “Greater '
                  'London, Surrey” count.',
        'checked_against': 'The unfiltered national /id/floods list, counted client-side for “London” in '
                           'floodArea.county: 0 against 0 on 7 October 2026 (1 item nationally, Norfolk).',
        'complete_fetch': 'One unpaged list.',
        'labels': 'True.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'RECONCILE', 'when': 'build',
             'what': 'The county=London item count equals the national list’s London items exactly '
                     '(0 = 0 on 7 October 2026).'},
        ],
    },
    'river_levels': {
        'source': 'Environment Agency flood-monitoring API, the latest level reading at six curated '
                  'gauges (RIVER_STATIONS) with each gauge’s published typical range (stageScale)',
        'counts': 'Where each gauge’s stage sits within its own typical low and high, as a bare percentage '
                  'under “Position in typical range”; “Fullest” and “Driest” rank the gauges that read in '
                  'the last two hours. The stage in metres (a height on the gauge, not water depth) is not '
                  'shown. Title fixed: “London river gauges”.',
        'checked_against': 'None available: no second publisher of these gauges. The station record’s '
                           'latestReading is the same feed.',
        'complete_fetch': 'Six of six answered on 7 October 2026; Roding at Wanstead read at 10:00 UTC, '
                          '11 hours behind the other five, and is left off and counted in the footnote.',
        'labels': 'True since 8 October 2026 (released): six gauges named as the six this account follows, '
                  'late gauges left off, no metres, the second line the readings’ own time.',
        'verified': '2026-10-08',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'At least four of the six read in the last two hours (five on the night of 7 October '
                     '2026); a late gauge is left off rather than failing the card.'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Every reading used is a stage level in mASD (measure id contains “-level-stage-” and '
                     'ends “-mASD”, all six on 7 October 2026), the unit the typical range is in.'},
            {'kind': 'RECONCILE', 'when': 'none',
             'what': 'No independent figure: the Environment Agency is the only publisher of these gauges.'},
        ],
    },
    'river_gauge': {
        'source': 'As river_levels, one gauge per card, the least recently featured of those that read '
                  'in the last two hours',
        'counts': 'One gauge’s stage now (mASD: a height on the gauge, not water depth, as the footnote '
                  'says), its typical low and high, and where it sits between them.',
        'checked_against': 'None available, as river_levels.',
        'complete_fetch': 'One gauge per card; the six fetched once per run and shared with river_levels.',
        'labels': 'True since 8 October 2026 (released): only a fresh gauge is spotlit, the second line is '
                  'its reading’s time, and the footnote says the metres are gauge heights.',
        'verified': '2026-10-08',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'The card’s gauge read no more than 2 hours ago and in mASD.'},
            {'kind': 'RECONCILE', 'when': 'none',
             'what': 'No independent figure: the Environment Agency is the only publisher of these gauges.'},
        ],
    },
    'police': {
        'source': 'data.police.uk crimes-street/all-crime, a one-mile point search around Trafalgar '
                  'Square (51.5074, −0.1278), the newest populated month (August 2026)',
        'counts': 'Street-level records within a mile, anti-social behaviour included (527 of 4,160 in '
                  'August 2026, 12.7%).',
        'checked_against': 'The same mile as a 48-sided polygon POSTed to the same API: 4,154 against '
                           '4,160 (0.14%), every polygon id among the point search’s, 7 October 2026.',
        'complete_fetch': 'Under the API’s 10,000-record cap; no duplicate id; every record for the '
                          'month asked; farthest record 1,611 m from the centre.',
        'labels': 'Held: “Reported crime” includes anti-social behaviour, which the Met’s own borough '
                  'counts under the same title leave out.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'RECONCILE', 'when': 'build',
             'what': 'Point search within 0.5% of the 48-sided polygon of the same mile (0.14% apart, '
                     'August 2026).'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Fewer than 10,000 records, no duplicate id, every record’s month the month asked.'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'No anti-social behaviour record in a “Reported crime” total; fails on 7 October 2026 '
                     '(527), the fault the vein is held for.'},
        ],
    },
    'police_boroughs': {
        'source': 'Metropolitan Police Monthly Crime Dashboard CSV on the London Datastore (dataset '
                  'e5n6w, 136 MB, refresh 2 September 2026), Area Type “Borough”, Measure “Offences”; '
                  'data.police.uk polygon counts only if the dashboard cannot be read',
        'counts': 'Total notifiable offences per borough per month, anti-social behaviour excluded; the '
                  '32 boroughs the Met polices (the City of London has its own force).',
        'checked_against': 'data.police.uk whole-borough polygon counts less anti-social behaviour, over '
                           'the Met’s figure: 0.919 to 0.969, median 0.939, across 32 boroughs for June and '
                           'July 2026 (audit, 7 October 2026). Within the file, Borough rows equal Safer '
                           'Neighbourhood Teams rows exactly every month, July 2024 to August 2026 (78,647 '
                           '= 78,647 for August).',
        'complete_fetch': 'The whole file, every month; 32 of 32 boroughs; no repeated (borough, group, '
                          'subgroup, month) row.',
        'labels': 'True.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'RECONCILE', 'when': 'build',
             'what': 'The month’s Borough rows, all of them, sum exactly to its Safer Neighbourhood '
                     'Teams rows (totals kept by mps_parse; 78,647 = 78,647 for August 2026).'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'All 32 Met boroughs present for the month.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'Per borough, data.police.uk polygon count less anti-social behaviour over the Met '
                     'figure in 0.88 to 1.00 (0.919 to 0.969 measured); 33 polygon fetches a month.'},
        ],
    },
    'police_spotlight': {
        'source': 'As police_boroughs, one borough per card, the least recently featured',
        'counts': 'One borough’s total notifiable offences, its largest offence group, change on the '
                  'month, and rank among the 32.',
        'checked_against': 'As police_boroughs.',
        'complete_fetch': 'As police_boroughs.',
        'labels': 'True: “of 32”, since the City of London Police is a separate force.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'RECONCILE', 'when': 'build',
             'what': 'As police_boroughs: Borough rows equal Safer Neighbourhood Teams rows exactly.'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'All 32 Met boroughs present, so the rank is of 32.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'As police_boroughs: data.police.uk polygon ratio in 0.88 to 1.00.'},
        ],
    },
    'cycle_hires': {
        'source': 'London Datastore, TfL daily cycle hires (tfl-daily-cycle-hires.xlsx), sheet Data',
        'counts': 'Santander Cycles hires on the newest day (31 August 2026, 19,426), and the mean of '
                  'this year’s daily figures (25,843).',
        'checked_against': 'The same sheet’s monthly, annual and grand-total columns, which TfL fills '
                           'separately: every month (194) and year equal to the daily sums, grand total '
                           '154,053,134 equal, 7 October 2026. Same workbook, so not an independent '
                           'publisher.',
        'complete_fetch': '5,877 days, July 2010 to August 2026, no date twice, no gap.',
        'labels': 'True.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'RECONCILE', 'when': 'build',
             'what': 'Daily figures sum exactly to the monthly column for every month, to the annual '
                     'column for the newest year, and to the daily grand total.'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'No date twice and no gap between consecutive dates.'},
        ],
    },
    'laqn': {
        'source': 'London Air Quality Network (Imperial College), hourly index, '
                  'api.erg.ic.ac.uk/AirQuality/Hourly/MonitoringIndex/GroupName=London/Json',
        'counts': 'By SITE: sites whose highest reading this hour is above “Low”, out of sites reporting a '
                  'reading (a species reading “No data” is not one); boroughs with a site reporting, out of '
                  'the 33 the feed lists; the highest reading, named only when one site holds it. The second '
                  'line is the bulletin hour in London time (BulletinDate is GMT).',
        'checked_against': 'The network’s own site list (MonitoringSites/GroupName=London): 73 open sites '
                           'against 72 in the index, 7 October 2026. BulletinDate’s zone from the raw data’s '
                           '@MeasurementDateGMT (newest 20:00 at 21:34 UTC, as the bulletin).',
        'complete_fetch': 'One document; 72 sites, none twice; one bulletin hour across all.',
        'labels': 'True since 8 October 2026 (released). Until then “Boroughs with a monitor” was 33 with '
                  '14 reporting, “Readings above ‘Low’” hid 105 of 194 “No data” readings, and “Worst '
                  'reading” took one of 15 tied.',
        'verified': '2026-10-08',
        'checks': [
            {'kind': 'RECONCILE', 'when': 'build',
             'what': 'Sites in the index within 3% of open sites in the site list (72 against 73, 1.4%).'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Exactly 33 local authorities listed (the card’s “of 33”), one bulletin hour across '
                     'sites, no site twice.'},
        ],
    },
    'dcms_museums': {
        'source': 'DCMS sponsored museums and galleries annual performance indicators 2024/25, ODS Table 1, '
                  'the 13 rows in LONDON_DCMS_MUSEUMS',
        'counts': 'Annual visits per museum group, every site, financial year: Science Museum Group '
                  'includes York, Manchester, Bradford and Shildon; Imperial War Museums includes Duxford '
                  'and IWM North; Tate includes St Ives and Liverpool; the Natural History Museum includes '
                  'Tring. Royal Armouries (the White Tower among its sites) is left out.',
        'checked_against': 'DCMS’s own Total row less National Museums Liverpool, Royal Armouries and the '
                           'National Coal Mining Museum: 37,338,500 against 37,338,276 (Total rounded to the '
                           'thousand); ALVA’s 2025 site table puts about 2.5 million of the 37.3 million '
                           'outside London (audit, 7 October 2026).',
        'complete_fetch': 'One table; 18 museum rows and a Total; all 13 London rows published for 2024/25.',
        'labels': 'Held: “All London DCMS museums” includes about 2.5 million visits outside London. '
                  '“Most visited” and “Fewest” are unaffected.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'RECONCILE', 'when': 'build',
             'what': 'The newest year’s museum rows sum to the Total row within 500 (DCMS rounds the '
                     'Total to the thousand; 224 for 2024/25, 490 at most over twelve years).'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Table 1’s rows are exactly the 18 known museums and the Total, so a new, renamed '
                     'or merged row fails. Passes on 7 October 2026: no figure in this table can show '
                     'the non-London sites the vein is held for.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'Each group’s London sites against ALVA’s annual site table (calendar year, so '
                     'approximate): Science Museum 2.64 million of the group’s 4.0 million.'},
        ],
    },
    'stop_search': {
        'source': 'data.police.uk /api/stops-force?force=metropolitan, the newest month with at least '
                  '1,000 records (July 2026)',
        'counts': 'Searches of people by the Met (not the City of London Police or British Transport '
                  'Police), with and without a location; vehicle-only searches are absent.',
        'checked_against': 'stops-no-location for the same force and month: 39 against the 39 records '
                           'without a location among 12,088, July 2026. No independent annual figure '
                           'fetched (the Home Office’s by-force table is the candidate).',
        'complete_fetch': 'One answer; the month must be listed for the Met in crimes-street-dates (August '
                          'and March 2026 are not, so the vein falls back to July).',
        'labels': 'Held: “For weapons” counts “Offensive weapons” only and leaves out 39 firearms and 17 '
                  'section 60 searches (July 2026).',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Records without a location equal the stops-no-location list exactly (39 = 39), and '
                     'crimes-street-dates lists the Met as published for the month.'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'No firearms or section 60 search outside “For weapons”; fails on 7 October 2026 '
                     '(56), the fault the vein is held for.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'An April-to-March sum against the Home Office’s stop and search by force table; '
                     'not yet measured.'},
        ],
    },
    'house_prices': {
        'source': 'HM Land Registry UK House Price Index, region/month JSON, London and the 33 local '
                  'authorities',
        'counts': 'Index-derived average price, all property types; change on the year and the month; '
                  'recent months provisional.',
        'checked_against': 'Borough sales volumes sum exactly to London’s (4,006 = 4,006, May 2026, the '
                           'newest month with volumes); the volume-weighted geometric mean of borough '
                           'averages is £544,826 against London’s £547,982 (−0.58%) (audit, 7 October 2026).',
        'complete_fetch': '33 of 33 boroughs answered for July 2026; the borough shapes need 30.',
        'labels': 'True. The City of London has 4 to 8 sales a month, so its changes are thin.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Every record’s refMonth is the month asked and its refRegion the slug asked (all 34 '
                     'on 7 October 2026), so a slug resolving to another region fails.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'Borough sales volumes sum exactly to London’s, and the volume-weighted geometric '
                     'mean of borough prices within 1.5% of London’s (−0.58%), for the newest month with '
                     'volumes, two months behind: 34 more requests.'},
        ],
    },
    'house_price_spotlight': {
        'source': 'As house_prices, one borough per card, the least recently featured',
        'counts': 'One borough’s average price, its changes, and its rank among those answering.',
        'checked_against': 'As house_prices.',
        'complete_fetch': 'As house_prices; no rank line under 30 answering.',
        'labels': 'True (the rank includes the thin-sample City).',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Every borough record is the month and region asked, as house_prices.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'As house_prices: sales volumes and the weighted mean against London.'},
        ],
    },
    'road_works': {
        'source': 'TfL Unified API /Road/all/Disruption',
        'counts': 'TfL’s current listed disruptions, on its own corridors and on borough roads alike '
                  '(55 of 115 on no TfL corridor, 7 October 2026); “Roadworks” is category Works, which '
                  'includes emergency works.',
        'checked_against': 'None available: no independent count of London street works. TfL’s /Road '
                           'corridor list (24) is used for the shape checks.',
        'complete_fetch': 'One unpaged list, 115 unique ids.',
        'labels': 'Relabelled and released 8 October 2026 (his call): second line “TfL’s list '
                  'of current disruptions”, footnote “on its red routes and on borough roads; not every '
                  'roadwork in London”, and “Roadworks” for what was “Planned roadworks”.',
        'verified': '2026-10-08',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'No duplicate id, and every corridor id named is one /Road lists.'},
            {'kind': 'RECONCILE', 'when': 'none',
             'what': 'No independent count of London disruptions or street works exists to compare with.'},
        ],
    },
    'lfb_animals': {
        'source': 'London Datastore, LFB animal rescue incidents workbook (since January 2009), the newest '
                  'complete month',
        'counts': 'Incidents (callouts), not animals and not all rescues: one incident can be several '
                  'animals, and many are assistance.',
        'checked_against': 'The LFB master incident file (em8xy), SpecialServiceType “Animal assistance '
                           'incidents”: 213 = 213 for July 2026, 167 = 167 for June (audit, 7 October 2026).',
        'complete_fetch': 'One sheet; 213 incidents for July 2026, none twice, last call 31 July.',
        'labels': 'Held: “Animals rescued” counts callouts; two rows read “cat” and are dropped from Cats '
                  '(114 shown of 116); three costs read “NULL” and are left out of the notional cost.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Every animal group is one the ranking names or an “Unknown” group, every incident '
                     'has a numeric cost, and no incident repeats; fails on 7 October 2026 (“cat”, and '
                     'three “NULL” costs), faults the vein is held for.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'The month’s incident count equals the master file’s animal assistance count exactly '
                     '(213 = 213); the master file is 81 MB.'},
        ],
    },
    'rail_departures': {
        'source': 'Rail Data Marketplace Live Departure Board (LDBWS GetDepartureBoard), 13 London '
                  'termini, 60-minute window, numRows 150',
        'counts': 'Board entries summed across the 13 boards, labelled “Departures on the boards”: a train '
                  'starting at one terminus and calling at another counts on both, and the footnote says '
                  'so; Elizabeth line trains included and named.',
        'checked_against': 'None available: rsid is empty on most services (201 of 236 on 6 October), so '
                           'distinct trains cannot be counted exactly. Measured 7 October 2026, 13:30 BST: '
                           '35 services on one board started at another of the 13.',
        'complete_fetch': 'Thirteen boards, each under numRows (81 at most).',
        'labels': 'Relabelled and released 8 October 2026 (his call): title “London’s '
                  'departure boards” on both rail cards, the total “Departures on the boards”, the footnote naming National '
                  'Rail and the Elizabeth line and the double count.',
        'verified': '2026-10-08',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'No board reached numRows (150), so none was cut off (81 at most).'},
            {'kind': 'RECONCILE', 'when': 'none',
             'what': 'No independent count of departures from London’s termini exists.'},
        ],
    },
    'rail_station': {
        'source': 'As rail_departures, one board per card, the least recently featured',
        'counts': 'Departures on that station’s own board in the next hour, through trains included, as '
                  'the board shows them.',
        'checked_against': 'None available: the live board is the only source.',
        'complete_fetch': 'The card’s board under numRows (150).',
        'labels': 'True: one board, labelled as that station.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'The card’s board has fewer than 150 services, so it was not cut off (81 at most '
                     'across the 13 on 7 October 2026).'},
            {'kind': 'RECONCILE', 'when': 'none',
             'what': 'No independent figure for a single live departure board.'},
        ],
    },
    'reservoirs': {
        'source': 'London Datastore, london_reservoir_levels.csv (Thames Water), daily since 1989',
        'counts': 'Percent of usable capacity in Thames Water’s Lower Thames and Lower Lee groups only; '
                  'other companies supplying parts of London are not counted.',
        'checked_against': 'None available: Thames Water publishes no other machine-readable series; the '
                           'Environment Agency’s monthly water situation report (PDF) is a manual option.',
        'complete_fetch': '13,757 rows to 31 August 2026; 122 rows (1 June 2020 to 30 September 2021) are '
                          'dd/mm/yyyy and do not parse; 15 levels read “n/a” or “---”.',
        'labels': 'Held: the dropped rows move the all-years average for 31 August (80.05 to 80.21); the '
                  'title “London’s reservoirs” covers two Thames Water groups (the footnote names them).',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Every data row’s date reads as dd-Mon-yy and no date repeats; fails on 7 October '
                     '2026 (122 rows), the fault the vein is held for.'},
            {'kind': 'RECONCILE', 'when': 'none',
             'what': 'No independent machine-readable figure; the Environment Agency’s monthly PDF is the '
                     'only other publisher.'},
        ],
    },
    'tfl_journeys': {
        'source': 'London Datastore, tfl-journeys-type.csv, journeys by mode per TfL reporting period',
        'counts': 'Journey stages by mode, in millions, per reporting period (13 a year, 25 to 32 days): '
                  '“All modes” sums the modes, so a bus-and-Tube trip counts twice.',
        'checked_against': 'None available: TfL publishes this series only here. Internally, 213 periods, '
                           'each beginning the day after the last ended, 7 October 2026.',
        'complete_fetch': 'One CSV; no period twice, no break between periods.',
        'labels': 'True for the newest period (P5, 26 July to 22 August 2026, 28 days, against P5 of '
                  '2025/26, 28 days). “Four weeks” is false for periods 1 and 13, which the checks withhold.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Periods contiguous and unique; the newest is 28 days (“Four weeks”); the year-earlier '
                     'period has the same period number and length (P5, 28 against 28).'},
            {'kind': 'RECONCILE', 'when': 'none',
             'what': 'No independent figure: TfL publishes journeys by mode by period only in this file.'},
        ],
    },
    'congestion_charge': {
        'source': 'London Datastore (dataset 2r88d), tfl-vehicles-c-charge-zone.csv, monthly since July 2010',
        'counts': 'The month’s sum of DAILY unique confirmed vehicles in charging hours: vehicle-days, so a '
                  'car seen on 20 days counts 20 times. “Per charging day” is distinct vehicles a day.',
        'checked_against': 'None available: no independent count of vehicles in the zone. Internally, '
                           'confirmed vehicles are at most the camera captures in 116 of 117 months; May '
                           '2026 (2,784,653 confirmed against 2,564,414 captures) is not.',
        'complete_fetch': 'One CSV, 193 lines, July 2010 to July 2026.',
        'labels': 'Held: “Vehicles seen in charging hours” counts vehicle-days. The page link '
                  '(CCZ_PAGE) answers 404; the dataset is at /dataset/2r88d.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'For the months the card reads (the newest and a year before), confirmed vehicles are '
                     'no more than camera captures and charging days no more than the month’s days; passes '
                     'for July 2026 and July 2025, would fail for May 2026. No figure here shows the '
                     'vehicle-days fault the vein is held for.'},
            {'kind': 'RECONCILE', 'when': 'none',
             'what': 'No independent count of vehicles in the Congestion Charge zone is published.'},
        ],
    },
    'police_strength': {
        'source': 'London Datastore, Police_Force_Strength.csv (MOPAC), monthly',
        'counts': 'Met full-time equivalents: officers, police staff, PCSOs.',
        'checked_against': 'Home Office Police Workforce tables (published 22 July 2026), Met, FTE: officers '
                           '31,495 against 31,181 (−1.0%), staff 11,854 against 11,558 (−2.5%), PCSOs 1,398 '
                           'against 1,389 (−0.6%) on 31 March 2026; the same pattern on 31 March and 30 '
                           'September 2025 (audit, 7 October 2026).',
        'complete_fetch': '159 months, May 2013 to July 2026, none missing.',
        'labels': 'True.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'One row a month and no month missing (159, May 2013 to July 2026), since the '
                     'year-on-year line reads the row twelve back.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'Each March and September row against the Home Office workforce tables: officers and '
                     'PCSOs within 2% (0.6% to 1.0% measured), staff within 4% (2.1% to 2.5%); the tables '
                     'are published twice a year.'},
        ],
    },
    'arrests': {
        'source': 'London Datastore (dataset 2r7po), MPS custody arrests workbook, sheet Arrests, a URL '
                  'naming “2022 01 to 2026 08”',
        'counts': 'Custody records created in Met custody suites, by first arrest offence: not people, '
                  'and including other agencies’ detainees (449 Immigration records in August 2026).',
        'checked_against': 'Home Office persons arrested for notifiable offences, Met: 108,993 against the '
                           'file’s 140,747 for 2025/26 (×1.291), 104,430 against 128,598 for 2024/25 '
                           '(×1.231); the scopes differ, so not a tight reconcile (audit, 7 October 2026).',
        'complete_fetch': '17,941 rows, January 2022 to August 2026, every month present, no repeated '
                          'dimensions.',
        'labels': 'Held: “Most common offence: Assault” (2,068) is outnumbered by “Other Offence” (4,979); '
                  '“Arrests by the Metropolitan Police” counts custody records. The page link '
                  '(ARRESTS_PAGE) answers 404; the dataset is at /dataset/2r7po.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Every month from January 2022 present and no row repeating its dimensions.'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'The named offence the card calls most common outnumbers “Other Offence”; fails on '
                     '7 October 2026 (2,068 against 4,979), the fault the vein is held for.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'The financial year’s total over the Home Office’s persons arrested for the Met '
                     '(×1.231 then ×1.291); watched for a jump, not held to a tolerance.'},
        ],
    },
    'unemployment': {
        'source': 'London Datastore (dataset e5mnw), unemployment-region.xlsx, sheet “Long-term trend” '
                  '(ONS Labour Force Survey via the GLA)',
        'counts': 'ILO unemployment, people 16 and over, seasonally adjusted, rolling quarter: London and '
                  'UK rates, Londoners unemployed.',
        'checked_against': 'ONS series YCNI (London rate) and MGSX (UK rate), the quarter the ONS labels '
                           'by its middle month: May to July 2026, London 6.80 against 6.8, UK 4.90 against '
                           '4.9; over the 24 quarters to then, 5.4% and 2.7% apart at most (the GLA keeps '
                           'first estimates, the ONS revises), 7 October 2026.',
        'complete_fetch': 'March to May 1992 to May to July 2026.',
        'labels': 'True (survey estimates, as the footnote says).',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'RECONCILE', 'when': 'build',
             'what': 'The newest quarter’s London rate within 6% of the ONS’s YCNI and its UK rate within '
                     '3% of MGSX for the same quarter (0.05% and 0.1% apart on 7 October 2026).'},
        ],
    },
    'lift_releases': {
        'source': 'London Datastore (dataset 2g980), LFB shut-in-lift releases, last 36 months',
        'counts': 'Lift entrapments the London Fire Brigade attended: incidents, not people, and not those '
                  'freed by lift engineers alone.',
        'checked_against': 'The LFB master incident file (em8xy), SpecialServiceType “Lift Release”: 827 '
                           'against 816 for July 2026 (the lift file a strict subset, −1.3%); 0 to −4 a month '
                           'January 2024 to June 2026 (audit, 7 October 2026).',
        'complete_fetch': '20,615 incidents, August 2023 to July 2026, none twice; last call 31 July.',
        'labels': 'Held: the title “People stuck in lifts” overstates (incidents, LFB only); the rows '
                  '“Callouts” and “Freed by the London Fire Brigade” are true. The page link (LIFTS_PAGE) '
                  'answers 404; the dataset is at /dataset/2g980.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'No incident twice, no month missing, and the newest month’s last call on its last '
                     'day (31 July 2026, 23:44). Passes: no figure here shows the title fault the vein is '
                     'held for.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'The month’s count against the master file’s “Lift Release” count: no more than it '
                     'and within 2% (1.3% measured); the master file is 81 MB.'},
        ],
    },
    'lfb_incidents': {
        'source': 'London Datastore (dataset em8xy), “LFB Incident data from 2024 onwards.xlsx” (81 MB), '
                  'aggregated by month into data/lfb_incidents.json',
        'counts': 'Every incident the brigade was mobilized to, by call date: fires, false alarms, special '
                  'services; mean first-engine attendance where recorded; notional cost.',
        'checked_against': 'Home Office FIRE0102, Greater London quarterly totals, 2024/25 Q1 to 2025/26 '
                           'Q4: the LFB file over the Home Office 1.0030 to 1.0076 (33,561 against 33,308 '
                           'for 2025/26 Q4) (audit, 7 October 2026).',
        'complete_fetch': '358,338 rows, January 2024 to July 2026, no duplicate id; incidents in no named '
                          'group 0.2% of a month at most.',
        'labels': 'True.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Incidents in none of Fire, False Alarm and Special Service at most 0.5% of the month '
                     '(6 of 14,307 in July 2026; 0.2% at most since January 2024), so a renamed group fails.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'Each complete quarter against the Home Office’s FIRE0102 Greater London total, ratio '
                     '1.000 to 1.015 (1.0030 to 1.0076 measured).'},
        ],
    },
    'events': {
        'source': 'Ticketmaster Discovery API, city=London, countryCode=GB',
        'counts': 'Ticketmaster’s own listings (each performance or timed entry) starting in the next '
                  '24 hours, 7 days and 30 days, by segment; venues and busiest day from Arts & Theatre and '
                  'Music listings.',
        'checked_against': 'None available: no London-wide listings count exists. Internally, 1,270 '
                           'listings pulled, 1,270 unique, total 1,270, every segment’s listings equal to '
                           'its total, 7 October 2026.',
        'complete_fetch': 'Per-segment paging, 627 at most against the API’s 1,000-item cap.',
        'labels': 'Held: “On sale in London” and “All events” read as citywide for one seller’s catalogue.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'Every page pulled; listings equal the seven-day total exactly with no id twice; each '
                     'segment’s listings equal its total; 24 hours ≤ 7 days ≤ 30 days. Passes: no figure '
                     'here shows the single-seller scope the vein is held for.'},
            {'kind': 'RECONCILE', 'when': 'none',
             'what': 'No independent count of what is on in London exists.'},
        ],
    },
    'museum_spotlight': {
        'source': 'As dcms_museums, Tables 1, 3, 4, 5, 6 and 10, one museum per card',
        'counts': 'One museum group’s visits, all sites (non-London sites included for Science Museum '
                  'Group, Imperial War Museums, Tate and the Natural History Museum), and its other '
                  'indicators for the same year.',
        'checked_against': 'ALVA 2025: Science Museum 2,640,417 against the group’s 4,002,918; IWM London, '
                           'Churchill War Rooms and HMS Belfast 1,496,411 against IWM’s 2,239,070 (financial '
                           'against calendar year, approximate; audit, 7 October 2026).',
        'complete_fetch': 'As dcms_museums.',
        'labels': 'Held: a group card includes sites outside London and the footnote does not say so; '
                  'IWM’s website visits break in series (Note 29).',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'RECONCILE', 'when': 'build',
             'what': 'As dcms_museums: Table 1’s rows sum to its Total within 500.'},
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'As dcms_museums: Table 1’s rows are exactly the 18 known and the Total.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'Each group’s London sites against ALVA’s annual site table.'},
        ],
    },
    'west_end': {
        'source': 'Society of London Theatre and UK Theatre, “Theatre in the UK 2026” (2025 figures), '
                  'transcribed into WEST_END_REPORTS',
        'counts': 'West End (SOLT member venues) attendances, box office, change in performances, '
                  'occupancy, and the share of tickets over £250 (from a majority subset of venues).',
        'checked_against': 'The report itself: all seven values verbatim in its text (pinned in '
                           'test_london_index_harvest.WestEnd). No other publisher of West End totals.',
        'complete_fetch': 'Transcribed; the report for the next year (theatre-in-the-uk-2027) answers 404.',
        'labels': 'True.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'No newer report exists at uktheatre.org/theatre-in-the-uk-<year + 2>/ (404 on '
                     '7 October 2026), so the transcribed year is still the latest.'},
            {'kind': 'RECONCILE', 'when': 'none',
             'what': 'No independent figure: SOLT and UK Theatre are the only publishers of West End totals.'},
        ],
    },
    'london_cinema': {
        'source': 'BFI Statistical Yearbook 2024, exhibition tables, Table 1 (2023 data), cached weekly in '
                  'data/bfi_exhibition.json',
        'counts': 'ITV’s London television region (13.6 million people): screens, sites, admissions, '
                  'average price, admissions per head, share of UK screens.',
        'checked_against': 'The same file’s Table 2, Greater London as the ONS draws it (8.9 million): '
                           '749 screens against 1,031, 144 sites against 199, 15.8% against 21.7% (audit, '
                           '7 October 2026). Admissions are published only by television region.',
        'complete_fetch': 'One sheet; its 14 regions sum to its total (4,749 screens, 993 sites).',
        'labels': 'Held: “London’s cinemas”, “Screens” and “Cinemas” are the television region, 38% more '
                  'screens than Greater London.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'The row read covers Greater London (8 to 10 million people); fails on 7 October 2026 '
                     '(13.6 million), the fault the vein is held for.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'Table 1’s total screens and sites equal Table 2’s exactly (4,749 and 993); needs the '
                     'exhibition file, read weekly.'},
        ],
    },
    'west_end_shows': {
        'source': 'SOLT, solt.co.uk/data-and-research, “longest-running productions in West End history”, '
                  'supplied January 2025',
        'counts': 'Performances to January 2025 for 20 productions; “Over” is a floor for a show still '
                  'running.',
        'checked_against': 'Wikipedia’s list (revised 23 September 2026): 11 of 12 closed shows identical '
                           '(Thriller Live 4,613 against 4,657); “The Book of Mormon” (4,345 or more) and '
                           '“The Play That Goes Wrong” (4,001 or more) likely in the 20 now (audit, '
                           '7 October 2026).',
        'complete_fetch': '20 rows, counts falling rank by rank, the “supplied in” date found.',
        'labels': 'Held: membership and rank are 21 months old, so “Newest of the West End’s longest runs” '
                  'is likely wrong today; the footnote covers the counts, not the list.',
        'verified': '2026-10-07',
        'checks': [
            {'kind': 'SHAPE', 'when': 'build',
             'what': 'The list was supplied within 12 months; fails on 7 October 2026 (January 2025, '
                     '21 months), the fault the vein is held for.'},
            {'kind': 'RECONCILE', 'when': 'audit',
             'what': 'Closed shows’ counts equal Wikipedia’s list exactly, Thriller Live excepted with both '
                     'numbers (11 of 12 identical).'},
        ],
    },
}
