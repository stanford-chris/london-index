"""Tests for london_wxday_post.py, yesterday's observed weather card.

Same shape as test_london_weather_post.py, but the failures worth fearing
are different ones. Two data sources, two different failure shapes:

- The Met Office Land Observations API's nearest-station result can 404
  (see the module docstring), so first_working_station() is tested against
  exactly that shape of response rather than assumed to always succeed on
  the first candidate.
- The Environment Agency's rain gauges can be silently offline, which
  looks identical to a network blip at the HTTP layer — ea_daily_total_mm()
  is tested for the distinction that actually matters: 'measured, totalled
  zero' (a genuinely dry day, saw_any=True) against 'nothing came back at
  all' (saw_any=False), since only the caller can tell those apart and a
  card that prints '0.0mm' for the second case would be lying.

The timezone-boundary filter is tested twice, once per source, against
real UTC/BST-crossing timestamps — a UTC-day filter would silently drop an
hour off each end of the London day for either one. build_card_lines() is
tested for what it must show ONLY when rain_mm is a real positive number
(never for a confirmed-dry 0.0, never guessed at when no gauge answered)
and for what it must NEVER show — Sunshine or Snow, since those fields
don't exist in either source.

No network, no Chrome, no posting: nothing here calls _curl_json,
render_card or atproto.
"""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.argv = ['test']
sys.path.insert(0, str(Path(__file__).resolve().parent))
import london_wxday_post as X


class DecodeGeohash(unittest.TestCase):
    """Pinned against the two points that were actually decoded and checked
    by hand while building this: the docs' own example (Met Office's Exeter
    HQ) and the unqueryable nearest-to-Trafalgar-Square result."""

    def test_the_docs_example_decodes_to_devon(self):
        lat, lon = X._decode_geohash('gcj8ds')
        self.assertAlmostEqual(lat, 50.74, delta=0.05)
        self.assertAlmostEqual(lon, -3.40, delta=0.05)

    def test_the_unqueryable_nearest_result_decodes_onto_trafalgar_square(self):
        lat, lon = X._decode_geohash('gcpvj0')
        self.assertAlmostEqual(lat, 51.507, delta=0.01)
        self.assertAlmostEqual(lon, -0.126, delta=0.01)


class HaversineKm(unittest.TestCase):
    def test_the_same_point_is_zero(self):
        self.assertAlmostEqual(X.haversine_km(51.5, -0.1, 51.5, -0.1), 0.0, delta=0.001)

    def test_a_known_pair_is_roughly_right(self):
        # Trafalgar Square to the working station this was built against
        # (gcptq8, out near Northolt) — measured live at ~20.2 km.
        km = X.haversine_km(51.5074, -0.1278, 51.5506, -0.4120)
        self.assertAlmostEqual(km, 20.2, delta=0.5)


class YesterdaysRows(unittest.TestCase):
    """The Europe/London local-day filter. September dates are BST
    (UTC+1), so a naive UTC-day filter would drop 23:00-23:59 UTC (which
    is already the next London day) and would also fail to pick up
    23:00-23:59 UTC the day before (which is still the SAME London day the
    following morning) — this account runs on London local time throughout,
    not UTC, for exactly that reason."""

    def test_a_row_just_before_midnight_bst_counts_as_the_earlier_day(self):
        # 2026-09-13 23:30 BST = 2026-09-13 22:30 UTC.
        rows = [{'datetime': '2026-09-13T22:30:00Z', 'temperature': 15.0}]
        self.assertEqual(len(X.yesterdays_rows(rows, date(2026, 9, 13))), 1)

    def test_a_row_at_2300_utc_is_already_the_next_london_day(self):
        # 2026-09-13 23:30 UTC = 2026-09-14 00:30 BST — belongs to the 14th,
        # not the 13th, which a bare UTC .date() would get wrong.
        rows = [{'datetime': '2026-09-13T23:30:00Z', 'temperature': 15.0}]
        self.assertEqual(X.yesterdays_rows(rows, date(2026, 9, 13)), [])
        self.assertEqual(len(X.yesterdays_rows(rows, date(2026, 9, 14))), 1)

    def test_rows_on_other_days_are_excluded(self):
        rows = [{'datetime': '2026-09-12T10:00:00Z'}, {'datetime': '2026-09-14T10:00:00Z'}]
        self.assertEqual(X.yesterdays_rows(rows, date(2026, 9, 13)), [])

    def test_a_row_missing_or_unparseable_datetime_is_dropped_not_fatal(self):
        rows = [{'temperature': 1.0}, {'datetime': 'not-a-date'},
                {'datetime': '2026-09-13T10:00:00Z', 'temperature': 2.0}]
        self.assertEqual(len(X.yesterdays_rows(rows, date(2026, 9, 13))), 1)

    def test_empty_or_none_rows_is_empty_not_a_crash(self):
        self.assertEqual(X.yesterdays_rows([], date(2026, 9, 13)), [])
        self.assertEqual(X.yesterdays_rows(None, date(2026, 9, 13)), [])


