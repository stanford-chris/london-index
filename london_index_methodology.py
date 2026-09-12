#!/usr/bin/env python3
"""
Post the London Index methodology / "about" thread as prose cards, then pin it.

Mirrors Seoul Index's seoul_index_methodology.py (its sibling bot, same
mechanism), scaled to what London Index actually is: English only (no
Korean posts here), 4 cards instead of Seoul's 5 EN + 5 KO, and no
crowd-log/artwork content since this account has neither. Posting it stands
up a 5-post thread:

  1. "About this account" card         (image, no caption)
  2. "About the figures" card
  3. "About the crowding figures" card
  4. "About the museum figures" card
  5. a short reply with clickable source links

Each card's full text is its alt text. The link stays clickable because it
lives in the trailing text reply, not the image (Bluesky renders post text
above the image, so a caption can't sit under the card — same reason the
daily index posts use a trailing source reply).

This is STATIC content, not part of the daily automation (no launchd). Run
it by hand.

Usage:
  python3 london_index_methodology.py --dry-run   # render cards to cwd, print plan
  python3 london_index_methodology.py             # post the thread
  python3 london_index_methodology.py --pin       # post, then pin the root
  python3 london_index_methodology.py --replace   # post, pin, delete the old thread

--replace exists for the day this wording changes: a card is an image, so
changing a word means five new records. Without it a superseded thread
stays in the feed, unpinned and wrong. --replace implies --pin, and deletes
ONLY the records of the thread that was pinned when the run started, and
only after the new thread is up and pinned — an account briefly missing a
pinned thread is recoverable, one whose credits were deleted before the
replacement posted is not. Same ordering Seoul Index's own --replace uses,
for the same reason.
"""

import json
import sys
import tempfile
from pathlib import Path

from atproto import Client, client_utils, models

from london_index_card import render_prose_card, curly
from london_index_post import HANDLE, KEYCHAIN_SERVICE, keychain_password

# Same lesson as london_index_post/select's own guards: an unrecognised flag
# would silently run LIVE (no flag at all means "post for real"), so refuse
# anything unknown before doing anything.
_KNOWN_ARGS = {'--dry-run', '--pin', '--replace'}
_unknown = [a for a in sys.argv[1:] if a not in _KNOWN_ARGS]
if _unknown:
    sys.exit(f'Unknown argument(s): {" ".join(_unknown)}. '
             f'Recognised: {" ".join(sorted(_KNOWN_ARGS))}. '
             f'Refusing to run (a bare run posts live).')

DRY_RUN = '--dry-run' in sys.argv
REPLACE = '--replace' in sys.argv
# Replacing without pinning would leave the account with no pinned thread at
# all, which is the one outcome worse than a stale one.
PIN = '--pin' in sys.argv or REPLACE
HERE = Path(__file__).parent

# --- content ---------------------------------------------------------------
# Straight quotes/apostrophes below are deliberate: london_index_card.curly()
# converts them for both the rendered card and the alt text (see _alt below),
# so there is exactly one place typography can be wrong, not one per string.

INTRO = ("This account provides a portrait of London, drawn from the city's own "
         "open data. An A.I. chooses which figures to set side by side and writes "
         "the posts. Every publisher is credited at the end of this thread.")
COUNTS = ("Counts appear exactly as published: bikes and docking points, river "
          "levels against their own typical range, reported crimes, air quality "
          "readings, museum visitor totals, station entries and exits, house "
          "prices, trains due. Nothing here is estimated or modelled by this "
          "account itself.")
# tfl_crowding (TfL's undocumented, relative-to-itself /crowding/Live
# endpoint) is paused as of 31 August 2026 - see HARVESTERS in
# london_index_harvest.py for why - and station_usage/daily_footfall took
# its place: real gate taps, not a relative percentage. This card describes
# what the account now actually posts, not the retired vein.
STATIONS = ("Station figures come in two grains: a whole year's total (TfL's own "
            "Annual Station Counts), or the most recent single day TfL has "
            "published, network-wide. Both are real gate taps, not modelled; "
            "entries and exits are counted separately, so a return trip counts "
            "twice.")
