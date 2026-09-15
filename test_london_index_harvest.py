"""Tests for the pure card-shape builders in london_index_harvest.py, added
12 September 2026 with the crime-card shapes and four new veins. No network:
every builder here takes records already fetched and returns facts, and that
split (fetch in harvest_*, shape in *_facts) exists so these can run.

What is pinned is what could publish a wrong number quietly: the sign and
wording of a change, a ranking's order, the label a card shape puts on a
fact, and the refusals (a partial previous month, too few boroughs, a
changed flood schema) that must yield fewer facts rather than a confident
wrong one.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import london_index_harvest as H


class Months(unittest.TestCase):
    def test_shift_month_crosses_the_year(self):
        self.assertEqual(H._shift_month('2026-07', 1), '2026-06')
        self.assertEqual(H._shift_month('2026-01', 1), '2025-12')
        self.assertEqual(H._shift_month('2026-03', 14), '2025-01')

    def test_pct_change_is_signed_with_a_typographic_minus(self):
        self.assertEqual(H._pct_change(3179, 2973), '+7%')
        self.assertEqual(H._pct_change(2900, 3000), '−3%')
        self.assertEqual(H._pct_change(100, 100), '0%')
        self.assertIsNone(H._pct_change(5, 0))

    def test_pct_point_change_is_a_point_difference_not_a_relative_change(self):
        # 92% -> 96%: a +4 point move, NOT the +4.3% relative change
        # _pct_change would report for the same two numbers — the whole
        # reason this is a separate function.
        self.assertEqual(H._pct_point_change(0.96, 0.92), '+4 pts')
        self.assertEqual(H._pct_point_change(0.88, 0.92), '−4 pts')
        self.assertEqual(H._pct_point_change(0.92, 0.92), '0 pts')

    def test_category_names(self):
        self.assertEqual(H._category_name('other-theft'), 'Other theft')
        self.assertEqual(H._category_name('anti-social-behaviour'), 'Anti-social behaviour')


def recs(**cats):
    out = []
    for cat, n in cats.items():
        out += [{'category': cat}] * n
    return out


class CentralFacts(unittest.TestCase):
    URL = 'u'

    def test_shapes(self):
        now = recs(**{'other-theft': 1097, 'violent-crime': 900, 'anti-social-behaviour': 800,
                      'shoplifting': 500, 'burglary': 200})
        prev = recs(**{'other-theft': 1000, 'violent-crime': 900, 'anti-social-behaviour': 800,
                       'shoplifting': 500, 'burglary': 200})
        facts = H.central_facts(now, prev, '2026-07', self.URL)
        labels = [f['label'] for f in facts]
        self.assertEqual(labels[:3], ['Within a mile of central London',
                                      'Most common: Other theft', 'Change since June'])
        self.assertEqual(facts[0]['value'], '3,497')
        self.assertEqual(facts[2]['value'], '+3%')
        top = [f for f in facts if f['pair'] == 'central_top']
        self.assertEqual([f['label'] for f in top],
                         ['Other theft', 'Violent crime', 'Anti-social behaviour', 'Shoplifting'])
        self.assertTrue(all(f['period'] == '2026-07' for f in facts))
        self.assertTrue(all(f['dateline_lead'] == H.CENTRAL_LEAD for f in top))

    def test_no_previous_month_means_no_change_line(self):
        facts = H.central_facts(recs(**{'other-theft': 5, 'burglary': 3}), None, '2026-07', self.URL)
        self.assertNotIn('Change since June', [f['label'] for f in facts])


class BoroughFacts(unittest.TestCase):
    # The real July and June 2026 counts, 12 September 2026.
    NOW = {'Westminster': 2494, 'Camden': 3179, 'Hackney': 1904, 'Newham': 1201,
           'Croydon': 1327, 'Ealing': 751, 'Brent': 832, 'Bromley': 449}
    PREV = {'Westminster': 2327, 'Camden': 2973, 'Hackney': 1593, 'Newham': 1181,
            'Croydon': 1270, 'Ealing': 692, 'Brent': 754, 'Bromley': 410}
    CATS = {'Camden': {'violent-crime': 544, 'shoplifting': 150},
            'Croydon': {'violent-crime': 357, 'shoplifting': 212},
            'Newham': {'violent-crime': 359, 'vehicle-crime': 123},
            'Westminster': {'violent-crime': 477, 'burglary': 90}}

    def facts(self, prev=PREV):
        return H.borough_facts(self.NOW, prev, self.CATS, '2026-07', 'u')

    def by_pair(self, facts, pair):
        return [(f['label'], f['value']) for f in facts if f['pair'] == pair]

    def test_gap_is_unchanged(self):
        self.assertEqual(self.by_pair(self.facts(), 'police_gap'),
                         [('Most: Camden', '3,179'), ('Fewest: Bromley', '449')])

    def test_top_four_ranked(self):
        self.assertEqual(self.by_pair(self.facts(), 'police_top'),
                         [('Camden', '3,179'), ('Westminster', '2,494'),
                          ('Hackney', '1,904'), ('Croydon', '1,327')])

    def test_change_names_the_previous_month_and_the_movers(self):
        change = self.by_pair(self.facts(), 'police_change')
        self.assertEqual(change, [('Biggest rise since June: Hackney', '+20%'),
                                  ('Smallest rise since June: Newham', '+2%')])

    def test_a_real_fall_is_called_a_fall(self):
        prev = dict(self.PREV, Newham=1300)
        change = self.by_pair(self.facts(prev), 'police_change')
        self.assertEqual(change[1], ('Biggest fall since June: Newham', '−8%'))

    def test_no_previous_month_means_no_change_pair(self):
        self.assertEqual(self.by_pair(self.facts({}), 'police_change'), [])

    def test_type_leaders_ranked_by_count(self):
        self.assertEqual(self.by_pair(self.facts(), 'police_types_top'),
                         [('Violent crime: Camden', '544'), ('Shoplifting: Croydon', '212'),
                          ('Vehicle crime: Newham', '123'), ('Burglary: Westminster', '90')])

    def test_whole_borough_cards_carry_no_sample_qualifier(self):
        for f in self.facts():
            self.assertIsNone(f['context_note'])
            self.assertIsNone(f['dateline_lead'])
            self.assertEqual(f['period'], '2026-07')


class FloodFacts(unittest.TestCase):
    def test_warnings_and_alerts_counted_separately(self):
        items = [{'severityLevel': 2}, {'severityLevel': 3}, {'severityLevel': 3},
                 {'severityLevel': 4, 'description': 'x no longer in force'}]
        facts = H.flood_facts(items, 'u')
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Warnings in force', '1'), ('Alerts in force', '2')])
        self.assertTrue(all(f['pair'] == 'flood_gap' for f in facts))

    def test_missing_severity_level_falls_back_to_one_fact(self):
        items = [{'severity': 'Flood Alert', 'description': 'x'}]
        facts = H.flood_facts(items, 'u')
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Active flood warnings or alerts', '1')])


class StopSearchFacts(unittest.TestCase):
    def test_counts(self):
        rows = ([{'outcome': 'Arrest', 'object_of_search': 'Controlled drugs'}] * 3
                + [{'outcome': 'A no further action disposal', 'object_of_search': 'Offensive weapons'}] * 5
                + [{'outcome': 'Community resolution', 'object_of_search': 'Stolen goods'}] * 2)
        facts = H.stop_search_facts(rows, '2026-07', 'u')
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Searches', '10'), ('Ended in arrest', '3'), ('No further action', '5'),
                          ('For drugs', '3'), ('For weapons', '5')])
        self.assertTrue(all(f['pair'] == 'stops_all' and f['period'] == '2026-07' for f in facts))


class HousePriceFacts(unittest.TestCase):
    LONDON = {'averagePrice': 553870, 'percentageAnnualChange': -2.5, 'percentageChange': 1.0,
              'averagePriceFlatMaisonette': 431036, 'averagePriceDetached': 1162231}

    def boroughs(self, n=33):
        out = {}
        for i in range(n):
            out[f'B{i:02d}'] = {'averagePrice': 300000 + i * 30000,
                                'percentageAnnualChange': -10 + i}
        return out

    def test_london_lines(self):
        facts = H.house_price_facts(self.LONDON, {}, '2026-06')
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Average price, London', '£553,870'), ('Change on a year earlier', '−2.5%'),
                          ('Change on the month', '+1.0%'), ('Average flat, London', '£431,036'),
                          ('Average detached house, London', '£1,162,231')])
        self.assertEqual(facts[3]['pair'], 'hp_types_gap')

    def test_borough_shapes(self):
        facts = H.house_price_facts(self.LONDON, self.boroughs(), '2026-06')
        by = {}
        for f in facts:
            by.setdefault(f['pair'], []).append((f['label'], f['value']))
        self.assertEqual(by['hp_gap'], [('Most expensive: B32', '£1,260,000'),
                                        ('Least expensive: B00', '£300,000')])
        self.assertEqual([l for l, _ in by['hp_top']], ['B32', 'B31', 'B30', 'B29'])
        self.assertEqual(by['hp_change'], [('Biggest rise on a year earlier: B32', '+22.0%'),
                                           ('Biggest fall on a year earlier: B00', '−10.0%')])

    def test_too_few_boroughs_withholds_the_borough_shapes(self):
        facts = H.house_price_facts(self.LONDON, self.boroughs(H.HPI_MIN_BOROUGHS - 1), '2026-06')
        self.assertEqual({f['pair'] for f in facts}, {None, 'hp_types_gap'})

    def test_hpi_month_refuses_the_missing_endpoint_string(self):
        # What the API returns for a month not yet published: result is a
        # bare string, not a record. Must read as "no data", never crash.
        with unittest.mock.patch.object(H, 'get_json',
                                        return_value={'result': 'elda:missingEndpoint'}):
            self.assertIsNone(H._hpi_month('london', '2026-08'))


class RoadFacts(unittest.TestCase):
    def test_counts(self):
        items = [{'severity': 'Minimal', 'category': 'Works'}] * 4 + \
                [{'severity': 'Moderate', 'category': 'Works'}] + \
                [{'severity': 'Serious', 'category': 'Network delays'}]
        facts = H.road_facts(items)
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Disruptions on TfL roads', '6'), ('Moderate or worse', '2'),
                          ('Planned roadworks', '5')])
        self.assertTrue(all(f['period'] is None for f in facts))


class AnimalFacts(unittest.TestCase):
    def rows(self):
        mk = lambda kind, borough, cost: {'AnimalGroupParent': kind, 'Borough': borough,
                                          'IncidentNotionalCost(£)': cost}
        return ([mk('Cat', 'NEWHAM', 500)] * 5 + [mk('Bird', 'CAMDEN', 500)] * 3
                + [mk('Dog', 'NEWHAM', 1000)] * 2 + [mk('Unknown - Domestic Animal Or Pet', 'BRENT', 500)])

    def test_shapes(self):
        facts = H.animal_facts(self.rows(), '2026-07')
        self.assertEqual([(f['label'], f['value'], f['pair']) for f in facts],
                         [('Animals rescued', '11', None), ('Most rescues: Newham', '7', None),
                          ('Cats', '5', 'animals_top'), ('Birds', '3', 'animals_top'),
                          ('Dogs', '2', 'animals_top'),
                          ('Notional cost to the brigade', '£6,500', None)])

    def test_unknown_group_never_reaches_the_ranked_list(self):
        labels = [f['label'] for f in H.animal_facts(self.rows(), '2026-07') if f['pair']]
        self.assertFalse(any('Unknown' in l for l in labels))

    def test_ranked_rows_carry_a_species_emoji_and_nothing_else_does(self):
        facts = H.animal_facts(self.rows(), '2026-07')
        by_label = {f['label']: f['emoji'] for f in facts}
        self.assertEqual(by_label['Cats'], '🐈')
        self.assertEqual(by_label['Birds'], '🐦')
        self.assertEqual(by_label['Dogs'], '🐕')
        self.assertIsNone(by_label['Animals rescued'])
        self.assertIsNone(by_label['Most rescues: Newham'])
        self.assertIsNone(by_label['Notional cost to the brigade'])


class RailFacts(unittest.TestCase):
    def setUp(self):
        H._RAIL_MEMO.clear()   # the boards are memoised per process; each test fetches afresh

    def svc(self, std, etd, cancelled=False):
        return {'std': std, 'etd': etd, 'isCancelled': cancelled}

    def test_classification_from_the_board_itself(self):
        self.assertEqual(H.classify_departure(self.svc('09:00', 'On time')), 'on time')
        self.assertEqual(H.classify_departure(self.svc('09:00', '09:00')), 'on time')
        self.assertEqual(H.classify_departure(self.svc('09:00', '09:07')), 'late')
        self.assertEqual(H.classify_departure(self.svc('09:00', 'Delayed')), 'late')
        self.assertEqual(H.classify_departure(self.svc('09:00', 'Cancelled')), 'cancelled')
        self.assertEqual(H.classify_departure(self.svc('09:00', 'On time', cancelled=True)), 'cancelled')
        self.assertEqual(H.classify_departure(self.svc('09:00', 'No report')), 'other')

    def test_shapes(self):
        boards = {'Waterloo': [self.svc('09:00', 'On time')] * 5 + [self.svc('09:10', '09:15')],
                  'Euston': [self.svc('09:00', 'Cancelled')] + [self.svc('09:20', 'On time')] * 2,
                  'Moorgate': [self.svc('09:05', 'No report')],
                  'Victoria': [self.svc('09:30', 'On time')]}
        facts = H.rail_facts(boards)
        self.assertEqual([(f['label'], f['value'], f['pair']) for f in facts],
                         [('Departing within the hour', '11', 'rail_all'), ('On time', '8', 'rail_all'),
                          ('Running late', '1', 'rail_all'), ('Cancelled', '1', 'rail_all'),
                          ('Waterloo', '6', 'rail_top'), ('Euston', '3', 'rail_top'),
                          ('Moorgate', '1', 'rail_top'), ('Victoria', '1', 'rail_top')])
        self.assertTrue(all(f['period'] is None and f['context_note'] == H.RAIL_NOTE
                            and f['dateline_lead'] == H.RAIL_LEAD for f in facts))

    def test_ranked_list_never_carries_a_zero_and_needs_four_busy_stations(self):
        boards = {'St Pancras': [self.svc('01:44', 'On time')] * 2, 'Paddington': [self.svc('01:45', 'On time')],
                  'King’s Cross': [], 'Euston': [], 'Waterloo': []}
        facts = H.rail_facts(boards)
        self.assertEqual([f['pair'] for f in facts], ['rail_all'] * 4)
        boards['King’s Cross'] = [self.svc('09:00', 'On time')]
        boards['Euston'] = [self.svc('09:00', 'On time')]
        top = [(f['label'], f['value']) for f in H.rail_facts(boards) if f['pair'] == 'rail_top']
        self.assertEqual(len(top), 4)
        self.assertNotIn('0', [v for _, v in top])

    def test_ops_top_needs_three_qualifying_operators(self):
        def svc(op, etd='09:07'):
            return {'std': '09:00', 'etd': etd, 'isCancelled': False, 'operator': op}
        boards = {'Waterloo': [svc('South Western Railway')] * 3 + [svc('South Western Railway', 'On time')],
                  'Victoria': [svc('Southern')] * 2 + [svc('Southeastern', 'Cancelled')]}
        # Two operators late (Southeastern is cancelled, not late), and
        # neither clears RAIL_OPS_MIN_SERVICES: no group either way.
        self.assertEqual([f for f in H.rail_facts(boards) if f['pair'] == 'rail_ops_top'], [])
        # A third operator with a late train, but it doesn't clear the
        # service floor (1 departure) and neither do the other two (4, 2):
        # still no group — RAIL_OPS_MIN needs three QUALIFYING operators,
        # not just three with a late train somewhere.
        boards['Euston'] = [svc('Avanti West Coast', 'Delayed')]
        self.assertEqual([f for f in H.rail_facts(boards) if f['pair'] == 'rail_ops_top'], [])

    def test_ops_top_ranks_by_share_of_the_operators_own_departures(self):
        def svc(op, etd='09:07'):
            return {'std': '09:00', 'etd': etd, 'isCancelled': False, 'operator': op}
        def ontime(op):
            return {'std': '09:00', 'etd': 'On time', 'isCancelled': False, 'operator': op}
        boards = {
            # A big operator: 60 departures, 5 late -> 8%.
            'Waterloo': [svc('South Western Railway')] * 5 + [ontime('South Western Railway')] * 55,
            # A small operator: 8 departures, 3 late -> 38%. A raw-count
            # ranking would put this well behind SWR's 5; by share it
            # should lead SWR, which is the whole point of the change.
            'Paddington': [svc('Great Western Railway')] * 3 + [ontime('Great Western Railway')] * 5,
            # The worst share of the three: 5 departures, 2 late -> 40%.
            'Euston': [svc('Avanti West Coast')] * 2 + [ontime('Avanti West Coast')] * 3,
        }
        ops = [(f['label'], f['value']) for f in H.rail_facts(boards) if f['pair'] == 'rail_ops_top']
        self.assertEqual(ops, [('Avanti West Coast', '40%'), ('Great Western Railway', '38%'),
                               ('South Western Railway', '8%')])

    def test_ops_top_excludes_an_operator_below_the_service_floor(self):
        def svc(op, etd='09:07'):
            return {'std': '09:00', 'etd': etd, 'isCancelled': False, 'operator': op}
        def ontime(op):
            return {'std': '09:00', 'etd': 'On time', 'isCancelled': False, 'operator': op}
        boards = {
            'Waterloo': [svc('South Western Railway')] * 5 + [ontime('South Western Railway')] * 55,
            'Paddington': [svc('Great Western Railway')] * 3 + [ontime('Great Western Railway')] * 5,
            'Victoria': [svc('Southern')] * 2 + [ontime('Southern')] * 3,
            # Only 1 departure total: a lone late train here must not read
            # as "100% of Avanti's trains are late".
            'Euston': [svc('Avanti West Coast')],
        }
        facts = [f for f in H.rail_facts(boards) if f['pair'] == 'rail_ops_top']
        labels = [f['label'] for f in facts]
        self.assertNotIn('Avanti West Coast', labels)
        self.assertIn('Southern', labels)   # the group still forms on the other three

    def dest_svc(self, dest, std='09:00', etd='On time'):
        return {'std': std, 'etd': etd, 'isCancelled': False, 'destination': [{'locationName': dest}]}

    def test_no_destination_data_leaves_the_note_unchanged(self):
        # None of the existing tests' fixtures carry a 'destination' field
        # at all — this pins that the plain RAIL_NOTE is exactly what a
        # real board with no destination info (or this account before the
        # feature existed) would still show.
        boards = {'Waterloo': [self.svc('09:00', 'On time')] * 20}
        facts = H.rail_facts(boards)
        notes = {f['context_note'] for f in facts if f['pair'] == 'rail_all'}
        self.assertEqual(notes, {H.RAIL_NOTE})

    def test_destination_reaches_the_footnote_not_a_new_row(self):
        boards = {'Waterloo': [self.dest_svc('Woking')] * 8 + [self.dest_svc('Reading')] * 3
                             + [self.dest_svc('Basingstoke')] * 2}
        facts = H.rail_facts(boards)
        # It is prose in the existing context_note, never a fifth label —
        # his instruction, 15 September 2026 ("I do not want the
        # equivalent of a departures board").
        self.assertFalse(any('woking' in (f['label'] or '').lower() for f in facts))
        rail_all_notes = {f['context_note'] for f in facts if f['pair'] == 'rail_all'}
        self.assertEqual(len(rail_all_notes), 1)
        note = rail_all_notes.pop()
        self.assertIn('Bound for 3 different places', note)
        self.assertIn('more to Woking than anywhere else', note)
        self.assertTrue(note.startswith(H.RAIL_NOTE))

    def test_destination_tie_break_matches_station_facts_own_convention(self):
        # max() on (count, name) picks the alphabetically LAST name on a
        # tie — the exact same expression station_facts() already uses
        # for its own single-station "Most trains to" pick, so a tie
        # resolves the same way here as it does there.
        boards = {'Waterloo': [self.dest_svc('Woking')] * 5 + [self.dest_svc('Basingstoke')] * 5}
        facts = H.rail_facts(boards)
        note = next(f['context_note'] for f in facts if f['pair'] == 'rail_all')
        self.assertIn('more to Woking than anywhere else', note)

    def test_rail_top_keeps_the_plain_note_even_when_destinations_exist(self):
        boards = {'Waterloo': [self.dest_svc('Woking')] * 12, 'Euston': [self.dest_svc('Crewe')] * 10,
                  'Victoria': [self.dest_svc('Brighton')] * 8, 'Paddington': [self.dest_svc('Reading')] * 6}
        facts = H.rail_facts(boards)
        top_notes = {f['context_note'] for f in facts if f['pair'] == 'rail_top'}
        self.assertEqual(top_notes, {H.RAIL_NOTE})   # not the destination sentence

    def test_no_key_is_a_named_refusal_not_a_crash(self):
        with unittest.mock.patch.object(H, '_rdm_key', return_value=None):
            facts, err = H.harvest_rail_departures()
        self.assertEqual(facts, [])
        self.assertIn('rdm-ldbws-key', err)

    def test_quiet_boards_make_no_card(self):
        quiet = {'crs': None, 'trainServices': [self.svc('01:45', 'On time')], 'areServicesAvailable': True}
        def fake(url, headers, timeout=25):
            crs = url.split('GetDepartureBoard/')[1][:3]
            return dict(quiet, crs=crs)
        with unittest.mock.patch.object(H, '_rdm_key', return_value='k'), \
             unittest.mock.patch.object(H, 'get_json_with_headers', side_effect=fake):
            facts, err = H.harvest_rail_departures()
        self.assertEqual(facts, [])
        self.assertIn('too quiet', err)

    def test_too_few_termini_answering_refuses_the_ranking(self):
        def fake(url, headers, timeout=25):
            crs = url.split('GetDepartureBoard/')[1][:3]
            if crs in ('PAD', 'KGX', 'EUS'):
                return {'crs': crs, 'trainServices': [self.svc('09:00', 'On time')] * 30,
                        'areServicesAvailable': True}
            return None
        with unittest.mock.patch.object(H, '_rdm_key', return_value='k'), \
             unittest.mock.patch.object(H, 'get_json_with_headers', side_effect=fake):
            facts, err = H.harvest_rail_departures()
        self.assertEqual(facts, [])
        self.assertIn('termini answered', err)


import statistics  # noqa: E402  (used by RailBaseline)
import tempfile  # noqa: E402  (used by RailBaseline / RailDeparturesLogging)
import unittest.mock  # noqa: E402  (already imported above; re-stated for clarity here)
from datetime import timedelta  # noqa: E402


class RailBaseline(unittest.TestCase):
    """rail_baseline()/_log_rail_snapshot()/_rail_snapshot_rows() — the
    account's own history of past readings, added 15 September 2026 so a
    live departures card can say whether now is unusual rather than just
    stating a number with nothing to read it against. Every test here
    works against a throwaway history file, never RAIL_HISTORY_PATH's
    real one — see the dry-run-guard lesson in CLAUDE.md: a guard checked
    only at the harvest entry point does not stop a test that calls the
    lower-level functions directly, so the file itself must be swapped."""

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._history_path = Path(self._tmp_dir.name) / 'rail_history.jsonl'
        self._patch = unittest.mock.patch.object(H, 'RAIL_HISTORY_PATH', self._history_path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp_dir.cleanup()

    def test_log_then_read_round_trips(self):
        now = H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ)
        H._log_rail_snapshot(379, 362, 16, 1, now=now)
        rows = H._rail_snapshot_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['total'], 379)
        self.assertEqual(rows[0]['on_time'], 362)
        self.assertEqual(rows[0]['late'], 16)
        self.assertEqual(rows[0]['cancelled'], 1)

    def test_an_unreadable_line_is_skipped_not_fatal(self):
        self._history_path.write_text('not json\n{"ts": "bad", "total": 1}\n', encoding='utf-8')
        # The second line parses as JSON but its "ts" doesn't parse as a
        # datetime — rail_baseline must skip it too, not raise.
        self.assertIsNone(H.rail_baseline(now=H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ)))

    def test_baseline_needs_three_matching_samples(self):
        base = H.datetime(2026, 9, 1, 20, 15, tzinfo=H.LONDON_TZ)
        now = base + timedelta(days=14, hours=0, minutes=19)   # same weekday, same hour, 2 weeks on
        H._log_rail_snapshot(300, 280, 15, 5, now=base)
        self.assertIsNone(H.rail_baseline(now=now))
        H._log_rail_snapshot(320, 300, 15, 5, now=base + timedelta(days=7))
        self.assertIsNone(H.rail_baseline(now=now))   # still only 2
        H._log_rail_snapshot(340, 310, 20, 10, now=base + timedelta(days=14))
        self.assertEqual(H.rail_baseline(now=now), 320)   # median of 300, 320, 340

    def test_baseline_ignores_a_different_weekday_or_hour(self):
        now = H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ)   # a Tuesday, hour 20
        H._log_rail_snapshot(300, 280, 15, 5, now=now - timedelta(days=7))    # same weekday+hour: matches
        H._log_rail_snapshot(999, 900, 90, 9, now=now - timedelta(days=6))    # a day off: wrong weekday
        H._log_rail_snapshot(111, 100, 10, 1, now=now.replace(hour=8) - timedelta(days=7))  # right weekday, hour 8
        self.assertIsNone(H.rail_baseline(now=now))   # only one true (weekday, hour) match so far

    def test_baseline_keeps_only_the_most_recent_max_samples(self):
        now = H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ)
        # Ten matching weeks, oldest to newest, each a distinct value so the
        # median identifies exactly which eight were kept.
        for i in range(10, 0, -1):
            H._log_rail_snapshot(100 + i, 90, 5, 1, now=now - timedelta(weeks=i))
        rows = H._rail_snapshot_rows()
        self.assertEqual(len(rows), 10)
        # Only the 8 most recent (i=8..1, values 108..101) should count;
        # the two oldest (i=10, i=9 -> 110, 109) must be dropped.
        self.assertEqual(H.rail_baseline(now=now), statistics.median(range(101, 109)))

    def test_on_time_share_needs_three_matching_samples(self):
        now = H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ)
        H._log_rail_snapshot(300, 276, 20, 4, now=now - timedelta(weeks=1))   # 92%
        self.assertIsNone(H.rail_baseline_on_time_share(now=now))
        H._log_rail_snapshot(300, 270, 25, 5, now=now - timedelta(weeks=2))   # 90%
        self.assertIsNone(H.rail_baseline_on_time_share(now=now))   # still only 2
        H._log_rail_snapshot(300, 288, 10, 2, now=now - timedelta(weeks=3))   # 96%
        self.assertAlmostEqual(H.rail_baseline_on_time_share(now=now), 0.92)   # median of .92,.90,.96

    def test_on_time_share_is_the_median_of_each_readings_own_share(self):
        # A big quiet reading and a small busy one must not let one side of
        # the fraction (total or on_time) dominate the other's median the
        # way a "median of totals / median of on-times" shortcut would.
        now = H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ)
        H._log_rail_snapshot(500, 100, 390, 10, now=now - timedelta(weeks=1))   # 20% on time, huge total
        H._log_rail_snapshot(10, 9, 1, 0, now=now - timedelta(weeks=2))         # 90% on time, tiny total
        H._log_rail_snapshot(50, 45, 5, 0, now=now - timedelta(weeks=3))        # 90% on time
        # Median of the three SHARES (0.2, 0.9, 0.9) is 0.9 — not the ratio
        # of median-total (50) to median-on-time (45), which would also be
        # 0.9 here by coincidence, so this fixture alone wouldn't catch a
        # ratio-of-medians bug; the assertion is on the actual value used.
        self.assertAlmostEqual(H.rail_baseline_on_time_share(now=now), 0.9)

    def test_on_time_share_ignores_a_different_weekday_or_hour(self):
        now = H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ)   # a Tuesday, hour 20
        H._log_rail_snapshot(300, 276, 20, 4, now=now - timedelta(days=7))    # matches
        H._log_rail_snapshot(300, 100, 190, 10, now=now - timedelta(days=6))  # wrong weekday
        self.assertIsNone(H.rail_baseline_on_time_share(now=now))   # only one true match so far

    def test_on_time_share_skips_a_zero_total_reading(self):
        now = H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ)
        H._log_rail_snapshot(300, 276, 20, 4, now=now - timedelta(weeks=1))
        H._log_rail_snapshot(300, 270, 25, 5, now=now - timedelta(weeks=2))
        H._log_rail_snapshot(0, 0, 0, 0, now=now - timedelta(weeks=3))   # would ZeroDivisionError if not skipped
        self.assertIsNone(H.rail_baseline_on_time_share(now=now))   # only 2 usable readings


class RailBaselineFact(unittest.TestCase):
    """The "Change from a typical <weekday>" facts rail_facts() adds when
    given baseline_total and/or baseline_on_time_share — pure functions of
    what they're handed, so these tests need no history file at all."""

    def svc(self, std, etd):
        return {'std': std, 'etd': etd, 'isCancelled': False}

    def test_no_baseline_given_means_no_such_fact(self):
        boards = {'Waterloo': [self.svc('09:00', 'On time')] * 25}
        facts = H.rail_facts(boards)
        self.assertFalse(any('typical' in f['label'].lower() for f in facts))

    def test_departures_baseline_fact_is_a_signed_pct_change_naming_the_weekday(self):
        boards = {'Waterloo': [self.svc('09:00', 'On time')] * 25}
        now = H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ)   # a Tuesday
        facts = H.rail_facts(boards, baseline_total=20, now=now)
        matches = [f for f in facts if 'typical' in f['label'].lower()]
        self.assertEqual(len(matches), 1)
        baseline_fact = matches[0]
        self.assertEqual(baseline_fact['value'], '+25%')
        self.assertIn('Tuesday', baseline_fact['label'])
        self.assertEqual(baseline_fact['pair'], 'rail_all')

    def test_a_zero_baseline_adds_no_fact_rather_than_dividing_by_zero(self):
        boards = {'Waterloo': [self.svc('09:00', 'On time')] * 25}
        facts = H.rail_facts(boards, baseline_total=0, now=H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ))
        self.assertFalse(any('typical' in f['label'].lower() for f in facts))

    def test_on_time_share_baseline_fact_is_a_signed_point_change(self):
        # 25 on time of 25 total = 100% on time now; a typical 92% means a
        # +8-point move, not _pct_change()'s +9% relative reading.
        boards = {'Waterloo': [self.svc('09:00', 'On time')] * 25}
        now = H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ)   # a Tuesday
        facts = H.rail_facts(boards, baseline_on_time_share=0.92, now=now)
        matches = [f for f in facts if 'typical' in f['label'].lower()]
        self.assertEqual(len(matches), 1)
        baseline_fact = matches[0]
        self.assertEqual(baseline_fact['value'], '+8 pts')
        self.assertIn('On time', baseline_fact['label'])
        self.assertIn('Tuesday', baseline_fact['label'])
        self.assertEqual(baseline_fact['pair'], 'rail_all')

    def test_both_baselines_can_appear_together_and_read_distinctly(self):
        boards = {'Waterloo': [self.svc('09:00', 'On time')] * 20 + [self.svc('09:00', '09:07')] * 5}
        now = H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ)
        facts = H.rail_facts(boards, baseline_total=20, baseline_on_time_share=0.7, now=now)
        matches = {f['label']: f['value'] for f in facts if 'typical' in f['label'].lower()}
        self.assertEqual(len(matches), 2)
        self.assertTrue(any(v.endswith('%') for v in matches.values()))
        self.assertTrue(any(v.endswith('pts') for v in matches.values()))

    def test_on_time_share_baseline_is_ignored_on_an_empty_board(self):
        # total == 0: dividing counts['on time'] / total must not crash.
        facts = H.rail_facts({}, baseline_on_time_share=0.9,
                             now=H.datetime(2026, 9, 15, 20, 34, tzinfo=H.LONDON_TZ))
        self.assertFalse(any('typical' in f['label'].lower() for f in facts))