class MiddayRow(unittest.TestCase):
    def test_picks_the_hour_closest_to_noon_london_time(self):
        rows = [{'datetime': '2026-09-13T09:00:00Z', 'humidity': 70},   # 10:00 BST
                {'datetime': '2026-09-13T11:00:00Z', 'humidity': 55},   # 12:00 BST — exact
                {'datetime': '2026-09-13T15:00:00Z', 'humidity': 40}]   # 16:00 BST
        self.assertEqual(X.midday_row(rows)['humidity'], 55)

    def test_a_tie_favours_the_earlier_hour(self):
        rows = [{'datetime': '2026-09-13T10:00:00Z', 'humidity': 1},    # 11:00 BST, -1h
                {'datetime': '2026-09-13T12:00:00Z', 'humidity': 2}]    # 13:00 BST, +1h
        self.assertEqual(X.midday_row(rows)['humidity'], 1)

    def test_empty_rows_is_none(self):
        self.assertIsNone(X.midday_row([]))

    def test_rows_all_missing_datetime_is_none(self):
        self.assertIsNone(X.midday_row([{'humidity': 1}]))


class EaNearestRainGauges(unittest.TestCase):
    def test_ranks_by_distance_and_picks_the_rainfall_measure(self):
        payload = {'items': [
            {'stationReference': 'FAR', 'lat': 52.0, 'long': -1.0,
             'measures': [{'@id': 'm-far', 'parameter': 'rainfall'}]},
            {'stationReference': 'NEAR', 'lat': 51.51, 'long': -0.13,
             'measures': [{'@id': 'm-near', 'parameter': 'rainfall'}]},
        ]}
        with patch.object(X, '_curl_json', return_value=payload):
            gauges = X.ea_nearest_rain_gauges()
        self.assertEqual(gauges[0]['station_ref'], 'NEAR')
        self.assertEqual(gauges[0]['measure_id'], 'm-near')
        self.assertEqual(gauges[1]['station_ref'], 'FAR')

    def test_a_station_with_no_rainfall_measure_is_skipped(self):
        payload = {'items': [
            {'stationReference': 'X', 'lat': 51.5, 'long': -0.1,
             'measures': [{'@id': 'm-level', 'parameter': 'level'}]},
        ]}
        with patch.object(X, '_curl_json', return_value=payload):
            self.assertEqual(X.ea_nearest_rain_gauges(), [])

    def test_a_station_missing_lat_or_long_is_skipped_not_fatal(self):
        payload = {'items': [
            {'stationReference': 'X', 'long': -0.1,
             'measures': [{'@id': 'm', 'parameter': 'rainfall'}]},
        ]}
        with patch.object(X, '_curl_json', return_value=payload):
            self.assertEqual(X.ea_nearest_rain_gauges(), [])

    def test_a_failed_call_is_an_empty_list_not_a_crash(self):
        with patch.object(X, '_curl_json', return_value=None):
            self.assertEqual(X.ea_nearest_rain_gauges(), [])


