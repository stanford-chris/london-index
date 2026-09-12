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


if __name__ == '__main__':
    unittest.main()
