"""Tests for london_index_post.py's main() around the parts that must not
have side effects: a dry run changes no state and posts nothing. Everything
network-shaped is patched; no Bluesky, no claude -p, no Chrome.

Until 12 September 2026 a dry run wrote vein_last_at and recent_ids to the
state file, so a hand rehearsal put its vein on the 20-hour cooldown for
the next real run. This suite exists to keep that from coming back.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import london_index_post as P


class DryRun(unittest.TestCase):
    def run_dry(self, state_path, history_path):
        pool = [{'id': 'v:0', 'vein': 'v', 'label': 'a', 'value': '1', 'pair': None,
                 'source': 's', 'url': 'u', 'period': None, 'context_note': None},
                {'id': 'v:1', 'vein': 'v', 'label': 'b', 'value': '2', 'pair': None,
                 'source': 's', 'url': 'u', 'period': None, 'context_note': None}]
        sel = {'opener': {'emoji': '', 'text': 'T'}, 'ids': ['v:0', 'v:1'], 'vein': 'v'}
        with patch.object(P, 'STATE', state_path), patch.object(P, 'CARD_LOG', history_path), \
             patch.object(P, 'LOCK', state_path.with_suffix('.lock')), \
             patch.object(P.select_mod, 'build_pool', return_value=(pool, {})), \
             patch.object(P.select_mod, 'select', return_value=sel), \
             patch.object(P.card, 'render_card', return_value=('/dev/null', (10, 10))), \
             patch.object(Path, 'read_bytes', return_value=b''), \
             patch.object(sys, 'argv', ['london_index_post.py', '--dry-run']):
            P.main()

    def test_dry_run_writes_no_state_and_no_history(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / 'state.json'
            history = Path(td) / 'card_history.jsonl'
            state.write_text(json.dumps({'recent_ids': ['old'], 'vein_last_at': {}}))
            self.run_dry(state, history)
            self.assertEqual(json.loads(state.read_text()), {'recent_ids': ['old'], 'vein_last_at': {}})
            self.assertFalse(history.exists())

    def test_dry_run_creates_no_state_file_where_none_existed(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / 'state.json'
            self.run_dry(state, Path(td) / 'card_history.jsonl')
            self.assertFalse(state.exists())


class CardAlt(unittest.TestCase):
    """The alt must say everything the picture says. The dateline was
    missing from it until 12 September 2026: the crime card read "July
    2026" on the image and nothing in the alt."""

    def _card(self, **over):
        c = {'opener': {'emoji': '🚓', 'text': 'Reported crime'},
             'dateline': 'July 2026',
             'lines': [{'label': 'Within a mile of central London', 'value': '4,728'},
                       {'label': "Most common: Other theft", 'value': '1,097'}],
             'footnote': ''}
        c.update(over)
        return c

    def test_the_dateline_is_in_the_alt(self):
        alt = P.card_alt(self._card())
        self.assertEqual(alt.split('\n')[:2], ['Reported crime', 'July 2026'])
        self.assertIn('Within a mile of central London: 4,728', alt)

    def test_no_dateline_means_no_blank_line(self):
        alt = P.card_alt(self._card(dateline=''))
        self.assertEqual(alt.split('\n')[1], 'Within a mile of central London: 4,728')

    def test_footnote_is_bracketed_and_apostrophes_curled(self):
        alt = P.card_alt(self._card(footnote="Sir John Soane's Museum counted"))
        self.assertTrue(alt.endswith('(Sir John Soane’s Museum counted)'))
        self.assertNotIn("'", alt)

    def test_main_uses_the_helper(self):
        src = Path(P.__file__).read_text()
        self.assertIn('        alt = card_alt(c)\n', src)


class LoginRetry(unittest.TestCase):
    def test_retries_then_succeeds_without_sleeping_for_real(self):
        calls = []
        slept = []

        class Flaky:
            n = 0
            def login(self, handle, password):
                Flaky.n += 1
                calls.append(Flaky.n)
                if Flaky.n < 3:
                    raise TimeoutError('read timed out')
        client = P.login_with_retry(Flaky, 'h', 'p', sleep=slept.append)
        self.assertIsInstance(client, Flaky)
        self.assertEqual(calls, [1, 2, 3])
        self.assertEqual(slept, [15, 45])

    def test_gives_up_after_three_and_raises_the_last_error(self):
        class Bad:
            def login(self, handle, password):
                raise ValueError('bad password')
        with self.assertRaises(ValueError):
            P.login_with_retry(Bad, 'h', 'p', sleep=lambda s: None)


if __name__ == '__main__':
    unittest.main()