class EaDailyTotalMm(unittest.TestCase):
    """The distinction this whole function exists for: a real zero against
    no answer at all."""

    def test_sums_only_readings_on_the_target_london_day(self):
        def fetch(measure_id, utc_date):
            if utc_date == date(2026, 9, 13):
                return [{'dateTime': '2026-09-13T10:00:00Z', 'value': 1.2},
                         {'dateTime': '2026-09-13T14:00:00Z', 'value': 0.4}]
            return []
        with patch.object(X, 'ea_readings_for_utc_date', side_effect=fetch):
            total, saw_any = X.ea_daily_total_mm('m', date(2026, 9, 13))
        self.assertAlmostEqual(total, 1.6)
        self.assertTrue(saw_any)

    def test_reads_across_both_utc_dates_the_london_day_touches(self):
        # 2026-09-13 23:30 BST = 2026-09-13 22:30 UTC, so a rain total for
        # the 13th genuinely spans the UTC dates 2026-09-12 and 2026-09-13.
        def fetch(measure_id, utc_date):
            if utc_date == date(2026, 9, 12):
                return [{'dateTime': '2026-09-12T23:30:00Z', 'value': 0.6}]
            if utc_date == date(2026, 9, 13):
                return [{'dateTime': '2026-09-13T10:00:00Z', 'value': 1.0}]
            return []
        with patch.object(X, 'ea_readings_for_utc_date', side_effect=fetch):
            total, saw_any = X.ea_daily_total_mm('m', date(2026, 9, 13))
        self.assertAlmostEqual(total, 1.6)
        self.assertTrue(saw_any)

    def test_a_genuinely_dry_day_is_zero_with_saw_any_true(self):
        def fetch(measure_id, utc_date):
            return [{'dateTime': '2026-09-13T10:00:00Z', 'value': 0.0}] \
                if utc_date == date(2026, 9, 13) else []
        with patch.object(X, 'ea_readings_for_utc_date', side_effect=fetch):
            total, saw_any = X.ea_daily_total_mm('m', date(2026, 9, 13))
        self.assertEqual(total, 0.0)
        self.assertTrue(saw_any)  # measured, not merely absent

    def test_no_readings_at_all_is_saw_any_false_not_zero(self):
        with patch.object(X, 'ea_readings_for_utc_date', return_value=[]):
            total, saw_any = X.ea_daily_total_mm('m', date(2026, 9, 13))
        self.assertEqual(total, 0.0)
        self.assertFalse(saw_any)  # the caller must not print this as "0.0mm"

    def test_a_reading_on_the_wrong_local_day_is_excluded(self):
        # 2026-09-13 23:30 UTC = 2026-09-14 00:30 BST — already the 14th.
        def fetch(measure_id, utc_date):
            return [{'dateTime': '2026-09-13T23:30:00Z', 'value': 5.0}] \
                if utc_date == date(2026, 9, 13) else []
        with patch.object(X, 'ea_readings_for_utc_date', side_effect=fetch):
            total, saw_any = X.ea_daily_total_mm('m', date(2026, 9, 13))
        self.assertEqual(total, 0.0)
        self.assertFalse(saw_any)

    def test_a_reading_with_no_value_is_dropped_not_fatal(self):
        def fetch(measure_id, utc_date):
            return [{'dateTime': '2026-09-13T10:00:00Z', 'value': None},
                     {'dateTime': '2026-09-13T11:00:00Z', 'value': 0.5}] \
                if utc_date == date(2026, 9, 13) else []
        with patch.object(X, 'ea_readings_for_utc_date', side_effect=fetch):
            total, saw_any = X.ea_daily_total_mm('m', date(2026, 9, 13))
        self.assertAlmostEqual(total, 0.5)
        self.assertTrue(saw_any)