class RailDeparturesLogging(unittest.TestCase):
    """harvest_rail_departures() logs exactly one snapshot on a full-
    coverage run and none on a partial one — see _log_rail_snapshot's own
    note on why a partial read must not become a baseline sample."""

    def setUp(self):
        H._RAIL_MEMO.clear()
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._history_path = Path(self._tmp_dir.name) / 'rail_history.jsonl'
        self._patch = unittest.mock.patch.object(H, 'RAIL_HISTORY_PATH', self._history_path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp_dir.cleanup()
        H._RAIL_MEMO.clear()

    def _board(self, crs, n=25):
        return {'crs': crs, 'areServicesAvailable': True,
                'trainServices': [{'std': '09:00', 'etd': 'On time'}] * n}

    def test_a_full_coverage_run_logs_exactly_one_snapshot(self):
        def fake(url, headers, timeout=25):
            crs = url.split('GetDepartureBoard/')[1][:3]
            return self._board(crs)
        with unittest.mock.patch.object(H, '_rdm_key', return_value='k'), \
             unittest.mock.patch.object(H, 'get_json_with_headers', side_effect=fake):
            facts, err = H.harvest_rail_departures()
        self.assertIsNone(err)
        rows = H._rail_snapshot_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['total'], 25 * len(H.RAIL_TERMINI))

    def test_a_partial_run_is_not_logged(self):
        crs_list = list(H.RAIL_TERMINI.values())
        def fake(url, headers, timeout=25):
            crs = url.split('GetDepartureBoard/')[1][:3]
            if crs == crs_list[0]:
                return {'crs': crs, 'areServicesAvailable': False, 'trainServices': []}
            return self._board(crs)
        with unittest.mock.patch.object(H, '_rdm_key', return_value='k'), \
             unittest.mock.patch.object(H, 'get_json_with_headers', side_effect=fake):
            facts, err = H.harvest_rail_departures()
        self.assertIsNone(err)   # still a card: RAIL_MIN_STATIONS allows one failure
        self.assertEqual(H._rail_snapshot_rows(), [])


