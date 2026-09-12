"""Tests for the vein-rotation machinery in london_index_select.py:
apply_cooldown(), promote_starved() and update_state().

Ported from Seoul Index's own apply_cooldown()/promote_starved(), built
6 September 2026 after 20 real posts showed exactly the failure these exist
to prevent: station_usage and daily_footfall (two data sources answering
the same "which station is busiest" question) were two-thirds of every
post once tfl_crowding was paused, while tfl_bikes, flood, police and
cycle_hires led none of them.

The refusal-to-fire tests are the point, same as everywhere else in this
codebase: a cooldown or a starve-promotion that fires on a malformed
timestamp, or that empties the pool and skips a post, is worse than no
guard at all. No network, no claude -p call — subprocess.run is mocked in
the one test that exercises select()'s wiring end to end.
"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import london_index_select as S


def mkfact(vein, n, pair=None):
    """n facts for one vein, shaped enough for these functions (they only
    ever look at 'id', 'vein' and, for select()'s own wiring, 'pair')."""
    return [{'id': f'{vein}:{i}', 'vein': vein, 'label': f'{vein} {i}',
             'value': str(i), 'pair': pair} for i in range(n)]


def iso(days_ago=0, hours_ago=0):
    return (datetime.now(timezone.utc)
            - timedelta(days=days_ago, hours=hours_ago)).isoformat()


class ApplyCooldown(unittest.TestCase):
    def setUp(self):
        self.pool = (mkfact('station_usage', 4) + mkfact('daily_footfall', 2)
                     + mkfact('river_levels', 2))

    def test_no_stamp_at_all_no_cooldown(self):
        out = S.apply_cooldown(self.pool, {}, S.BUSIEST_STATION_VEINS,
                               S.BUSIEST_STATION_COOLDOWN_DAYS, 'test')
        self.assertEqual(out, self.pool)

    def test_recent_stamp_on_either_vein_drops_the_whole_group(self):
        state = {'vein_last_at': {'daily_footfall': iso(hours_ago=1)}}
        out = S.apply_cooldown(self.pool, state, S.BUSIEST_STATION_VEINS,
                               S.BUSIEST_STATION_COOLDOWN_DAYS, 'test')
        veins = {f['vein'] for f in out}
        self.assertNotIn('station_usage', veins)
        self.assertNotIn('daily_footfall', veins)
        self.assertIn('river_levels', veins)

    def test_stamp_older_than_the_window_does_not_cool_down(self):
        state = {'vein_last_at': {
            'station_usage': iso(days_ago=S.BUSIEST_STATION_COOLDOWN_DAYS + 1)}}
        out = S.apply_cooldown(self.pool, state, S.BUSIEST_STATION_VEINS,
                               S.BUSIEST_STATION_COOLDOWN_DAYS, 'test')
        self.assertEqual(out, self.pool)

    def test_malformed_stamp_is_ignored_not_raised(self):
        state = {'vein_last_at': {'station_usage': 'not-a-timestamp'}}
        out = S.apply_cooldown(self.pool, state, S.BUSIEST_STATION_VEINS,
                               S.BUSIEST_STATION_COOLDOWN_DAYS, 'test')
        self.assertEqual(out, self.pool)

    def test_the_actual_incident_gaps_are_now_blocked(self):
        # Real exact-repeat gaps found on the live feed once bot_variety_check
        # was pointed at this bot, 8 September 2026: "Busiest Tube stations"
        # 2d8h apart, "Transport for London footfall" 2d21h apart — both
        # past the old 2-day cooldown, both must now be caught by the 4-day
        # one. A stamp 2 days 21 hours old is the closest of the two to the
        # boundary, so it is the sharper check.
        state = {'vein_last_at': {'daily_footfall':
                 (datetime.now(timezone.utc)
                  - timedelta(days=2, hours=21)).isoformat()}}
        out = S.apply_cooldown(self.pool, state, S.BUSIEST_STATION_VEINS,
                               S.BUSIEST_STATION_COOLDOWN_DAYS, 'test')
        veins = {f['vein'] for f in out}
        self.assertNotIn('daily_footfall', veins)
        self.assertNotIn('station_usage', veins)

    def test_abandoned_rather_than_emptying_the_pool(self):
        # Nothing left outside the cooled group with >= 2 facts of its own.
        pool = mkfact('station_usage', 4) + mkfact('daily_footfall', 2)
        state = {'vein_last_at': {'station_usage': iso(hours_ago=1)}}
        out = S.apply_cooldown(pool, state, S.BUSIEST_STATION_VEINS,
                               S.BUSIEST_STATION_COOLDOWN_DAYS, 'test')
        self.assertEqual(out, pool)


class PromoteStarved(unittest.TestCase):
    def test_never_posted_vein_is_promoted_over_a_recently_led_one(self):
        pool = mkfact('tfl_bikes', 3) + mkfact('river_levels', 2)
        state = {'vein_last_at': {'river_levels': iso(hours_ago=1)}}
        out, promoted = S.promote_starved(pool, state)
        self.assertEqual(promoted, 'tfl_bikes')
        self.assertTrue(all(f['vein'] == 'tfl_bikes' for f in out))

    def test_below_starve_min_facts_is_never_promoted(self):
        # flood's real shape: exactly one fact, permanently.
        pool = mkfact('flood', 1) + mkfact('river_levels', 2)
        state = {'vein_last_at': {'river_levels': iso(hours_ago=1)}}
        out, promoted = S.promote_starved(pool, state)
        self.assertIsNone(promoted)
        self.assertEqual(out, pool)

    def test_nothing_starved_when_everything_posted_recently(self):
        pool = mkfact('tfl_bikes', 3) + mkfact('river_levels', 2)
        state = {'vein_last_at': {'tfl_bikes': iso(hours_ago=1),
                                   'river_levels': iso(hours_ago=2)}}
        out, promoted = S.promote_starved(pool, state)
        self.assertIsNone(promoted)
        self.assertEqual(out, pool)

    def test_longest_waiting_vein_wins(self):
        pool = mkfact('tfl_bikes', 3) + mkfact('river_levels', 2)
        state = {'vein_last_at': {'tfl_bikes': iso(days_ago=3),
                                   'river_levels': iso(days_ago=5)}}
        out, promoted = S.promote_starved(pool, state)
        self.assertEqual(promoted, 'river_levels')

    def test_tie_between_never_posted_veins_is_deterministic(self):
        pool = mkfact('tfl_bikes', 3) + mkfact('river_levels', 2)
        out, promoted = S.promote_starved(pool, {})
        # Both never posted; alphabetical tie-break, not dict order.
        self.assertEqual(promoted, 'river_levels')

    def test_malformed_stamp_treated_as_never_posted(self):
        pool = mkfact('tfl_bikes', 3) + mkfact('river_levels', 2)
        state = {'vein_last_at': {'tfl_bikes': iso(hours_ago=1),
                                   'river_levels': 'garbage'}}
        out, promoted = S.promote_starved(pool, state)
        self.assertEqual(promoted, 'river_levels')


class UpdateState(unittest.TestCase):
    def test_records_ids_and_stamps_the_vein(self):
        state = {}
        sel = {'ids': ['a:1', 'a:2'], 'vein': 'river_levels'}
        state = S.update_state(state, sel)
        self.assertEqual(state['recent_ids'], ['a:1', 'a:2'])
        self.assertIn('river_levels', state['vein_last_at'])

    def test_no_vein_key_stamps_nothing(self):
        state = {}
        sel = {'ids': ['a:1']}
        state = S.update_state(state, sel)
        self.assertEqual(state['recent_ids'], ['a:1'])
        self.assertNotIn('vein_last_at', state)

    def test_recent_ids_trimmed_to_keep(self):
        state = {'recent_ids': [f'x:{i}' for i in range(S.RECENT_IDS_KEEP)]}
        sel = {'ids': ['new:1', 'new:2']}
        state = S.update_state(state, sel)
        self.assertEqual(len(state['recent_ids']), S.RECENT_IDS_KEEP)
        self.assertEqual(state['recent_ids'][-2:], ['new:1', 'new:2'])

    def test_stamping_a_second_vein_does_not_clobber_the_first(self):
        state = {}
        state = S.update_state(state, {'ids': ['a:1'], 'vein': 'tfl_bikes'})
        state = S.update_state(state, {'ids': ['b:1'], 'vein': 'river_levels'})
        self.assertIn('tfl_bikes', state['vein_last_at'])
        self.assertIn('river_levels', state['vein_last_at'])


class DcmsMuseumsCooldown(unittest.TestCase):
    """dcms_museums is annual/static data: a repeat pick of the same pair is
    a byte-identical card, not just a repeated theme, which is why it gets
    its own cooldown group rather than relying on recent_ids alone — see
    the museum_gap duplicate of 5/8 September 2026 in the module docstring."""

    def setUp(self):
        self.pool = mkfact('dcms_museums', 3) + mkfact('river_levels', 2)

    def test_recent_post_drops_the_vein(self):
        state = {'vein_last_at': {'dcms_museums': iso(hours_ago=1)}}
        out = S.apply_cooldown(self.pool, state, S.DCMS_MUSEUMS_VEINS,
                               S.DCMS_MUSEUMS_COOLDOWN_DAYS, 'test')
        veins = {f['vein'] for f in out}
        self.assertNotIn('dcms_museums', veins)
        self.assertIn('river_levels', veins)

    def test_stamp_older_than_the_window_does_not_cool_down(self):
        state = {'vein_last_at': {
            'dcms_museums': iso(days_ago=S.DCMS_MUSEUMS_COOLDOWN_DAYS + 1)}}
        out = S.apply_cooldown(self.pool, state, S.DCMS_MUSEUMS_VEINS,
                               S.DCMS_MUSEUMS_COOLDOWN_DAYS, 'test')
        self.assertEqual(out, self.pool)

    def test_the_actual_incident_gap_is_now_blocked(self):
        # The real duplicate was 3 days apart (5 Sept 16:04 -> 8 Sept
        # 16:04). A stamp 3 days old must still be within the 4-day window.
        state = {'vein_last_at': {'dcms_museums': iso(days_ago=3)}}
        out = S.apply_cooldown(self.pool, state, S.DCMS_MUSEUMS_VEINS,
                               S.DCMS_MUSEUMS_COOLDOWN_DAYS, 'test')
        self.assertNotIn('dcms_museums', {f['vein'] for f in out})

    def test_select_applies_both_cooldowns_together(self):
        pool = (mkfact('station_usage', 4) + mkfact('dcms_museums', 3)
                + mkfact('tfl_bikes', 3))
        state = {'vein_last_at': {
            'station_usage': iso(hours_ago=1),
            'dcms_museums': iso(hours_ago=1),
        }}
        captured = {}

        def fake_run(cmd, **kwargs):
            captured['prompt'] = cmd[-1]

            class Result:
                returncode = 0
                stdout = ('{"opener": {"emoji": "", "text": "Test"}, '
                          '"ids": ["tfl_bikes:0", "tfl_bikes:1"]}')
                stderr = ''
            return Result()

        with patch('subprocess.run', side_effect=fake_run):
            sel = S.select(pool, state)

        self.assertEqual(sel['vein'], 'tfl_bikes')
        self.assertNotIn('station_usage:0', captured['prompt'])
        self.assertNotIn('dcms_museums:0', captured['prompt'])


class SelectWiring(unittest.TestCase):
    """Confirms select() actually applies both guards before ever building
    the prompt — not just that the guard functions work in isolation."""

    def _fake_claude(self, ids, opener_text='Test opener'):
        class Result:
            returncode = 0
            stdout = (f'{{"opener": {{"emoji": "", "text": "{opener_text}"}}, '
                      f'"ids": {ids!r}}}').replace("'", '"')
            stderr = ''
        return Result()

    def test_cooled_and_starved_veins_never_reach_the_prompt(self):
        pool = (mkfact('station_usage', 4) + mkfact('daily_footfall', 2)
                + mkfact('tfl_bikes', 3) + mkfact('river_levels', 2))
        # station_usage/daily_footfall on cooldown; river_levels posted
        # recently so it isn't force-promoted out from under tfl_bikes;
        # tfl_bikes never posted, so it's the one legitimately starved.
        state = {'vein_last_at': {
            'station_usage': iso(hours_ago=1),
            'river_levels': iso(hours_ago=1),
        }}
        captured = {}

        def fake_run(cmd, **kwargs):
            captured['prompt'] = cmd[-1]
            return self._fake_claude(['tfl_bikes:0', 'tfl_bikes:1'])

        with patch('subprocess.run', side_effect=fake_run):
            sel = S.select(pool, state)

        self.assertEqual(sel['vein'], 'tfl_bikes')
        self.assertNotIn('station_usage:0', captured['prompt'])
        self.assertNotIn('daily_footfall:0', captured['prompt'])
        # promote_starved narrowed the pool to tfl_bikes alone, so
        # river_levels shouldn't have reached the prompt either.
        self.assertNotIn('river_levels:0', captured['prompt'])


class SpentFacts(unittest.TestCase):
    """The 12 September 2026 guard: a fact already posted at this value is
    withheld, a pair group goes with any spent member, and a pool with
    nothing fresh raises rather than repeating. The two real cards that
    prompted it are the fixtures."""

    CAMDEN = [{'label': 'Most: Camden', 'value': '3,179'},
              {'label': 'Fewest: Bromley', 'value': '449'}]

    def _history(self, cards):
        import json, tempfile
        fh = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
        for lines in cards:
            fh.write(json.dumps({'at': 'x', 'primary_vein': 'police_boroughs',
                                 'veins': ['police_boroughs'], 'opener': 'Reported crime',
                                 'dateline': 'July 2026', 'lines': lines}) + '\n')
        fh.close()
        self.addCleanup(Path(fh.name).unlink)
        return fh.name

    def test_posted_lines_reads_every_line_of_every_card(self):
        seen = S.posted_lines(self._history([self.CAMDEN]))
        self.assertEqual(seen, {('Most: Camden', '3,179'), ('Fewest: Bromley', '449')})

    def test_missing_history_is_empty_not_fatal(self):
        self.assertEqual(S.posted_lines('/nonexistent/card_history.jsonl'), set())

    def test_garbage_line_in_history_is_skipped(self):
        path = self._history([self.CAMDEN])
        with open(path, 'a') as fh:
            fh.write('not json\n')
        self.assertEqual(len(S.posted_lines(path)), 2)

    def test_the_actual_incident_card_is_withheld(self):
        pool = [{'id': 'police_boroughs:most-camden', 'vein': 'police_boroughs',
                 'label': 'Most: Camden', 'value': '3,179', 'pair': 'police_gap'},
                {'id': 'police_boroughs:fewest-bromley', 'vein': 'police_boroughs',
                 'label': 'Fewest: Bromley', 'value': '449', 'pair': 'police_gap'},
                {'id': 'tfl_bikes:a', 'vein': 'tfl_bikes', 'label': 'Available', 'value': '9,234', 'pair': None},
                {'id': 'tfl_bikes:b', 'vein': 'tfl_bikes', 'label': 'Empty docks', 'value': '109 of 800', 'pair': None}]
        fresh, withheld = S.drop_spent(pool, S.posted_lines(self._history([self.CAMDEN])))
        self.assertEqual(withheld, 2)
        self.assertEqual({f['vein'] for f in fresh}, {'tfl_bikes'})

    def test_same_label_new_value_is_fresh(self):
        # The month rolls over: Camden still leads, at a new figure.
        pool = [{'id': 'a', 'vein': 'police_boroughs', 'label': 'Most: Camden',
                 'value': '3,301', 'pair': 'police_gap'}]
        fresh, withheld = S.drop_spent(pool, {('Most: Camden', '3,179')})
        self.assertEqual(withheld, 0)
        self.assertEqual(fresh, pool)

    def test_one_spent_member_takes_the_whole_pair_group(self):
        pool = [{'id': f'station_usage:{n}', 'vein': 'station_usage', 'label': n,
                 'value': v, 'pair': 'usage_top'}
                for n, v in (('Waterloo', '74,483,879'), ('King’s Cross', '73,571,468'),
                             ('Tottenham Court Road', '60,813,501'), ('Victoria', '60,156,525'))]
        pool.append({'id': 'station_usage:gap', 'vein': 'station_usage',
                     'label': 'Quietest: Roding Valley', 'value': '204,505', 'pair': 'usage_gap'})
        fresh, withheld = S.drop_spent(pool, {('Waterloo', '74,483,879')})
        self.assertEqual(withheld, 4)
        self.assertEqual([f['label'] for f in fresh], ['Quietest: Roding Valley'])

    def test_unpaired_spent_fact_takes_only_itself(self):
        pool = [{'id': 'laqn:a', 'vein': 'laqn', 'label': 'Boroughs with a monitor', 'value': '33', 'pair': None},
                {'id': 'laqn:b', 'vein': 'laqn', 'label': 'Worst reading: Ozone', 'value': 'index 2 (Low)', 'pair': None}]
        fresh, withheld = S.drop_spent(pool, {('Boroughs with a monitor', '33')})
        self.assertEqual(withheld, 1)
        self.assertEqual([f['label'] for f in fresh], ['Worst reading: Ozone'])

    def test_select_raises_nothing_fresh_rather_than_repeating(self):
        pool = [{'id': 'police_boroughs:most-camden', 'vein': 'police_boroughs',
                 'label': 'Most: Camden', 'value': '3,179', 'pair': 'police_gap'},
                {'id': 'police_boroughs:fewest-bromley', 'vein': 'police_boroughs',
                 'label': 'Fewest: Bromley', 'value': '449', 'pair': 'police_gap'}]
        with patch('subprocess.run') as run:
            with self.assertRaises(S.NothingFresh):
                S.select(pool, {}, history_path=self._history([self.CAMDEN]))
            run.assert_not_called()

    def test_select_drops_spent_before_the_prompt(self):
        pool = [{'id': 'police_boroughs:most-camden', 'vein': 'police_boroughs',
                 'label': 'Most: Camden', 'value': '3,179', 'pair': 'police_gap'},
                {'id': 'police_boroughs:fewest-bromley', 'vein': 'police_boroughs',
                 'label': 'Fewest: Bromley', 'value': '449', 'pair': 'police_gap'}] + mkfact('tfl_bikes', 3)
        captured = {}

        def fake_run(cmd, **kwargs):
            captured['prompt'] = cmd[-1]
            return SelectWiring._fake_claude(None, ['tfl_bikes:0', 'tfl_bikes:1'])

        with patch('subprocess.run', side_effect=fake_run):
            sel = S.select(pool, {}, history_path=self._history([self.CAMDEN]))
        self.assertEqual(sel['vein'], 'tfl_bikes')
        # The id, not the label: "Most: Camden" is quoted in SELECT_PROMPT's
        # own rules text, so the label is in every prompt regardless.
        self.assertNotIn('police_boroughs:most-camden', captured['prompt'])
        self.assertIn('tfl_bikes:0', captured['prompt'])

    def test_card_key_ignores_opener_and_matches_posted_card(self):
        posted = S.posted_cards(self._history([self.CAMDEN]))
        self.assertIn(S.card_lines_key(self.CAMDEN), posted)
        self.assertNotIn(S.card_lines_key(self.CAMDEN[:1]), posted)


class GeneralCooldown(unittest.TestCase):
    def test_vein_that_led_within_the_day_is_withheld(self):
        state = {'vein_last_at': {'tfl_bikes': iso(hours_ago=5),
                                  'laqn': iso(days_ago=3)}}
        self.assertEqual(S.recently_led(state), {'tfl_bikes'})

    def test_boundary_is_twenty_hours(self):
        state = {'vein_last_at': {'a': iso(hours_ago=19), 'b': iso(hours_ago=21)}}
        self.assertEqual(S.recently_led(state), {'a'})

    def test_malformed_stamp_is_not_recent(self):
        self.assertEqual(S.recently_led({'vein_last_at': {'a': 'garbage'}}), set())

    def test_select_withholds_the_vein_that_just_led(self):
        pool = mkfact('tfl_bikes', 3) + mkfact('laqn', 3)
        state = {'vein_last_at': {'tfl_bikes': iso(hours_ago=4),
                                  'laqn': iso(hours_ago=30)}}
        captured = {}

        def fake_run(cmd, **kwargs):
            captured['prompt'] = cmd[-1]
            return SelectWiring._fake_claude(None, ['laqn:0', 'laqn:1'])

        with patch('subprocess.run', side_effect=fake_run):
            sel = S.select(pool, state, history_path='/nonexistent')
        self.assertEqual(sel['vein'], 'laqn')
        self.assertNotIn('tfl_bikes:0', captured['prompt'])

    def test_abandoned_when_it_would_leave_nothing(self):
        # Only one fresh vein and it led four hours ago: post it again with
        # new numbers rather than skip, same rule as every other cooldown.
        pool = mkfact('tfl_bikes', 3)
        state = {'vein_last_at': {'tfl_bikes': iso(hours_ago=4)}}

        def fake_run(cmd, **kwargs):
            return SelectWiring._fake_claude(None, ['tfl_bikes:0', 'tfl_bikes:1'])

        with patch('subprocess.run', side_effect=fake_run):
            sel = S.select(pool, state, history_path='/nonexistent')
        self.assertEqual(sel['vein'], 'tfl_bikes')



if __name__ == '__main__':
    unittest.main()
