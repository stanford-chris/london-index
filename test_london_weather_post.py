"""Tests for london_weather_post.py, the daily forecast card.

Same shape as seoul-index's test_seoul_weather_post.py: the failure to fear
is not a crash but a plausible wrong card (a dropped row read as "nothing to
say", a wet code losing its own description to a bolted-on rain-chance
sentence). So the tests pin the field-to-row reduction (build_card_lines),
the weather-code/UV-band tables, and the dedup guard (already_posted) — not
rendering or posting, which are covered by london_index_card.py's own smoke
test and by hand-verification against a live dry run once the account has
its Met Office key.

No network, no Chrome, no posting: nothing here calls fetch_daily_forecast,
render_card or atproto. sun_times() is exercised directly — it's a local
astral calculation, not a network call, so there's nothing to mock.
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
import london_index_card as C
import london_weather_post as W


class FmtC(unittest.TestCase):
    def test_rounds_to_the_nearest_whole_degree(self):
        self.assertEqual(W.fmt_c(19.4), '19°C')
        self.assertEqual(W.fmt_c(19.6), '20°C')

    def test_no_fahrenheit_pairing(self):
        # Deliberately unlike Seoul Index's English card: this account
        # keeps full British convention, and UK forecasts are Celsius-only.
        self.assertNotIn('°F', W.fmt_c(19.0))


class FormatAmpm(unittest.TestCase):
    def test_on_the_hour_omits_minutes(self):
        self.assertEqual(W.format_ampm(5, 0), '5 a.m.')
        self.assertEqual(W.format_ampm(17, 0), '5 p.m.')

    def test_minutes_are_kept_and_zero_padded(self):
        self.assertEqual(W.format_ampm(6, 3), '6:03 a.m.')
        self.assertEqual(W.format_ampm(19, 38), '7:38 p.m.')

    def test_midnight_and_noon_are_still_twelve(self):
        self.assertEqual(W.format_ampm(0, 0), '12 a.m.')
        self.assertEqual(W.format_ampm(12, 0), '12 p.m.')


class UvBand(unittest.TestCase):
    def test_the_who_bands(self):
        self.assertEqual(W.uv_band(0), 'Low')
        self.assertEqual(W.uv_band(2), 'Low')
        self.assertEqual(W.uv_band(3), 'Moderate')
        self.assertEqual(W.uv_band(5), 'Moderate')
        self.assertEqual(W.uv_band(6), 'High')
        self.assertEqual(W.uv_band(8), 'Very high')
        self.assertEqual(W.uv_band(11), 'Extreme')
        self.assertEqual(W.uv_band(14), 'Extreme')


class ConditionsText(unittest.TestCase):
    def test_a_plain_sky_reading_gets_the_chance_of_rain_appended(self):
        # code 7 = Cloudy, not in WET_CODES.
        self.assertEqual(W.conditions_text(7, 40), 'Cloudy with a 40% chance of rain')

    def test_a_plain_sky_reading_with_no_pop_shows_the_sky_alone(self):
        self.assertEqual(W.conditions_text(1, None), 'Sunny')

    def test_a_wet_code_keeps_its_own_description_and_appends_the_percent(self):
        # code 24 = Light snow — must not be overwritten with generic "rain"
        # wording the way a plain-sky code's row is.
        self.assertEqual(W.conditions_text(24, 60), 'Light snow, 60% chance of rain')

    def test_a_wet_code_with_no_pop_shows_its_description_alone(self):
        self.assertEqual(W.conditions_text(15, None), 'Heavy rain')

    def test_an_unknown_code_with_a_pop_still_states_the_chance(self):
        self.assertEqual(W.conditions_text(99, 25), '25% chance of rain')

    def test_an_unknown_code_with_no_pop_is_empty(self):
        # The caller must be able to drop the row entirely rather than
        # print a blank "Conditions:" line.
        self.assertEqual(W.conditions_text(99, None), '')

    def test_code_4_not_used_behaves_like_unknown(self):
        self.assertEqual(W.conditions_text(4, None), '')
        self.assertEqual(W.conditions_text(4, 10), '10% chance of rain')


class BuildCardLines(unittest.TestCase):
    def _entry(self, **over):
        base = {'dayMaxScreenTemperature': 19.4, 'nightMinScreenTemperature': 11.2,
                'daySignificantWeatherCode': 3, 'dayProbabilityOfPrecipitation': 20,
                'maxUvIndex': 4.6, 'middayRelativeHumidity': 62.0}
        base.update(over)
        return base

    def test_high_and_low_rows(self):
        _, lines, _ = W.build_card_lines(self._entry())
        self.assertEqual(next(l for l in lines if l['label'] == 'High')['value'], '19°C')
        self.assertEqual(next(l for l in lines if l['label'] == 'Low')['value'], '11°C')

    def test_a_missing_temperature_omits_only_that_row(self):
        _, lines, _ = W.build_card_lines(self._entry(dayMaxScreenTemperature=None))
        labels = [l['label'] for l in lines]
        self.assertNotIn('High', labels)
        self.assertIn('Low', labels)

    def test_uv_row_rounds_and_names_its_band(self):
        _, lines, _ = W.build_card_lines(self._entry(maxUvIndex=6.7))
        self.assertEqual(next(l for l in lines if l['label'] == 'UV index')['value'], '7 (High)')

    def test_no_uv_omits_the_row(self):
        _, lines, _ = W.build_card_lines(self._entry(maxUvIndex=None))
        self.assertNotIn('UV index', [l['label'] for l in lines])

    def test_humidity_row_when_present(self):
        _, lines, _ = W.build_card_lines(self._entry(middayRelativeHumidity=58.0))
        self.assertEqual(next(l for l in lines if l['label'] == 'Humidity')['value'], '58%')

    def test_no_humidity_omits_the_row(self):
        _, lines, _ = W.build_card_lines(self._entry(middayRelativeHumidity=None))
        self.assertNotIn('Humidity', [l['label'] for l in lines])

    def test_sunrise_and_sunset_share_one_merged_row(self):
        # Matches Seoul Index's own card exactly, 5 September 2026: one row,
        # the time inside "Sunrise ..." bolded via 'emph', the sunset
        # reading packed into the value slot via 'value_lead', and no
        # dotted leader between the two (see london_index_card.py).
        _, lines, _ = W.build_card_lines(self._entry(), sunrise='6:19 a.m.', sunset='7:38 p.m.')
        row = next(l for l in lines if l['label'].startswith('Sunrise'))
        self.assertEqual(row['label'], 'Sunrise 6:19 a.m.')
        self.assertEqual(row['emph'], '6:19 a.m.')
        self.assertEqual(row['value_lead'], '🌙 Sunset ')
        self.assertEqual(row['value'], '7:38 p.m.')
        self.assertTrue(row['no_leader'])
        self.assertEqual(row['alt'], 'Sunrise 6:19 a.m., Sunset 7:38 p.m.')

    def test_no_sun_times_omits_the_row(self):
        _, lines, _ = W.build_card_lines(self._entry())
        self.assertFalse(any(l['label'].startswith('Sunrise') for l in lines))

    def test_only_one_of_the_pair_present_also_omits_the_row(self):
        # sun_times() only ever returns both or neither, but the row logic
        # itself should not assume that.
        _, lines, _ = W.build_card_lines(self._entry(), sunrise='6:19 a.m.')
        self.assertFalse(any(l['label'].startswith('Sunrise') for l in lines))
        _, lines, _ = W.build_card_lines(self._entry(), sunset='7:38 p.m.')
        self.assertFalse(any(l['label'].startswith('Sunrise') for l in lines))

    def test_opener_emoji_follows_the_days_code(self):
        opener, _, _ = W.build_card_lines(self._entry(daySignificantWeatherCode=15))
        self.assertEqual(opener['emoji'], W.WEATHER_EMOJI[15])

    def test_every_row_carries_its_own_emoji(self):
        # His call, 5 September 2026: per-row emoji, matching Seoul's card.
        _, lines, _ = W.build_card_lines(self._entry(), sunrise='6:19 a.m.', sunset='7:38 p.m.')
        by_label = {l['label']: l['emoji'] for l in lines}
        self.assertEqual(by_label['High'], '🔺')
        self.assertEqual(by_label['Low'], '🔻')
        self.assertEqual(by_label['Conditions'], W.WEATHER_EMOJI[3])
        self.assertEqual(by_label['UV index'], '🔆')
        self.assertEqual(by_label['Humidity'], '💧')
        self.assertEqual(by_label['Sunrise 6:19 a.m.'], '☀️')

    def test_footnote_states_this_is_a_forecast_not_an_observation(self):
        _, _, footnote = W.build_card_lines(self._entry())
        self.assertIn('forecast', footnote.lower())
        self.assertIn('not an observed reading', footnote)

    def test_opener_text_names_london_and_today(self):
        opener, _, _ = W.build_card_lines(self._entry())
        self.assertEqual(opener['text'], "London's forecast for today")


class BuildAlt(unittest.TestCase):
    def test_every_row_and_the_footnote_appear(self):
        opener = {'emoji': '⛅', 'text': "London's forecast for today"}
        lines = [{'label': 'High', 'value': '19°C'}, {'label': 'Low', 'value': '11°C'}]
        alt = W.build_alt(opener, lines, "Met Office's forecast: not an observed reading")
        self.assertIn('London’s forecast for today', alt)  # curly() curls the apostrophe
        self.assertIn('High: 19°C', alt)
        self.assertIn('Low: 11°C', alt)
        self.assertIn('not an observed reading', alt)

    def test_no_footnote_is_omitted_not_a_blank_line(self):
        opener = {'emoji': '', 'text': 'x'}
        alt = W.build_alt(opener, [], '')
        self.assertEqual(alt.count('\n'), 0)

    def test_a_row_with_its_own_alt_uses_that_instead_of_label_colon_value(self):
        # The merged sunrise/sunset row: the default "{label}: {value}"
        # template would print "Sunrise 6:19 a.m.: 7:38 p.m." with no word
        # saying what the second time even is.
        opener = {'emoji': '', 'text': 'x'}
        lines = [{'label': 'Sunrise 6:19 a.m.', 'value': '7:38 p.m.',
                  'alt': 'Sunrise 6:19 a.m., Sunset 7:38 p.m.'}]
        alt = W.build_alt(opener, lines, '')
        self.assertIn('Sunrise 6:19 a.m., Sunset 7:38 p.m.', alt)
        self.assertNotIn('Sunrise 6:19 a.m.: 7:38 p.m.', alt)


class LineHtml(unittest.TestCase):
    """The renderer half of the emoji/emph/value_lead/no_leader additions to
    london_index_card.py — pure string work, same shape as
    seoul-index's own NoLeaderRow/BoldPeriodRow tests. A plain row (no vein
    here sets these keys except the weather one) must render byte-identical
    to before, so every existing index card stays visually unchanged."""

    def test_a_plain_row_is_unchanged_by_any_of_the_new_keys(self):
        html = C._line_html({'label': 'Busiest station: Euston', 'value': '11% of typical'})
        self.assertIn('class="leader"', html)
        self.assertNotIn('leader plain', html)
        self.assertNotIn('<b>', html)
        self.assertNotIn('valreg', html)

    def test_emoji_prefixes_the_label(self):
        html = C._line_html({'emoji': '🔺', 'label': 'High', 'value': '22°C'})
        self.assertIn('🔺 High', html)

    def test_no_leader_gets_the_plain_class(self):
        html = C._line_html({'label': 'Sunrise 6:19 a.m.', 'value': '7:38 p.m.',
                             'no_leader': True})
        self.assertIn('class="leader plain"', html)

    def test_emph_bolds_just_that_run_inside_the_label(self):
        html = C._line_html({'label': 'Sunrise 6:19 a.m.', 'emph': '6:19 a.m.',
                             'value': '7:38 p.m.'})
        self.assertIn('<b>6:19 a.m.</b>', html)
        self.assertNotIn('<b>Sunrise 6:19 a.m.</b>', html)

    def test_value_lead_renders_at_regular_weight_before_the_bold_value(self):
        html = C._line_html({'label': 'Sunrise 6:19 a.m.', 'value_lead': '🌙 Sunset ',
                             'value': '7:38 p.m.'})
        self.assertIn('<span class="valreg">🌙 Sunset </span>7:38 p.m.', html)


class TodaysEntry(unittest.TestCase):
    def test_matches_on_the_date_prefix(self):
        series = [{'time': '2026-09-04T00:00:00Z', 'dayMaxScreenTemperature': 18},
                  {'time': '2026-09-05T00:00:00Z', 'dayMaxScreenTemperature': 20}]
        self.assertEqual(W.todays_entry(series, date(2026, 9, 5))['dayMaxScreenTemperature'], 20)

    def test_no_matching_date_is_none(self):
        series = [{'time': '2026-09-04T00:00:00Z'}]
        self.assertIsNone(W.todays_entry(series, date(2026, 9, 5)))

    def test_empty_or_none_series_is_none_not_a_crash(self):
        self.assertIsNone(W.todays_entry([], date(2026, 9, 5)))
        self.assertIsNone(W.todays_entry(None, date(2026, 9, 5)))

    def test_a_row_missing_time_entirely_is_skipped_not_fatal(self):
        series = [{'dayMaxScreenTemperature': 18}, {'time': '2026-09-05T00:00:00Z', 'x': 1}]
        self.assertEqual(W.todays_entry(series, date(2026, 9, 5))['x'], 1)


class SunTimes(unittest.TestCase):
    """A local astral calculation — no network, so this runs for real rather
    than mocking anything. Pinned against known-good London sun times."""

    def test_a_september_day_matches_known_london_times(self):
        sunrise, sunset = W.sun_times(date(2026, 9, 5))
        self.assertEqual(sunrise, '6:19 a.m.')
        self.assertEqual(sunset, '7:37 p.m.')

    def test_a_january_day_uses_gmt_not_a_fixed_utc_plus_one(self):
        # Confirms the ZoneInfo('Europe/London') pass-through actually
        # resolves GMT in winter rather than carrying BST's +1 year-round,
        # unlike london_index_post.py's own hardcoded LONDON_TZ constant.
        sunrise, sunset = W.sun_times(date(2026, 1, 5))
        self.assertEqual(sunrise, '8:05 a.m.')
        self.assertEqual(sunset, '4:06 p.m.')


class AlreadyPosted(unittest.TestCase):
    """Guards the safety-net rerun exactly as seoul_weather_post.py's own
    already_posted() does — see com.chrisstanford.londonweather.plist."""

    def _with_log(self, lines):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        log_path = Path(td.name) / 'weather_history.jsonl'
        if lines is not None:
            log_path.write_text('\n'.join(lines) + ('\n' if lines else ''))
        return patch.object(W, 'WEATHER_LOG', log_path)

    def test_no_log_file_at_all_is_not_posted(self):
        with self._with_log(None):
            self.assertFalse(W.already_posted('2026-09-05'))

    def test_empty_log_is_not_posted(self):
        with self._with_log([]):
            self.assertFalse(W.already_posted('2026-09-05'))

    def test_a_different_date_in_the_log_is_not_posted(self):
        with self._with_log([json.dumps({'target_date': '2026-09-04'})]):
            self.assertFalse(W.already_posted('2026-09-05'))

    def test_todays_date_in_the_log_is_posted(self):
        with self._with_log([json.dumps({'target_date': '2026-09-04'}),
                              json.dumps({'target_date': '2026-09-05'})]):
            self.assertTrue(W.already_posted('2026-09-05'))

    def test_a_corrupt_line_is_skipped_not_fatal(self):
        with self._with_log(['{not valid json', json.dumps({'target_date': '2026-09-05'})]):
            self.assertTrue(W.already_posted('2026-09-05'))


if __name__ == '__main__':
    unittest.main()