class Spotlight(unittest.TestCase):
    def test_thirty_three_boroughs_all_inside_greater_london(self):
        self.assertEqual(len(H.ALL_BOROUGHS), 33)
        for name, (lat, lon) in H.ALL_BOROUGHS.items():
            self.assertTrue(51.28 < lat < 51.70 and -0.52 < lon < 0.34, name)
        self.assertTrue(set(H.POLICE_BOROUGHS) <= set(H.ALL_BOROUGHS))

    def test_ordinals(self):
        self.assertEqual([H._ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 33)],
                         ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '33rd'])

    def test_pick_never_featured_first_then_longest_ago_then_alphabetical(self):
        last = {'Camden': '2026-09-10 12:00:00', 'Brent': '2026-09-01 12:00:00'}
        self.assertEqual(H.spotlight_pick(['Camden', 'Brent', 'Sutton', 'Bexley'], last), 'Bexley')
        self.assertEqual(H.spotlight_pick(['Camden', 'Brent'], last), 'Brent')

    def test_last_featured_reads_spotlight_openers_only(self):
        import json, tempfile
        fh = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
        for at, opener in (('2026-09-01 08:00:00', 'Reported crime in Sutton'),
                           ('2026-09-03 08:00:00', 'Reported crime in Sutton'),
                           ('2026-09-02 08:00:00', 'Reported crime'),
                           ('2026-09-02 09:00:00', 'Reported crime in Narnia')):
            fh.write(json.dumps({'at': at, 'opener': opener, 'lines': []}) + '\n')
        fh.close()
        self.addCleanup(Path(fh.name).unlink)
        self.assertEqual(H.spotlight_last_featured(fh.name), {'Sutton': '2026-09-03 08:00:00'})

    def test_facts(self):
        cats = {'violent-crime': 359, 'vehicle-crime': 123}
        counts = {f'B{i}': 100 * i for i in range(1, 33)}
        counts['Newham'] = 482
        facts = H.spotlight_facts('Newham', 482, cats, 400, counts, '2026-07', 'u')
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Reported crimes', '482'), ('Most common: Violent crime', '359'),
                          ('Change since June', '+20%'), ('Rank among boroughs', '29th highest of 33')])
        for f in facts:
            self.assertEqual(f['fixed_opener'], {'emoji': '🚓', 'text': 'Reported crime in Newham'})
            self.assertEqual(f['dateline_lead'], H.SPOTLIGHT_LEAD)
            self.assertEqual(f['pair'], 'spot_all')

    def test_no_rank_when_too_few_boroughs_answered(self):
        facts = H.spotlight_facts('Bexley', 5, {'burglary': 5}, None, {'Bexley': 5, 'Brent': 9}, '2026-07', 'u')
        self.assertEqual([f['label'] for f in facts], ['Reported crimes', 'Most common: Burglary'])