# "13 ... out of 18" is LONDON_DCMS_MUSEUMS against the full row count in
# london_index_harvest.py's Table 1 parse — update both together if DCMS adds
# or drops a sponsored institution.
MUSEUMS = ("Museum visitor totals are the Department for Culture, Media and "
           "Sport's (DCMS) own annual figures for the 13 London-based museums it "
           "sponsors, out of 18 nationally: not every museum in London, and not "
           "live. DCMS publishes them once a year.")

CARDS = [
    {'heading': 'About this account', 'emoji': '\U0001f1ec\U0001f1e7', 'body': [INTRO]},
    {'heading': 'About the figures', 'emoji': '\U0001f9ee', 'body': [COUNTS]},
    {'heading': 'About the station figures', 'emoji': '\U0001f687', 'body': [STATIONS]},
    {'heading': 'About the museum figures', 'emoji': '\U0001f5bc️', 'body': [MUSEUMS]},
]

# Every publisher a live vein in london_index_harvest.HARVESTERS actually
# draws on, each hyperlinked in the trailing reply — never Ticketmaster or
# Darwin, which are registered but not wired into the harvester yet. Kept as
# its own constant so the recogniser (is_methodology_thread) and the line
# itself cannot drift apart. "www.gov.uk", not the bare "gov.uk", so it is
# never mistaken by _source_tb() for the "gov.uk" substring already inside
# environment.data.gov.uk and data.london.gov.uk earlier in the same line.
SOURCE_PREFIX = 'Sources: '
SOURCE_LINE = (SOURCE_PREFIX + 'tfl.gov.uk, crowding.data.tfl.gov.uk, '
               'environment.data.gov.uk, data.police.uk, '
               'data.london.gov.uk, londonair.org.uk, www.gov.uk, '
               'landregistry.data.gov.uk, nationalrail.co.uk')
# landregistry.data.gov.uk (UK House Price Index) and nationalrail.co.uk
# (Rail Delivery Group's Live Departure Board, whose licence requires the
# credit) added 12 September 2026 with the house_prices and rail_departures
# veins. Neither is a substring of another listed domain, nor contains one:
# 'data.gov.uk' and 'gov.uk' are never listed bare. Facet byte-ranges were
# checked against the rendered text on the dry run before posting.
# 'crowding.data.tfl.gov.uk' contains 'tfl.gov.uk' as a substring - the exact
# hazard _source_tb()'s own docstring warns about. Safe only because
# 'tfl.gov.uk' is listed FIRST in SOURCE_LINE, so .find('tfl.gov.uk') locates
# the standalone occurrence before the embedded one; verified 1 September
# 2026 by actually running _source_tb() and checking the facet byte-ranges
# against the rendered text, not just reasoning about it.
SOURCE_DOMAINS = [('tfl.gov.uk', 'https://tfl.gov.uk'),
                  ('crowding.data.tfl.gov.uk', 'https://crowding.data.tfl.gov.uk'),
                  ('environment.data.gov.uk', 'https://environment.data.gov.uk'),
                  ('data.police.uk', 'https://data.police.uk'),
                  ('data.london.gov.uk', 'https://data.london.gov.uk'),
                  ('londonair.org.uk', 'https://www.londonair.org.uk'),
                  ('www.gov.uk', 'https://www.gov.uk'),
                  ('landregistry.data.gov.uk', 'https://landregistry.data.gov.uk/app/ukhpi'),
                  ('nationalrail.co.uk', 'https://www.nationalrail.co.uk')]


def _alt(card):
    # curly() so the alt text matches the card, which the renderer curls.
    return curly(card['heading'] + '\n\n' + '\n\n'.join(card['body']))


def _source_tb():
    """Clickable source line, no hashtags — keeps the pinned thread clean.
    Walks the domains in the order they appear so the facets stay in step
    with the text however SOURCE_LINE is reordered. Relies on no domain in
    SOURCE_DOMAINS being a substring of another — see the SOURCE_LINE
    comment above for the one case that needed avoiding."""
    tb = client_utils.TextBuilder()
    hits = sorted((SOURCE_LINE.find(dom), dom, url) for dom, url in SOURCE_DOMAINS
                  if SOURCE_LINE.find(dom) != -1)
    pos = 0
    for i, dom, url in hits:
        if i < pos:  # a later domain nested inside an earlier match — skip
            continue
        tb.text(SOURCE_LINE[pos:i]).link(dom, url)
        pos = i + len(dom)
    tb.text(SOURCE_LINE[pos:])
    return tb