class FirstWorkingRainGauge(unittest.TestCase):
    def test_walks_past_a_silent_gauge(self):
        gauges = [{'station_ref': 'DEAD', 'distance_km': 3.0, 'measure_id': 'm-dead'},
                  {'station_ref': 'LIVE', 'distance_km': 8.0, 'measure_id': 'm-live'}]
        totals = {'m-dead': (0.0, False), 'm-live': (2.6, True)}
        with patch.object(X, 'ea_nearest_rain_gauges', return_value=gauges), \
             patch.object(X, 'ea_daily_total_mm', side_effect=lambda mid, d: totals[mid]):
            ref, dist, total = X.first_working_rain_gauge(date(2026, 9, 13))
        self.assertEqual(ref, 'LIVE')
        self.assertEqual(dist, 8.0)
        self.assertEqual(total, 2.6)

    def test_a_confirmed_dry_reading_counts_as_working(self):
        gauges = [{'station_ref': 'DRY', 'distance_km': 3.0, 'measure_id': 'm'}]
        with patch.object(X, 'ea_nearest_rain_gauges', return_value=gauges), \
             patch.object(X, 'ea_daily_total_mm', return_value=(0.0, True)):
            ref, dist, total = X.first_working_rain_gauge(date(2026, 9, 13))
        self.assertEqual((ref, dist, total), ('DRY', 3.0, 0.0))

    def test_every_gauge_silent_returns_none_triple(self):
        gauges = [{'station_ref': 'A', 'distance_km': 1.0, 'measure_id': 'm'}]
        with patch.object(X, 'ea_nearest_rain_gauges', return_value=gauges), \
             patch.object(X, 'ea_daily_total_mm', return_value=(0.0, False)):
            self.assertEqual(X.first_working_rain_gauge(date(2026, 9, 13)), (None, None, None))

    def test_no_gauges_at_all_returns_none_triple(self):
        with patch.object(X, 'ea_nearest_rain_gauges', return_value=[]):
            self.assertEqual(X.first_working_rain_gauge(date(2026, 9, 13)), (None, None, None))


