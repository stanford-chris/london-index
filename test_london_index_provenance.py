"""london_index_provenance.PROVENANCE against the harvester it describes.
No network."""
import inspect
import re
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import london_index_harvest as H
from london_index_provenance import PROVENANCE

FIELDS = ('source', 'counts', 'checked_against', 'complete_fetch', 'labels', 'verified')


def _code_names(fn):
    """[(name, called)] for every name in `fn`'s code, comments and strings
    (its docstring among them) left out, so prose naming a function does not
    count as using it."""
    import io
    import tokenize
    toks = [t for t in tokenize.generate_tokens(io.StringIO(inspect.getsource(fn)).readline)
            if t.type in (tokenize.NAME, tokenize.OP)]
    return [(t.string, i + 1 < len(toks) and toks[i + 1].string == '(')
            for i, t in enumerate(toks) if t.type == tokenize.NAME][2:]   # past "def <name>"


def reaches_a_check(fn, seen=None, depth=6):
    """True when `fn`'s code, or that of a module function it names (called,
    or handed on as `check=journey_checks`; followed `depth` deep), calls
    require() or reconcile(). What this proves: a 'build' entry is not
    describing a harvester with no check at all on its path. What it does
    not: that the check is the one the entry describes, that it runs on every
    branch, or that a shared helper's check (the S3 listing guard, say) is
    this vein's own; those are for test_london_index_harvest.py and reading."""
    seen = set() if seen is None else seen
    if fn in seen or depth < 0:
        return False
    seen.add(fn)
    names = _code_names(fn)
    if any(called and n in ('require', 'reconcile') for n, called in names):
        return True
    for n, _ in names:
        g = getattr(H, n, None)
        if inspect.isfunction(g) and g.__module__ == H.__name__ and g not in (H.require, H.reconcile):
            if reaches_a_check(g, seen, depth - 1):
                return True
    return False


class Provenance(unittest.TestCase):
    def test_one_entry_per_harvester(self):
        self.assertEqual(set(PROVENANCE), set(H.HARVESTERS))

    def test_every_field_present_and_written(self):
        for vein, entry in PROVENANCE.items():
            for f in FIELDS:
                self.assertIsInstance(entry.get(f), str, f'{vein}.{f}')
                self.assertTrue(entry[f].strip(), f'{vein}.{f} is empty')
            date.fromisoformat(entry['verified'])

    def test_every_check_is_well_formed(self):
        for vein, entry in PROVENANCE.items():
            self.assertTrue(entry.get('checks'), f'{vein} lists no check')
            for c in entry['checks']:
                self.assertIn(c.get('kind'), ('RECONCILE', 'SHAPE'), vein)
                self.assertIn(c.get('when'), ('build', 'audit', 'none'), vein)
                self.assertTrue((c.get('what') or '').strip(), f'{vein}: a check says nothing')

    def test_a_build_check_is_on_the_harvesters_path(self):
        for vein, entry in PROVENANCE.items():
            if any(c['when'] == 'build' for c in entry['checks']):
                self.assertTrue(reaches_a_check(H.HARVESTERS[vein]),
                                f'{vein} lists a build check, but its harvester calls none')

    def test_the_path_test_can_fail(self):
        # A harvester with no check on its path reads as such.
        self.assertFalse(reaches_a_check(H.harvest_tfl_crowding))


if __name__ == '__main__':
    unittest.main()