def render_all(out_dir):
    out = []
    for i, card in enumerate(CARDS):
        path = Path(out_dir) / f'meth_{i}.png'
        _, size = render_prose_card(card['heading'], card['body'], path, emoji=card['emoji'])
        out.append((str(path), size))
    return out


def main():
    rendered = render_all(Path.cwd() if DRY_RUN else tempfile.mkdtemp())

    print('Methodology thread plan:')
    for card, (path, size) in zip(CARDS, rendered):
        print(f'  {card["emoji"]} {card["heading"]} — {size}  {path}')
    clickable = ', '.join(dom for dom, _ in SOURCE_DOMAINS)
    print(f'  [reply] {_source_tb().build_text()!r} (clickable: {clickable})')

    if DRY_RUN:
        print('\n(dry run — rendered cards, not posting)')
        return

    password = keychain_password(HANDLE, KEYCHAIN_SERVICE)
    bsky = Client()
    bsky.login(HANDLE, password)

    # Read this before posting: once the new root is pinned the old uri is
    # gone from the profile record, and with it the only pointer to what to
    # delete.
    old_root_uri = current_pinned_uri(bsky) if REPLACE else None
    if REPLACE and old_root_uri is None:
        print('--replace: nothing is pinned, so there is no thread to replace.')

    def _reply(parent_ref, root_ref):
        return models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)

    root_ref = None
    prev_ref = None
    for card, (path, size) in zip(CARDS, rendered):
        ar = models.AppBskyEmbedDefs.AspectRatio(width=size[0], height=size[1])
        img = Path(path).read_bytes()
        kwargs = dict(text='', image=img, image_alt=_alt(card),
                      langs=['en'], image_aspect_ratio=ar)
        if prev_ref is not None:
            kwargs['reply_to'] = _reply(prev_ref, root_ref)
        post = bsky.send_image(**kwargs)
        prev_ref = models.create_strong_ref(post)
        if root_ref is None:
            root_ref = prev_ref
    # Trailing clickable source reply.
    bsky.send_post(text=_source_tb(), reply_to=_reply(prev_ref, root_ref), langs=['en'])
    print(f'\nPosted methodology thread ({len(CARDS)} cards + source reply).')

    if PIN:
        pin_post(bsky, root_ref)
        print('Pinned the thread root.')

    if REPLACE and old_root_uri:
        replace_old_thread(bsky, old_root_uri)


def pin_post(bsky, root_ref):
    """Pin root_ref by updating ONLY the pinned_post field of the existing
    profile record, so the avatar/description are preserved."""
    got = bsky.com.atproto.repo.get_record(
        models.ComAtprotoRepoGetRecord.Params(
            repo=bsky.me.did, collection='app.bsky.actor.profile', rkey='self'))
    record = got.value
    record.pinned_post = models.ComAtprotoRepoStrongRef.Main(
        cid=root_ref.cid, uri=root_ref.uri)
    bsky.com.atproto.repo.put_record(
        models.ComAtprotoRepoPutRecord.Data(
            repo=bsky.me.did, collection='app.bsky.actor.profile', rkey='self',
            record=record, swap_record=got.cid))


def current_pinned_uri(bsky):
    """The uri of the currently pinned post, or None if nothing is pinned."""
    got = bsky.com.atproto.repo.get_record(
        models.ComAtprotoRepoGetRecord.Params(
            repo=bsky.me.did, collection='app.bsky.actor.profile', rkey='self'))
    pinned = getattr(got.value, 'pinned_post', None)
    return pinned.uri if pinned else None