class BuildCardLines(unittest.TestCase):
    def _rows(self, **over):
        base = [
            {'datetime': '2026-09-13T05:00:00Z', 'temperature': 12.0},   # low
            {'datetime': '2026-09-13T11:00:00Z', 'temperature': 19.5,    # midday, also high
             'weather_code': 3},
            {'datetime': '2026-09-13T18:00:00Z', 'temperature': 16.0},
        ]
        for row in base:
            row.update(over.get(row['datetime'], {}))
        return base

    def test_high_and_low_span_every_row_not_just_midday(self):
        _, lines, _ = X.build_card_lines(self._rows(), 'Greater London', 'gcptq8')
        self.assertEqual(next(l for l in lines if l['label'] == 'High')['value'], '20°C')
        self.assertEqual(next(l for l in lines if l['label'] == 'Low')['value'], '12°C')

    def test_no_temperature_readings_at_all_omits_high_and_low(self):
        rows = [{'datetime': '2026-09-13T11:00:00Z'}]
        _, lines, _ = X.build_card_lines(rows, 'Greater London', 'gcptq8')
        labels = [l['label'] for l in lines]
        self.assertNotIn('High', labels)
        self.assertNotIn('Low', labels)

    def test_never_shows_conditions_humidity_wind_sunshine_or_snow(self):
        # His call, 14 September 2026: High/Low(/Rain) only — this pins
        # that the card never grows one of these back, whatever a caller
        # passes in the rows.
        rows = self._rows()
        rows[1].update({'humidity': 58, 'wind_speed': 4.5, 'wind_direction': 'SW',
                        'sunshine': 3.0, 'snow': 1.0})
        _, lines, _ = X.build_card_lines(rows, 'Greater London', 'gcptq8')
        labels = [l['label'] for l in lines]
        for absent in ('Conditions', 'Humidity', 'Wind', 'Sunshine', 'Snow'):
            self.assertNotIn(absent, labels)

    def test_a_positive_rain_total_gets_its_own_row(self):
        _, lines, _ = X.build_card_lines(self._rows(), 'Greater London', 'gcptq8',
                                         rain_mm=2.6, rain_distance_km=5.4)
        self.assertEqual(next(l for l in lines if l['label'] == 'Rain')['value'], '2.6mm')

    def test_a_zero_rain_total_shows_no_rain_row(self):
        # A confirmed-dry day: his rule is "otherwise high and low are
        # sufficient", not a "Rain: None" line the way Seoul's card has.
        _, lines, _ = X.build_card_lines(self._rows(), 'Greater London', 'gcptq8',
                                         rain_mm=0.0, rain_distance_km=5.4)
        self.assertNotIn('Rain', [l['label'] for l in lines])

    def test_no_rain_figure_at_all_shows_no_rain_row(self):
        # No gauge answered — must not be treated as "confirmed dry".
        _, lines, _ = X.build_card_lines(self._rows(), 'Greater London', 'gcptq8')
        self.assertNotIn('Rain', [l['label'] for l in lines])

    def test_opener_text(self):
        opener, _, _ = X.build_card_lines(self._rows(), 'Greater London', 'gcptq8')
        self.assertEqual(opener['text'], "London's weather yesterday")

    def test_opener_emoji_falls_back_to_middays_weather_code_when_dry(self):
        opener, _, _ = X.build_card_lines(self._rows(), 'Greater London', 'gcptq8')
        self.assertEqual(opener['emoji'], X.WEATHER_EMOJI[3])

    def test_opener_emoji_is_rain_when_it_rained_even_over_a_sunny_code(self):
        rows = self._rows()
        rows[1]['weather_code'] = 1  # Sunny
        opener, _, _ = X.build_card_lines(rows, 'Greater London', 'gcptq8',
                                          rain_mm=2.6, rain_distance_km=5.4)
        self.assertEqual(opener['emoji'], '🌧️')

    def test_footnote_names_the_station_and_its_distance_honestly(self):
        # gcptq8 decodes ~20 km from Trafalgar Square — the footnote must
        # say so rather than implying a central-London reading.
        _, _, footnote = X.build_card_lines(self._rows(), 'Greater London', 'gcptq8')
        self.assertIn('Met Office observation', footnote)
        self.assertIn('Greater London', footnote)
        self.assertIn('km from central London', footnote)
        self.assertIn('20 km', footnote)

    def test_footnote_falls_back_to_a_generic_label_with_no_area(self):
        _, _, footnote = X.build_card_lines(self._rows(), None, 'gcptq8')
        self.assertIn('nearest reporting station with data', footnote)

    def test_footnote_never_claims_a_forecast(self):
        _, _, footnote = X.build_card_lines(self._rows(), 'Greater London', 'gcptq8')
        self.assertNotIn('forecast', footnote.lower())

    def test_footnote_credits_the_environment_agency_only_when_rain_shown(self):
        _, _, dry_footnote = X.build_card_lines(self._rows(), 'Greater London', 'gcptq8')
        self.assertNotIn('Environment Agency', dry_footnote)
        _, _, wet_footnote = X.build_card_lines(self._rows(), 'Greater London', 'gcptq8',
                                                 rain_mm=2.6, rain_distance_km=5.4)
        self.assertIn('Environment Agency gauge, about 5 km away', wet_footnote)


class BuildAlt(unittest.TestCase):
    def test_every_row_and_the_footnote_appear(self):
        opener = {'emoji': '⛅', 'text': "London's weather yesterday"}
        lines = [{'label': 'High', 'value': '20°C'}, {'label': 'Low', 'value': '12°C'}]
        alt = X.build_alt(opener, lines, 'Met Office observation: Greater London, '
                                          'the nearest reporting station with data, '
                                          'about 20 km from central London')
        self.assertIn('London’s weather yesterday', alt)  # curly() curls the apostrophe
        self.assertIn('High: 20°C', alt)
        self.assertIn('Low: 12°C', alt)
        self.assertIn('about 20 km from central London', alt)

    def test_no_footnote_is_omitted_not_a_blank_line(self):
        opener = {'emoji': '', 'text': 'x'}
        alt = X.build_alt(opener, [], '')
        self.assertEqual(alt.count('\n'), 0)