class HousePriceSpotlight(unittest.TestCase):
    """The choropleth's second vein: same rotation/rank shape as Spotlight
    above, over house_prices' own HPI_BOROUGHS instead of crime counts."""

    def _boroughs(self, prices):
        return {name: {'averagePrice': price} for name, price in prices.items()}

    def test_facts(self):
        # Same numeric shape as Spotlight.test_facts above (32 evenly-spaced
        # values plus one deliberate insert), so the expected rank is
        # checkable by the same reasoning: 28 of the 32 B-names exceed
        # 482,000, so Newham is 29th of 33.
        prices = {f'B{i}': 100_000 * i for i in range(1, 33)}
        prices['Newham'] = 482_000
        boroughs = self._boroughs(prices)
        boroughs['Newham']['percentageAnnualChange'] = 7.3
        boroughs['Newham']['percentageChange'] = -0.4
        facts = H.house_price_spotlight_facts('Newham', boroughs, '2026-07')
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Average price', '£482,000'), ('Change on a year earlier', '+7.3%'),
                          ('Change on the month', '−0.4%'), ('Rank among boroughs', '29th highest of 33')])
        for f in facts:
            self.assertEqual(f['fixed_opener'], {'emoji': '🏠', 'text': 'House prices in Newham'})
            self.assertIsNone(f['dateline_lead'])
            self.assertEqual(f['pair'], 'hp_spot')
            self.assertEqual(f['map_pin']['name'], 'Newham')
            self.assertEqual(len(f['map_pin']['ranks']), 33)
            self.assertEqual(f['map_pin']['ranks']['Newham'], 482_000)

    def test_no_rank_or_map_ranks_when_too_few_boroughs_answered(self):
        boroughs = self._boroughs({'Bexley': 400_000, 'Brent': 450_000})
        facts = H.house_price_spotlight_facts('Bexley', boroughs, '2026-07')
        self.assertEqual([f['label'] for f in facts], ['Average price'])
        self.assertEqual(facts[0]['map_pin'], {'name': 'Bexley', 'lat': None, 'lng': None})

    def test_hp_spotlight_last_featured_reads_its_own_openers_only(self):
        import json, tempfile
        fh = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
        for at, opener in (('2026-09-01 08:00:00', 'House prices in Sutton'),
                           ('2026-09-03 08:00:00', 'House prices in Sutton'),
                           ('2026-09-02 08:00:00', 'Reported crime in Sutton'),
                           ('2026-09-02 09:00:00', 'House prices in Narnia')):
            fh.write(json.dumps({'at': at, 'opener': opener, 'lines': []}) + '\n')
        fh.close()
        self.addCleanup(Path(fh.name).unlink)
        self.assertEqual(H.hp_spotlight_last_featured(fh.name), {'Sutton': '2026-09-03 08:00:00'})

    def test_hpi_boroughs_matches_the_boundary_file_exactly(self):
        # Same guarantee test_boundary_file_names_match_the_harvester_exactly
        # gives ALL_BOROUGHS: render_borough_map() raises CardRenderError
        # for a name the boundary file does not carry, so a mismatch here
        # would fail every picked borough's map, not just some.
        self.assertEqual(set(H.HPI_BOROUGHS), set(H.ALL_BOROUGHS))

    def test_registered_in_the_dispatch_table(self):
        self.assertIs(H.HARVESTERS['house_price_spotlight'], H.harvest_house_price_spotlight)