def all_records(did):
    """Every app.bsky.feed.post record in the repo, oldest last. Inlined from
    Seoul Index's wipe_posts.py rather than imported — London Index has no
    such module, and this is the only place here that needs it."""
    import subprocess
    r = subprocess.run(['curl', '-sS', '--max-time', '25', f'https://plc.directory/{did}'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'plc.directory lookup failed for {did}')
    doc = json.loads(r.stdout)
    pds = next(s['serviceEndpoint'] for s in doc['service']
               if s['type'] == 'AtprotoPersonalDataServer')
    out, cursor = [], None
    while True:
        url = (f'{pds}/xrpc/com.atproto.repo.listRecords?repo={did}'
               f'&collection=app.bsky.feed.post&limit=100'
               + (f'&cursor={cursor}' if cursor else ''))
        r = subprocess.run(['curl', '-sS', '--max-time', '25', url],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f'listRecords fetch failed: {url}')
        page = json.loads(r.stdout)
        out.extend(page.get('records', []))
        cursor = page.get('cursor')
        if not cursor or not page.get('records'):
            return out


def old_thread_records(did, root_uri):
    """Every record of the thread rooted at root_uri, oldest first.

    A reply names its root, so one pass over the repo collects the whole
    thread without walking parent links. Listed from the PDS rather than
    from a thread view for the same reason Seoul Index's wipe_posts lists it
    that way: a view can drop replies, and the source reply is the one post
    here with no image on it."""
    recs = all_records(did)
    mine = [r for r in recs
            if r['uri'] == root_uri
            or (((r['value'].get('reply') or {}).get('root') or {}).get('uri')
                == root_uri)]
    return sorted(mine, key=lambda r: r['value']['createdAt'])


# A thread longer than this is not one of ours whatever it looks like, and
# the bound is what stops a runaway match deleting an account's worth of
# records.
MAX_THREAD_RECORDS = 25


def is_methodology_thread(recs):
    """Does this look like a thread THIS script posted?

    --replace deletes whatever was pinned, and what is pinned is not
    guaranteed to be a methodology thread: pin a daily card by hand, forget,
    and a later --replace would take that card and every reply under it. So
    the shape is checked first, and it is a shape no daily post has:
    captionless image posts, then one text reply opening with the credits.
    A methodology card carries empty text by construction (Bluesky renders
    text above the image, so a caption cannot sit under the card), while a
    daily card is an image WITH a hashtag caption.

    The count is deliberately NOT compared with len(CARDS), matching Seoul
    Index's own is_methodology_thread — the thread being replaced is by
    definition the PREVIOUS shape, so measuring it against the current one
    is the one comparison guaranteed to fail exactly when it is needed (see
    that function's docstring for the concrete case that bit it)."""
    if not 2 <= len(recs) <= MAX_THREAD_RECORDS:
        return False
    *cards, last = recs
    if any((r['value'].get('text') or '') for r in cards):
        return False
    if not all((r['value'].get('embed') or {}).get('images') for r in cards):
        return False
    return (last['value'].get('text') or '').startswith(SOURCE_PREFIX)


def replace_old_thread(bsky, old_root_uri):
    """Delete the superseded thread, after printing the wording it takes
    with it. Refuses, loudly and without deleting anything, if what was
    pinned is not a methodology thread: by this point the replacement is
    already up, so the safe failure is to leave both threads standing and
    say so."""
    recs = old_thread_records(bsky.me.did, old_root_uri)
    print(f'\nSuperseded thread, {len(recs)} record(s) '
          f'(rooted at {old_root_uri.split("/")[-1]}):')
    for r in recs:
        v = r['value']
        body = v.get('text') or ' / '.join(
            i.get('alt', '') for i in (v.get('embed') or {}).get('images', []))
        print(f'  {r["uri"].split("/")[-1]}  {body[:100].replace(chr(10), " ")}')

    if not is_methodology_thread(recs):
        sys.exit('\nThat is not the shape of a methodology thread, so nothing '
                 'was deleted. The new thread is posted and pinned; the old one '
                 'is still up. Sort it out by hand.')

    failed = [r['uri'] for r in recs if not bsky.delete_post(r['uri'])]
    left = all_records(bsky.me.did)
    survivors = [r['uri'] for r in recs if r['uri'] in {x['uri'] for x in left}]
    print(f'Deleted {len(recs) - len(survivors)} of {len(recs)}.')
    if failed or survivors:
        sys.exit(f'Deletion incomplete: {len(failed)} call(s) failed, '
                 f'{len(survivors)} record(s) still in the repo.')


if __name__ == '__main__':
    main()
