"""Tests for is_methodology_thread, the guard on --replace.

Mirrors seoul-index's test_seoul_index_methodology.py ReplaceRecognisesItsOwnThread
class -- same function, same risk (a wrong answer here means --replace deletes
the wrong thing), and until now london-index had no coverage of it at all while
its sister bot did.

No network and no posting: the facets are built locally and nothing is sent.
"""
import sys, unittest
from pathlib import Path

# Refuses unrecognised argv at import time (a bare run posts live), so
# unittest's own arguments have to be cleared before importing it.
sys.argv = ['test']
sys.path.insert(0, str(Path(__file__).resolve().parent))
import london_index_methodology as M


def _card(alt='About this account'):
    """A methodology card as the repo returns it: no text, one image."""
    return {'uri': 'at://did/app.bsky.feed.post/x', 'value': {
        'text': '', 'createdAt': '2026-09-19T00:00:00Z',
        'embed': {'images': [{'alt': alt}]}}}


def _credits(text=None):
    return {'uri': 'at://did/app.bsky.feed.post/y', 'value': {
        'text': M.SOURCE_LINE if text is None else text,
        'createdAt': '2026-09-19T00:00:01Z'}}


def _code_reply(text=None):
    return {'uri': 'at://did/app.bsky.feed.post/z', 'value': {
        'text': M.CODE_PREFIX + 'GitHub' if text is None else text,
        'createdAt': '2026-09-19T00:00:02Z'}}


def _thread(cards=None, last=None):
    return [_card() for _ in range(len(M.CARDS) if cards is None else cards)] + [
        _credits() if last is None else last]


class ReplaceRecognisesItsOwnThread(unittest.TestCase):
    """Guards --replace, which deletes whatever was pinned when it started."""

    def test_a_real_thread_is_recognised(self):
        self.assertTrue(M.is_methodology_thread(_thread()))

    def test_a_thread_of_a_DIFFERENT_length_is_still_recognised(self):
        for n in (len(M.CARDS) - 1, len(M.CARDS) + 1):
            self.assertTrue(M.is_methodology_thread(_thread(cards=n)),
                            f'{n} cards + credits should still be recognized')

    def test_a_thread_too_short_or_too_long_is_refused(self):
        for n in (0, M.MAX_THREAD_RECORDS):
            self.assertFalse(M.is_methodology_thread(_thread(cards=n)),
                             f'{n} cards + credits should not be recognized')

    def test_a_card_with_text_is_refused(self):
        thread = _thread()
        thread[0]['value']['text'] = '#London'
        self.assertFalse(M.is_methodology_thread(thread))

    def test_a_card_without_an_image_is_refused(self):
        thread = _thread()
        thread[1]['value'].pop('embed')
        self.assertFalse(M.is_methodology_thread(thread))

    def test_a_last_post_that_is_not_the_credits_is_refused(self):
        self.assertFalse(M.is_methodology_thread(
            _thread(last=_credits('Just a reply, not the credits'))))

    def test_the_credits_still_open_with_the_prefix(self):
        self.assertTrue(M.SOURCE_LINE.startswith(M.SOURCE_PREFIX))

    def test_a_thread_with_the_code_reply_is_recognised(self):
        """Since 19 September 2026 a thread may end in TWO text replies
        (sources, then the code credit) rather than one. Both shapes must be
        recognised: the one-reply shape is every thread already live the
        moment this code shipped, and --replace has to find and delete
        exactly that thread on its first run under the new code."""
        thread = _thread(last=_credits())
        thread.append(_code_reply())
        self.assertTrue(M.is_methodology_thread(thread))

    def test_a_code_reply_with_the_wrong_text_is_refused(self):
        thread = _thread(last=_credits())
        thread.append(_code_reply('Just a plain reply, not the code credit'))
        self.assertFalse(M.is_methodology_thread(thread))

    def test_a_third_trailing_text_reply_is_refused(self):
        thread = _thread(last=_credits())
        thread.append(_code_reply())
        thread.append(_code_reply('one more, unexpectedly'))
        self.assertFalse(M.is_methodology_thread(thread))

    def test_the_code_reply_still_opens_with_its_prefix(self):
        self.assertTrue(M._code_tb().build_text().startswith(M.CODE_PREFIX))

    def test_replace_is_a_recognised_argument(self):
        self.assertIn('--replace', M._KNOWN_ARGS)


if __name__ == '__main__':
    unittest.main()