class BoroughMap(unittest.TestCase):
    def test_boundary_file_names_match_the_harvester_exactly(self):
        import london_index_card as card
        b = card.load_boroughs()
        self.assertEqual(set(b), set(H.ALL_BOROUGHS))
        self.assertEqual(len(b), 33)
        for name, rings in b.items():
            self.assertTrue(rings and all(len(r) >= 4 for r in rings), name)

    def test_every_town_hall_lies_inside_its_own_borough_outline(self):
        # Ray casting against the outer rings; a coordinate that fails is a
        # geocode that landed in the wrong borough (the Reading/Boveney Lock
        # lesson from the river gauges), not a rounding error.
        import london_index_card as card
        b = card.load_boroughs()

        def inside(pt, ring):
            x, y = pt
            hit = False
            for i in range(len(ring)):
                x1, y1 = ring[i - 1]
                x2, y2 = ring[i]
                if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                    hit = not hit
            return hit
        for name, (lat, lng) in H.ALL_BOROUGHS.items():
            self.assertTrue(any(inside((lng, lat), r) for r in b[name]), name)

    def test_unknown_borough_refuses_to_draw(self):
        import london_index_card as card
        with self.assertRaises(card.CardRenderError):
            card.render_borough_map('Narnia', (51.5, -0.1), '/tmp/x.png', boroughs={'A': [[(0, 0), (1, 0), (1, 1), (0, 1)]]})

    def test_spotlight_facts_carry_the_pin_without_coordinates(self):
        facts = H.spotlight_facts('Sutton', 3, {'burglary': 3}, None, {}, '2026-07', 'u')
        self.assertTrue(all(f['map_pin'] == {'name': 'Sutton', 'lat': None, 'lng': None} for f in facts))

    def test_outer_rings_cover_all_33(self):
        import london_index_card as card
        outers = card.load_borough_outers()
        self.assertEqual(set(outers), set(H.ALL_BOROUGHS))
        self.assertTrue(all(len(rings) >= 1 and all(len(r) >= 4 for r in rings) for rings in outers.values()))

    def test_compose_passes_the_pin_through(self):
        import london_index_compose as C
        facts = H.spotlight_facts('Sutton', 3, {'burglary': 3}, None, {}, '2026-07', 'u')
        for i, f in enumerate(facts):
            f['id'] = f'x:{i}'
            f['vein'] = 'police_spotlight'
        c = C.compose({'opener': facts[0]['fixed_opener'], 'ids': [f['id'] for f in facts]}, facts)
        self.assertEqual(c['map_pin']['name'], 'Sutton')
        plain = H.central_facts([{'category': 'burglary'}] * 3, None, '2026-07', 'u')[:2]
        for i, f in enumerate(plain):
            f['id'] = f'y:{i}'
            f['vein'] = 'police'
        self.assertIsNone(C.compose({'opener': {'emoji': '', 'text': 'T'}, 'ids': [f['id'] for f in plain]}, plain)['map_pin'])

    def test_compose_passes_the_animal_emoji_through_and_omits_it_elsewhere(self):
        import london_index_compose as C
        rows = [{'AnimalGroupParent': 'Cat', 'Borough': 'NEWHAM', 'IncidentNotionalCost(£)': 500}] * 5 \
            + [{'AnimalGroupParent': 'Bird', 'Borough': 'CAMDEN', 'IncidentNotionalCost(£)': 500}] * 3 \
            + [{'AnimalGroupParent': 'Dog', 'Borough': 'NEWHAM', 'IncidentNotionalCost(£)': 1000}] * 2
        facts = H.animal_facts(rows, '2026-07')
        for i, f in enumerate(facts):
            f['id'] = f'z:{i}'
            f['vein'] = 'lfb_animals'
        by_label_all = {f['label']: f for f in facts}
        # Under MAX_LINES=4: the ranked trio plus the unranked total, so both
        # sides of the rule (a ranked row carries the icon, the total does not)
        # are exercised in one compose() call.
        ids = [by_label_all['Animals rescued']['id'], by_label_all['Cats']['id'],
               by_label_all['Birds']['id'], by_label_all['Dogs']['id']]
        c = C.compose({'opener': {'emoji': '🚒', 'text': 'T'}, 'ids': ids}, facts)
        by_label = {l['label']: l.get('emoji') for l in c['lines']}
        self.assertEqual(by_label['Cats'], '🐈')
        self.assertEqual(by_label['Birds'], '🐦')
        self.assertEqual(by_label['Dogs'], '🐕')
        total_line = next(l for l in c['lines'] if l['label'] == 'Animals rescued')
        self.assertNotIn('emoji', total_line)


class WholeBoroughCache(unittest.TestCase):
    def test_fetches_only_what_the_cache_lacks_and_never_caches_a_failure(self):
        import json, tempfile
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'c.json'
            path.write_text(json.dumps({'2026-07': {'Camden': {'total': 5, 'categories': {'x': 5}}}}))
            calls = []

            def fake(name, ym, outers):
                calls.append(name)
                return None if name == 'Bexley' else {'total': 1, 'categories': {'y': 1}}
            out = H.whole_borough_counts('2026-07', names=['Camden', 'Bexley', 'Sutton'],
                                         cache_path=path, fetch=fake)
            self.assertEqual(sorted(calls), ['Bexley', 'Sutton'])
            self.assertEqual(set(out), {'Camden', 'Sutton'})
            cached = json.loads(path.read_text())['2026-07']
            self.assertIn('Sutton', cached)
            self.assertNotIn('Bexley', cached)

    def test_a_failed_ring_fails_the_borough(self):
        with unittest.mock.patch.object(H, '_poly_post', side_effect=[[{'category': 'a'}] * 3, None]):
            self.assertIsNone(H.borough_month_whole('X', '2026-07', [[(0, 0)] * 4, [(1, 1)] * 4]))
        with unittest.mock.patch.object(H, '_poly_post', side_effect=[[{'category': 'a'}] * 3, [{'category': 'b'}]]):
            self.assertEqual(H.borough_month_whole('X', '2026-07', [[(0, 0)] * 4, [(1, 1)] * 4]),
                             {'total': 4, 'categories': {'a': 3, 'b': 1}})


class StationAndGaugeSpotlights(unittest.TestCase):
    def setUp(self):
        H._RAIL_MEMO.clear()
        H._RIVER_MEMO.clear()

    def svc(self, etd, dest, op='X'):
        return {'std': '09:00', 'etd': etd, 'isCancelled': False, 'operator': op,
                'destination': [{'locationName': dest}]}

    def test_station_facts(self):
        services = [self.svc('On time', 'Reading')] * 5 + [self.svc('09:09', 'Reading')] + \
                   [self.svc('Cancelled', 'Oxford')] + [self.svc('On time', 'Bristol Temple Meads')] * 2
        facts = H.station_facts('Paddington', services)
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Departing within the hour', '9'), ('On time', '7'), ('Running late', '1'),
                          ('Cancelled', '1'), ('Most trains to: Reading', '6')])
        for f in facts:
            self.assertEqual(f['fixed_opener'], {'emoji': '🚆', 'text': 'Trains from Paddington'})
            self.assertEqual(f['pair'], 'station_all')
            self.assertIsNone(f['period'])

    def test_station_rotation_ignores_the_network_card_opener(self):
        import json, tempfile
        fh = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
        for at, opener in (('2026-09-12 08:00:00', 'Trains from London’s stations'),
                           ('2026-09-12 09:00:00', 'Trains from Waterloo')):
            fh.write(json.dumps({'at': at, 'opener': opener, 'lines': []}) + '\n')
        fh.close()
        self.addCleanup(Path(fh.name).unlink)
        self.assertEqual(H.last_featured(H.STATION_OPENER_PREFIX, H.RAIL_TERMINI, fh.name),
                         {'Waterloo': '2026-09-12 09:00:00'})

    def test_quiet_stations_are_not_candidates(self):
        boards = {n: [] for n in H.RAIL_TERMINI}
        boards['Waterloo'] = [self.svc('On time', 'Woking')] * H.STATION_MIN_DEPARTURES
        boards['Euston'] = [self.svc('On time', 'Watford Junction')] * 3
        with unittest.mock.patch.object(H, '_rail_boards', return_value=(boards, [], None)), \
             unittest.mock.patch.object(H, 'last_featured', return_value={}):
            facts, err = H.harvest_rail_station()
        self.assertIsNone(err)
        self.assertEqual(facts[0]['fixed_opener']['text'], 'Trains from Waterloo')
        boards['Waterloo'] = boards['Waterloo'][:3]
        with unittest.mock.patch.object(H, '_rail_boards', return_value=(boards, [], None)):
            facts, err = H.harvest_rail_station()
        self.assertEqual(facts, [])
        self.assertIn('too quiet', err)

    def test_gauge_facts(self):
        facts = H.gauge_facts(('Thames at Kingston', 4.312, 3.9, 4.6, 58.857, 'when'), 'u')
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Level now', '4.31m'), ('Typical low', '3.90m'), ('Typical high', '4.60m'),
                          ('Where it sits', '59% of the way up')])
        self.assertEqual(facts[0]['fixed_opener']['text'], 'The Thames at Kingston')
        self.assertEqual(H.gauge_facts(('X', 5.0, 3.0, 4.0, 200.0, 'w'), 'u')[3]['value'], 'above its range')
        self.assertEqual(H.gauge_facts(('X', 1.0, 3.0, 4.0, -200.0, 'w'), 'u')[3]['value'], 'below its range')

    def test_gauge_rotation_picks_least_recent_gauge(self):
        readings = [(n, 1.0, 0.5, 2.0, 33.3, 'w') for n in H.RIVER_STATIONS]
        with unittest.mock.patch.object(H, '_river_readings', return_value=(readings, [])), \
             unittest.mock.patch.object(H, 'last_featured', return_value={n: '2026-09-01' for n in list(H.RIVER_STATIONS)[1:]}):
            facts, err = H.harvest_river_gauge()
        self.assertIsNone(err)
        self.assertEqual(facts[0]['fixed_opener']['text'], 'The ' + list(H.RIVER_STATIONS)[0])


