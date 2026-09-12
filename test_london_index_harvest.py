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
        self.assertTrue(all(f['context_note'] == H.CENTRAL_NOTE for f in top))

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

    def test_every_fact_carries_the_sample_note(self):
        for f in self.facts():
            self.assertEqual(f['context_note'], H.BOROUGH_NOTE)
            self.assertEqual(f['period'], '2026-07')
        self.assertIn('eight boroughs sampled', H.BOROUGH_NOTE)


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


class RailFacts(unittest.TestCase):
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
                         [('Trains due within the hour', '11', 'rail_all'), ('On time', '8', 'rail_all'),
                          ('Running late', '1', 'rail_all'), ('Cancelled', '1', 'rail_all'),
                          ('Waterloo', '6', 'rail_top'), ('Euston', '3', 'rail_top'),
                          ('Moorgate', '1', 'rail_top'), ('Victoria', '1', 'rail_top')])
        self.assertTrue(all(f['period'] is None and f['context_note'] == H.RAIL_NOTE for f in facts))

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


import unittest.mock  # noqa: E402  (used by HousePriceFacts)

if __name__ == '__main__':
    unittest.main()