class FirstWorkingStation(unittest.TestCase):
    """The fix for the confirmed-live 404-nearest-station quirk: the nearest
    candidate can 404 while later ones answer, so this must walk the list
    rather than trust the first result."""

    def test_walks_past_a_dead_nearest_candidate(self):
        candidates = [{'geohash': 'gcpvj0', 'area': 'Greater London'},
                      {'geohash': 'gcptq8', 'area': 'Greater London'}]
        obs = {'gcptq8': [{'datetime': '2026-09-13T11:00:00Z', 'temperature': 19.0}]}
        with patch.object(X, 'nearest_candidates', return_value=candidates), \
             patch.object(X, 'observations_for', side_effect=lambda g, k: obs.get(g)):
            geohash, area, rows = X.first_working_station('key')
        self.assertEqual(geohash, 'gcptq8')
        self.assertEqual(area, 'Greater London')
        self.assertEqual(len(rows), 1)

    def test_the_first_candidate_working_is_used_directly(self):
        candidates = [{'geohash': 'gcptq8', 'area': 'Greater London'}]
        obs = {'gcptq8': [{'datetime': '2026-09-13T11:00:00Z', 'temperature': 19.0}]}
        with patch.object(X, 'nearest_candidates', return_value=candidates), \
             patch.object(X, 'observations_for', side_effect=lambda g, k: obs.get(g)):
            geohash, _, _ = X.first_working_station('key')
        self.assertEqual(geohash, 'gcptq8')

    def test_every_candidate_dead_returns_none_triple(self):
        candidates = [{'geohash': 'gcpvj0', 'area': 'Greater London'}]
        with patch.object(X, 'nearest_candidates', return_value=candidates), \
             patch.object(X, 'observations_for', return_value=None):
            result = X.first_working_station('key')
        self.assertEqual(result, (None, None, None))

    def test_no_candidates_at_all_returns_none_triple(self):
        with patch.object(X, 'nearest_candidates', return_value=[]):
            result = X.first_working_station('key')
        self.assertEqual(result, (None, None, None))

    def test_a_candidate_missing_its_own_geohash_is_skipped_not_fatal(self):
        candidates = [{'area': 'nowhere'}, {'geohash': 'gcptq8', 'area': 'Greater London'}]
        obs = {'gcptq8': [{'datetime': '2026-09-13T11:00:00Z', 'temperature': 19.0}]}
        with patch.object(X, 'nearest_candidates', return_value=candidates), \
             patch.object(X, 'observations_for', side_effect=lambda g, k: obs.get(g)):
            geohash, _, _ = X.first_working_station('key')
        self.assertEqual(geohash, 'gcptq8')


class AlreadyPosted(unittest.TestCase):
    """Guards the safety-net rerun, matching london_weather_post.py's own
    already_posted() exactly, against its own separate log file."""

    def _with_log(self, lines):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        log_path = Path(td.name) / 'wxday_history.jsonl'
        if lines is not None:
            log_path.write_text('\n'.join(lines) + ('\n' if lines else ''))
        return patch.object(X, 'WXDAY_LOG', log_path)

    def test_no_log_file_at_all_is_not_posted(self):
        with self._with_log(None):
            self.assertFalse(X.already_posted('2026-09-13'))

    def test_empty_log_is_not_posted(self):
        with self._with_log([]):
            self.assertFalse(X.already_posted('2026-09-13'))

    def test_a_different_date_in_the_log_is_not_posted(self):
        with self._with_log([json.dumps({'target_date': '2026-09-12'})]):
            self.assertFalse(X.already_posted('2026-09-13'))

    def test_the_target_dates_own_log_entry_is_posted(self):
        with self._with_log([json.dumps({'target_date': '2026-09-12'}),
                              json.dumps({'target_date': '2026-09-13'})]):
            self.assertTrue(X.already_posted('2026-09-13'))

    def test_a_corrupt_line_is_skipped_not_fatal(self):
        with self._with_log(['{not valid json', json.dumps({'target_date': '2026-09-13'})]):
            self.assertTrue(X.already_posted('2026-09-13'))


if __name__ == '__main__':
    unittest.main()