class DatastoreSeries(unittest.TestCase):
    """The seven Datastore builders, each on rows shaped like the real file's
    header (read on 12 September 2026), plus the refusals on a changed
    header, which must raise rather than build a card of zeros."""

    def test_reservoirs(self):
        rows = [['date', 'month', 'year', ' lower_lee_group ', ' lower_thames_group ']]
        for y in range(1989, 2027):
            rows.append([f'31-Aug-{str(y)[2:]}', 'Aug', str(y), '80', '70' if y < 2026 else '59'])
        rows.append(['30-Aug-26', 'Aug', '2026', '69', '60'])
        facts = H.reservoir_facts(rows)
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Lower Thames group', '59%'), ('Lower Lee group', '80%'),
                          ('Thames group, on a year earlier', '−11 points'),
                          ('Thames group, average for the date since 1989', '70%')])
        self.assertTrue(all(f['period'] == '2026-08-31' and f['pair'] == 'reservoir_all' for f in facts))
        with self.assertRaises(ValueError):
            H.reservoir_facts([['Date', 'Level']])

    def test_journeys(self):
        header = ['Period and Financial year', 'Reporting Period', 'Days in period', 'Period beginning',
                  'Period ending', 'Bus journeys (m)', 'Underground journeys (m)', 'DLR Journeys (m)',
                  'Tram Journeys (m)', 'Overground Journeys (m)', 'London Cable Car Journeys (m)', 'TfL Rail Journeys (m)']
        rows = [header]
        for i in range(14):
            rows.append(['', str(i), '28', '01-Jan-25', f'{(i % 28) + 1:02d}-Jan-25', '100', '80', '5', '1', '10', '0.1', '15'])
        rows.append(['', '4', '28', '28-Jun-26', '25-Jul-26', '134.8', '97.3', '7.1', '1.7', '14.0', '0.1', '19.7'])
        facts = H.journey_facts(rows)
        self.assertEqual(facts[0]['label'], 'All modes')
        self.assertEqual(facts[0]['value'], '274.7 million')
        self.assertEqual(facts[0]['dateline_text'], 'Four weeks, 28 June to 25 July 2026')
        self.assertEqual(facts[1]['label'], 'Change on the same period a year earlier')
        self.assertEqual([(f['label'], f['value']) for f in facts if f['pair'] == 'journeys_top'],
                         [('Bus', '134.8 million'), ('Underground', '97.3 million'),
                          ('Elizabeth line', '19.7 million'), ('Overground', '14.0 million')])

    def test_congestion(self):
        rows = [['Month', 'CC Camera Captures during Charging Hours', 'CC Confirmed Vehicles observed during Charging Hours', 'Number of Charging Day in Month', 'Notes'],
                ['Jul-25', '2900000', '2500000', '31', ''], ['Jul-26', '2783502', '2359567', '31', '']]
        facts = H.congestion_facts(rows)
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Vehicles seen in charging hours', '2,359,567'), ('Per charging day', '76,115'),
                          ('Charging days', '31'), ('Change on a year earlier', '−6%')])
        self.assertTrue(all(f['period'] == '2026-07' for f in facts))

    def test_strength(self):
        rows = [['Date', 'Police Officer Strength', 'Police Staff Strength', 'PCSO Strength'],
                ['Jul-25', '32000', '11000', '1400'], ['Jul-26', '31011', '11522', '1366']]
        facts = H.strength_facts(rows)
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Police officers', '31,011'), ('Civilian staff', '11,522'),
                          ('Community support officers', '1,366'), ('Officers, change on a year earlier', '−3%')])

    def test_arrests(self):
        header = ('Arrest Year', 'Arrest Month', 'Arrest Month Name', 'Gender', 'Age Group', 'Ethnicity (4+1)',
                  'First Arrest Offence', 'Domestic Abuse Flag', 'Arrest Count')
        rows = [header,
                (2025, 8, 'August', 'Male', 'Adult', 'White', 'Assault', 'No', 1000),
                (2026, 8, 'August', 'Male', 'Adult', 'White', 'Assault', 'No', 600),
                (2026, 8, 'August', 'Female', 'Adult', 'White', 'Assault', 'Yes', 300),
                (2026, 8, 'August', 'Male', 'Adult', 'Black', 'Drugs', 'No', 200),
                (2026, 8, 'August', 'Male', 'Adult', 'White', 'Other Offence', 'No', 5000)]
        facts = H.arrests_facts(rows)
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Arrests', '6,100'), ('Most common offence: Assault', '900'),
                          ('Flagged as domestic abuse', '300'), ('Change on a year earlier', '+510%')])
        self.assertTrue(all(f['period'] == '2026-08' for f in facts))

    def test_unemployment(self):
        rows = [(None, 'London', None, None, 'UK'), ('All Persons', 'Unemployed', 'rate', None, 'Unemployed', 'rate')]
        for i in range(14):
            rows.append((f'Mar-May {2025 + i // 12}', 300000.0, 6.0, None, 1700000.0, 4.5))
        rows.append(('Apr-Jun 2026', 338918.1, 6.51, None, 1772269.6, 4.89))
        facts = H.unemployment_facts(rows)
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('London rate', '6.5%'), ('U.K. rate', '4.9%'),
                          ('Londoners unemployed', '339,000'), ('London rate, on a year earlier', '+0.5 points')])
        self.assertEqual(facts[0]['dateline_text'], 'April to June 2026')
        self.assertEqual(facts[0]['period'], '2026-06')

    def test_lifts(self):
        rows = [{'Borough': 'BRENT'}] * 6 + [{'Borough': 'HACKNEY'}] * 4
        facts = H.lifts_facts(rows, '2026-07', prev_rows=[{}] * 8)
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Callouts', '10'), ('Per day', '0.3'),
                          ('Most: Brent', '6'), ('Change on a year earlier', '+25%')])

    def test_dateline_text_reaches_the_card(self):
        import london_index_compose as C
        facts = [H.fact('1', 'a', 's', 'u', period='2026-07-25', dateline_text='Four weeks, 28 June to 25 July 2026'),
                 H.fact('2', 'b', 's', 'u', period='2026-07-25', dateline_text='Four weeks, 28 June to 25 July 2026')]
        for i, f in enumerate(facts):
            f['id'] = f'x:{i}'; f['vein'] = 'x'
        c = C.compose({'opener': {'emoji': '', 'text': 'T'}, 'ids': ['x:0', 'x:1']}, facts)
        self.assertEqual(c['dateline'], 'Four weeks, 28 June to 25 July 2026')
        # The footnote says the period is the newest published, TfL's
        # four-week span turned round into a sentence (12 September 2026).
        self.assertEqual(c['footnote'],
                         'the four weeks to 25 July 2026 is the latest period for which data is available')


class LatestNote(unittest.TestCase):
    """Every dated card's footnote ends by naming its period as the newest
    published, his call, 12 September 2026; a live card says nothing."""

    def compose(self, facts):
        import london_index_compose as C
        for i, f in enumerate(facts):
            f['id'] = f'x:{i}'
            f['vein'] = 'x'
        return C.compose({'opener': {'emoji': '', 'text': 'T'}, 'ids': [f['id'] for f in facts]}, facts)

    def test_a_month_a_year_and_a_day_each_name_their_own_unit(self):
        # Each period here is more than one degree removed from today (13
        # September 2026), so the sentence shows; see LatestNoteFreshness
        # for the boundary itself.
        month = [H.fact('1', 'a', 's', 'u', period='2026-06'), H.fact('2', 'b', 's', 'u', period='2026-06')]
        self.assertEqual(self.compose(month)['footnote'],
                         'June 2026 is the latest month for which data is available')
        year = [H.fact('1', 'a', 's', 'u', period='2024'), H.fact('2', 'b', 's', 'u', period='2024')]
        self.assertEqual(self.compose(year)['footnote'],
                         '2024 is the latest year for which data is available')
        day = [H.fact('1', 'a', 's', 'u', period='2026-09-03'), H.fact('2', 'b', 's', 'u', period='2026-09-03')]
        self.assertEqual(self.compose(day)['footnote'],
                         '3 September 2026 is the latest date for which data is available')

    def test_a_financial_year_names_itself_a_year_not_a_month(self):
        # museum_facts's own shape ('2024-25'), 7 characters like 'YYYY-MM'
        # -- caught calling the British Museum's 2024-25 figures "the
        # latest month for which data is available" in a live post, 14
        # September 2026, because the unit was picked from len(p) alone.
        fy = [H.fact('1', 'a', 's', 'u', period='2024-25'), H.fact('2', 'b', 's', 'u', period='2024-25')]
        self.assertEqual(self.compose(fy)['footnote'],
                         '2024-25 is the latest year for which data is available')

    def test_it_follows_the_context_note_after_a_middle_dot(self):
        # Footnotes here carry no full stop (MUSEUM_NOTE_GROUP), so the two
        # parts meet on a middle dot, Seoul Index's busmovers arrangement.
        facts = [H.fact('1', 'a', 's', 'u', period='2026-07', context_note='Counted by the Met'),
                 H.fact('2', 'b', 's', 'u', period='2026-07', context_note='Counted by the Met')]
        self.assertEqual(self.compose(facts)['footnote'],
                         'Counted by the Met · July 2026 is the latest month for which data is available')

    def test_a_live_card_and_a_mixed_card_say_nothing(self):
        live = [H.fact('1', 'a', 's', 'u'), H.fact('2', 'b', 's', 'u')]
        self.assertEqual(self.compose(live)['footnote'], '')
        mixed = [H.fact('1', 'a', 's', 'u', period='2026-06'), H.fact('2', 'b', 's', 'u', period='2026-07')]
        self.assertEqual(self.compose(mixed)['footnote'], '')

    def test_a_spelled_out_period_is_restated_as_it_stands(self):
        facts = [H.fact('1', 'a', 's', 'u', period='2026-07', dateline_text='May to July 2026'),
                 H.fact('2', 'b', 's', 'u', period='2026-07', dateline_text='May to July 2026')]
        self.assertEqual(self.compose(facts)['footnote'],
                         'May to July 2026 is the latest period for which data is available')


class LatestNoteFreshness(unittest.TestCase):
    """_is_stale()/_latest_note(): the sentence is dropped when a period is
    no more than one degree removed from today's own, necessarily-
    incomplete day/month/year, his call, 13 September 2026 -- Seoul
    Index's identical narrowing (see LatestNoteFreshness there), applied
    here too since the sentence is the same one, worded from the same
    _latest_note(). Pinned against an injected `now` rather than the real
    calendar, exactly for the reason Seoul Index's test class gives."""

    def setUp(self):
        import london_index_compose as C
        self.C = C
        self.now = C.date(2026, 9, 13)

    def compose(self, facts):
        for i, f in enumerate(facts):
            f['id'] = f'x:{i}'
            f['vein'] = 'x'
        return self.C.compose({'opener': {'emoji': '', 'text': 'T'}, 'ids': [f['id'] for f in facts]}, facts)

    def test_a_date_is_stale_only_when_more_than_a_day_behind(self):
        self.assertFalse(self.C._is_stale('2026-09-13', self.now))  # today
        self.assertFalse(self.C._is_stale('2026-09-12', self.now))  # yesterday
        self.assertTrue(self.C._is_stale('2026-09-11', self.now))   # two days back

    def test_a_month_is_stale_only_when_more_than_a_calendar_month_behind(self):
        self.assertFalse(self.C._is_stale('2026-08', self.now))   # last month
        self.assertTrue(self.C._is_stale('2026-07', self.now))    # two months back

    def test_a_year_is_stale_only_when_more_than_a_calendar_year_behind(self):
        self.assertFalse(self.C._is_stale('2025', self.now))   # last year
        self.assertTrue(self.C._is_stale('2024', self.now))    # two years back

    def test_an_unrecognised_shape_is_treated_as_stale(self):
        self.assertTrue(self.C._is_stale('not-a-period', self.now))
        self.assertTrue(self.C._is_stale('2026-13-40', self.now))   # not a real date

    def test_the_sentence_is_dropped_for_a_fresh_period_on_a_real_card(self):
        fresh = [H.fact('1', 'a', 's', 'u', period='2026-09-12'),
                 H.fact('2', 'b', 's', 'u', period='2026-09-12')]
        # compose() reads the real clock, not the injected `now` above; this
        # only holds while "yesterday" from _is_stale's own default equals
        # 12 September, i.e. while this suite runs on 13 September 2026 or
        # later. The unit tests above are the ones that don't drift.
        if self.C.datetime.now(self.C.LONDON_TZ).date() == self.C.date(2026, 9, 13):
            self.assertEqual(self.compose(fresh)['footnote'], '')


class ZoneMap(unittest.TestCase):
    def test_zone_file_is_one_ring_in_central_london(self):
        import london_index_card as card
        rings = card.load_zone()
        self.assertEqual(len(rings), 1)
        self.assertGreater(len(rings[0]), 1000)
        lons = [p[0] for p in rings[0]]; lats = [p[1] for p in rings[0]]
        self.assertTrue(-0.17 < min(lons) and max(lons) < -0.07)
        self.assertTrue(51.48 < min(lats) and max(lats) < 51.54)

    def test_zone_lies_inside_the_central_boroughs(self):
        # Every vertex of the zone falls inside one of the boroughs it is
        # known to span; a reprojection error would put vertices in none.
        import london_index_card as card
        b = card.load_boroughs()
        central = ['Westminster', 'City of London', 'Camden', 'Islington', 'Southwark', 'Lambeth',
                   'Tower Hamlets', 'Hackney', 'Kensington and Chelsea']

        def inside(pt, ring):
            x, y = pt; hit = False
            for i in range(len(ring)):
                x1, y1 = ring[i - 1]; x2, y2 = ring[i]
                if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                    hit = not hit
            return hit
        zone = card.load_zone()[0]
        misses = [p for p in zone[::10] if not any(inside(p, r) for n in central for r in b[n])]
        # The river is no borough, so a vertex on the Thames bank may miss; allow a few.
        self.assertLess(len(misses), len(zone[::10]) * 0.15, misses[:5])

    def test_congestion_facts_ask_for_the_zone_map(self):
        rows = [['Month', 'a', 'b', 'c', 'Notes'], ['Jul-26', '2783502', '2359567', '31', '']]
        self.assertTrue(all(f['map_zone'] == 'congestion_charge_zone' for f in H.congestion_facts(rows)))

    def test_empty_zone_refuses_to_draw(self):
        import london_index_card as card
        with self.assertRaises(card.CardRenderError):
            card.render_zone_map([], '/tmp/x.png')


class MetDashboardAndLfb(unittest.TestCase):
    CSV = ('Month_Year,Area Type,Borough_SNT,Area Name,Area Code,offence group,Offence Subgroup,Measure,Financial Year,Count,Refresh Date\n'
           '2026-08-01,Borough,Camden,Camden,E09000007,THEFT,OTHER THEFT,Offences,fy26-27,1200,2026-09-02\n'
           '2026-08-01,Borough,Camden,Camden,E09000007,VIOLENCE AGAINST THE PERSON,VIOLENCE WITH INJURY,Offences,fy26-27,900,2026-09-02\n'
           '2026-08-01,Borough,Camden,Camden,E09000007,THEFT,OTHER THEFT,Positive Outcomes,fy26-27,50,2026-09-02\n'
           '2026-08-01,Safer Neighbourhood Teams,Camden Bloomsbury,Bloomsbury,E05,THEFT,OTHER THEFT,Offences,fy26-27,300,2026-09-02\n'
           '2026-08-01,Borough,Other / NK,Other / NK,-1,THEFT,OTHER THEFT,Offences,fy26-27,99,2026-09-02\n'
           '2026-08-01,Borough,Aviation Policing,Aviation Policing,-1,THEFT,OTHER THEFT,Offences,fy26-27,7,2026-09-02\n'
           '2026-07-01,Borough,Camden,Camden,E09000007,THEFT,OTHER THEFT,Offences,fy26-27,1000,2026-09-02\n')

    def test_mps_parse_keeps_borough_offences_only(self):
        p = H.mps_parse(self.CSV)
        self.assertEqual(p['refresh'], '2026-09-02')
        self.assertEqual(set(p['months']), {'2026-08', '2026-07'})
        self.assertEqual(p['months']['2026-08'], {'Camden': {'total': 2100, 'groups': {'THEFT': 1200, 'VIOLENCE AGAINST THE PERSON': 900}}})
        with self.assertRaises(ValueError):
            H.mps_parse('Month,Count\n2026-08-01,5\n')

    def test_group_name(self):
        self.assertEqual(H._group_name('VIOLENCE AGAINST THE PERSON'), 'Violence against the person')

    def test_needs_refetch_rules(self):
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 9, 12, tzinfo=timezone.utc)
        self.assertFalse(H.needs_refetch({'months': {'2026-08': {}}}, now))            # expected month present
        self.assertTrue(H.needs_refetch({'months': {'2026-07': {}}}, now))             # missing, never fetched
        fresh = (now - timedelta(hours=2)).isoformat(); stale = (now - timedelta(hours=30)).isoformat()
        self.assertFalse(H.needs_refetch({'months': {'2026-07': {}}, 'fetched': fresh}, now))
        self.assertTrue(H.needs_refetch({'months': {'2026-07': {}}, 'fetched': stale}, now))
        same = {'months': {'2026-07': {}}, 'fetched': stale, 'etag': '"a"'}
        self.assertFalse(H.needs_refetch(same, now, url='u', etag_of=lambda u: '"a"'))
        self.assertTrue(H.needs_refetch(same, now, url='u', etag_of=lambda u: '"b"'))
        self.assertTrue(H.needs_refetch(same, now, url='u', etag_of=lambda u: None))

    def test_borough_source_prefers_the_dashboard_and_falls_back(self):
        months = {'2026-08': {'Camden': {'total': 2100, 'groups': {'THEFT': 1200}}},
                  '2026-07': {'Camden': {'total': 1000, 'groups': {'THEFT': 700}}}}
        with unittest.mock.patch.object(H, 'mps_borough_months', return_value=months):
            ym, now, prev, cats, source, url, note, groups, name_fn = H.borough_source()
        self.assertEqual((ym, now, prev), ('2026-08', {'Camden': 2100}, {'Camden': 1000}))
        self.assertEqual(source, H.MPS_SOURCE)
        self.assertEqual(name_fn('THEFT'), 'Theft')
        with unittest.mock.patch.object(H, 'mps_borough_months', return_value={}), \
             unittest.mock.patch.object(H, '_latest_police_month', return_value=('2026-07', [])), \
             unittest.mock.patch.object(H, 'whole_borough_counts', side_effect=lambda ym, names=None, **k:
                                        {'Camden': {'total': 5, 'categories': {'burglary': 5}}}):
            src = H.borough_source()
        self.assertEqual(src[4], 'data.police.uk')
        self.assertEqual(src[1], {'Camden': 5})

    def test_lfb_aggregate_and_facts(self):
        from datetime import datetime
        header = ('IncidentNumber', 'DateOfCall', 'IncidentGroup', 'StopCodeDescription', 'IncGeo_BoroughName',
                  'FirstPumpArriving_AttendanceTime', 'Notional Cost (£)')
        rows = [header,
                ('1', datetime(2026, 7, 1), 'Fire', 'Primary Fire', 'WESTMINSTER', 300, 1000),
                ('2', datetime(2026, 7, 2), 'Fire', 'Secondary Fire', 'CAMDEN', 400, 500),
                ('3', datetime(2026, 7, 3), 'False Alarm', 'AFA', 'WESTMINSTER', None, 500),
                ('4', datetime(2026, 7, 4), 'Special Service', 'Special Service', 'BRENT', 380, 2000000),
                ('5', datetime(2025, 7, 4), 'Fire', 'Primary Fire', 'BRENT', 100, 100)]
        m = H.lfb_aggregate(rows)
        self.assertEqual(m['2026-07']['total'], 4); self.assertEqual(m['2026-07']['fires'], 2)
        self.assertEqual(m['2026-07']['primary_fires'], 1); self.assertEqual(m['2026-07']['false_alarms'], 1)
        self.assertEqual(m['2026-07']['special'], 1); self.assertEqual(m['2026-07']['boroughs']['WESTMINSTER'], 2)
        self.assertAlmostEqual(m['2026-07']['attendance_s'], 360.0)
        facts = H.lfb_facts(m['2026-07'], '2026-07', prev=m['2025-07'])
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Incidents attended', '4'), ('Fires', '2'), ('False alarms', '1'), ('Special services', '1'),
                          ('Most: Westminster', '2'), ('First engine on scene, average', '6 min 0 s'),
                          ('Notional cost', '£2.0 million'), ('Change on a year earlier', '+300%')])
        with self.assertRaises(ValueError):
            H.lfb_aggregate([('a', 'b')])


class Events(unittest.TestCase):
    def test_events_facts(self):
        counts = {'week': 1184, 'day': 280, 'month': 5123,
                  'segments': {'Arts & Theatre': 372, 'Music': 127, 'Miscellaneous': 625, 'Sports': 4}}
        facts = H.events_facts(counts)
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('All events', '1,184'), ('Starting in the next 24 hours', '280'),
                          ('Theatre and arts', '372'), ('Music', '127'), ('Attractions and other', '625'),
                          ('Sport', '4'), ('Listed for the next 30 days', '5,123')])
        self.assertTrue(all(f['period'] is None and f['pair'] == 'events_all' and f['dateline_lead'] == H.TM_LEAD for f in facts))

    def test_no_key_and_no_total_are_named_refusals(self):
        with unittest.mock.patch.object(H, '_tm_key', return_value=None):
            facts, err = H.harvest_events()
        self.assertEqual(facts, []); self.assertIn('ticketmaster-api-key', err)
        with unittest.mock.patch.object(H, '_tm_key', return_value='k'), \
             unittest.mock.patch.object(H, '_tm_total', return_value=None):
            facts, err = H.harvest_events()
        self.assertEqual(facts, []); self.assertIn('seven-day total', err)


class EventsListingsAndMuseums(unittest.TestCase):
    def ev(self, venue, day, test=False, seg='Music'):
        return {'_embedded': {'venues': [{'name': venue}]}, 'dates': {'start': {'localDate': day}}, 'test': test,
                'classifications': [{'segment': {'name': seg}}]}

    def test_listing_facts_busiest_day_and_venues(self):
        L = [self.ev('A', '2026-09-18')] * 5 + [self.ev('B', '2026-09-12')] * 3 + \
            [self.ev('C', '2026-09-18')] * 2 + [self.ev('D', '2026-09-13')] + \
            [self.ev('Twist Museum', '2026-09-18', seg='Miscellaneous')] * 50   # attractions do not count
        facts = H.events_listing_facts(L)
        self.assertEqual((facts[0]['label'], facts[0]['value'], facts[0]['pair']),
                         ('Most performances: Friday 18 September', '7', 'events_all'))
        self.assertEqual([(f['label'], f['value']) for f in facts if f['pair'] == 'venues_top'],
                         [('A', '5'), ('B', '3'), ('C', '2'), ('D', '1')])

    def test_fewer_than_four_venues_means_no_venue_ranking(self):
        facts = H.events_listing_facts([self.ev('A', '2026-09-18')] * 3)
        self.assertEqual([f['pair'] for f in facts], ['events_all'])

    def test_museum_facts(self):
        years = [f'{y}-{str(y + 1)[2:]}' for y in range(2008, 2025)]   # 2008-09 .. 2024-25
        visitors = {y: 6_000_000 for y in years}
        visitors['2024-25'] = 6_474_734; visitors['2023-24'] = 6_159_856; visitors['2014-15'] = 6_695_213
        extras = {'Overseas visitors': '3,822,175', 'Would recommend a visit': '93%'}
        facts = H.museum_facts('British Museum', visitors, years, extras)
        self.assertEqual([(f['label'], f['value']) for f in facts],
                         [('Visitors', '6,474,734'), ('Change on 2023-24', '+5%'),
                          ('Visitors in 2014-15', '6,695,213'), ('Overseas visitors', '3,822,175'),
                          ('Would recommend a visit', '93%')])
        for f in facts:
            self.assertEqual(f['fixed_opener'], {'emoji': '🏛️', 'text': 'British Museum'})
            self.assertEqual(f['period'], '2024-25'); self.assertEqual(f['pair'], 'museum_all')

    def test_museum_uses_its_latest_published_year(self):
        years = ['2022-23', '2023-24', '2024-25']
        facts = H.museum_facts('Wallace Collection', {'2022-23': 400000, '2023-24': 450000}, years, {})
        self.assertEqual(facts[0]['period'], '2023-24')
        self.assertEqual(facts[1]['label'], 'Change on 2022-23')
        with self.assertRaises(ValueError):
            H.museum_facts('X', {}, years, {})

    def test_dcms_table_reads_the_real_file_shape(self):
        # scratch/ holds the 2024/25 release; the same parser the vein runs.
        import glob
        paths = glob.glob(str(Path(__file__).resolve().parent / 'scratch' / 'DCMS_museums_2024_25_tables.ods'))
        if not paths:
            self.skipTest('no local DCMS file')
        H._DCMS_MEMO.clear(); H._DCMS_MEMO['path'] = Path(paths[0])
        table, years = H.dcms_table('1')
        self.assertEqual(years[-1], '2024-25'); self.assertIn('British Museum', table)
        self.assertEqual(int(table['British Museum']['2023-24']), 6159856)
        t6, _ = H.dcms_table('6')
        self.assertAlmostEqual(t6['British Museum']['2023-24'], 0.96)
        H._DCMS_MEMO.clear()


class DatelineLead(unittest.TestCase):
    """compose() puts a fact's dateline_lead ahead of the date on the second
    line; a fact without one renders as before."""

    def compose(self, facts):
        import london_index_compose as C
        for i, f in enumerate(facts):
            f['id'] = f'x:{i}'
            f['vein'] = 'x'   # build_pool() stamps this on real facts
        return C.compose({'opener': {'emoji': '', 'text': 'T'}, 'ids': [f['id'] for f in facts]}, facts)

    def test_lead_rides_the_dateline_with_the_period(self):
        facts = [H.fact('1', 'a', 's', 'u', period='2026-07', dateline_lead='Within a mile of X'),
                 H.fact('2', 'b', 's', 'u', period='2026-07', dateline_lead='Within a mile of X')]
        self.assertEqual(self.compose(facts)['dateline'], 'Within a mile of X, July 2026')

    def test_lead_alone_when_there_is_no_single_period(self):
        facts = [H.fact('1', 'a', 's', 'u', period='2026-06', dateline_lead='Lead'),
                 H.fact('2', 'b', 's', 'u', period='2026-07', dateline_lead='Lead')]
        self.assertEqual(self.compose(facts)['dateline'], 'Lead')

    def test_no_lead_is_unchanged(self):
        facts = [H.fact('1', 'a', 's', 'u', period='2026-06'), H.fact('2', 'b', 's', 'u', period='2026-06')]
        self.assertEqual(self.compose(facts)['dateline'], 'June 2026')

    def test_live_lead_carries_the_clock(self):
        facts = H.rail_facts({'A': [{'std': '09:00', 'etd': 'On time'}] * 2, 'B': [], 'C': [], 'D': []})[:2]
        d = self.compose(facts)['dateline']
        self.assertTrue(d.startswith('Departures in the next hour, 13 main stations, '), d)
        self.assertRegex(d, r'\d{1,2}:\d\d [ap]\.m\.$')


import unittest.mock  # noqa: E402  (used by HousePriceFacts)

if __name__ == '__main__':
    unittest.main()
