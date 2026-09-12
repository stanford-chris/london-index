#!/usr/bin/env python3
"""
Entry point for London Index (@london-index.bsky.social). Orchestrates the
whole pipeline: harvest -> select (claude -p) -> compose -> render -> post,
then logs the result. See SESSION_SUMMARY.md and the approved posting-
pipeline plan for what this deliberately does NOT do yet (cross-vein
collisions, spotlight cards, label-accuracy audit, bilingual threads) and
why. Vein rotation (cooldown + starve-floor) shipped 6 September 2026 —
see london_index_select.py's apply_cooldown()/promote_starved().

Posts a 2-post thread: the card image (no caption text, so the image stays
visually first), then a reply with the clickable source credit(s). Falls
back to a plaintext post if rendering fails, so a post always goes out.

Usage:
    python3 london_index_post.py --dry-run      # harvest, select, compose, render; print; no post
    python3 london_index_post.py                # the real thing
    python3 london_index_post.py --only=tfl_bikes  # force one vein
"""

import argparse
import fcntl
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import london_index_card as card
import london_index_compose as compose_mod
import london_index_select as select_mod

HERE = Path(__file__).parent
STATE = HERE / 'london_index_state.json'
CARD_LOG = HERE / 'card_history.jsonl'
LOCK = HERE / '.post.lock'
HANDLE = 'london-index.bsky.social'
KEYCHAIN_SERVICE = 'londonindex-bluesky'
MAX_POST_CHARS = 280
LONDON_TZ = timezone(timedelta(hours=1))


def keychain_password(account, service):
    r = subprocess.run(['security', 'find-generic-password', '-a', account,
                        '-s', service, '-w'], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            f'No Keychain password for account="{account}" service="{service}".\n'
            f'Add it with:\n'
            f'  security add-generic-password -a "{account}" -s "{service}" -w')
    return r.stdout.strip()


LOGIN_ATTEMPTS = 3
LOGIN_DELAYS = (15, 45)   # seconds between attempts


def login_with_retry(client_cls, handle, password, attempts=LOGIN_ATTEMPTS, delays=LOGIN_DELAYS,
                     sleep=time.sleep):
    """A logged-in client, or the last exception re-raised after `attempts`
    tries. Added 12 September 2026 after the 08:00 BST run harvested for six
    minutes, composed and rendered a card, then died at bsky.login() on a
    single httpx ReadTimeout with no retry: a transient blip cost the whole
    slot. Any exception is retried, since the point is the class of fault
    (a timeout, a reset, a 5xx) and a genuinely bad password fails all three
    times and is raised just the same."""
    last = None
    for i in range(attempts):
        try:
            client = client_cls()
            client.login(handle, password)
            return client
        except Exception as e:  # noqa: BLE001 - see the docstring
            last = e
            if i < attempts - 1:
                delay = delays[min(i, len(delays) - 1)]
                print(f'Bluesky login failed ({type(e).__name__}); retrying in {delay}s '
                      f'({i + 2} of {attempts}).', file=sys.stderr)
                sleep(delay)
    raise last


def write_json_atomic(path, data, **dumps_kwargs):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, **dumps_kwargs))
    tmp.replace(path)


def log_card(c, post_uri, handle, fallback):
    """Best-effort append-only log; a logging failure is warned and
    swallowed, never raised — the thread is already live by this point."""
    try:
        rkey = post_uri.rsplit('/', 1)[-1] if post_uri else None
        url = f'https://bsky.app/profile/{handle}/post/{rkey}' if rkey else None
        rec = {
            'at': datetime.now(LONDON_TZ).strftime('%Y-%m-%d %H:%M:%S'),
            'primary_vein': c['primary_vein'],
            'veins': c['veins'],
            'opener': c['opener']['text'],
            'dateline': c['dateline'],
            'lines': c['lines'],
            'source_text': c['source_text'],
            'fallback': fallback,
            'url': url,
        }
        with CARD_LOG.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f'(card log failed: {e})')


def card_alt(c):
    """The card's alt text: opener, dateline, every line as "label: value",
    footnote in brackets, all curled to match the image. Lifted out of
    main() on 12 September 2026 so a test can hold it: the dateline had
    been left out of the alt until that morning, so a screen-reader user
    got a two-month-old crime figure with no month while the picture said
    "July 2026", and nothing would have noticed it going missing again."""
    alt = f"{card.curly(c['opener']['text'])}\n"
    if c['dateline']:
        alt += f"{card.curly(c['dateline'])}\n"
    alt += '\n'.join(
        f"{card.curly(l['label'])}: {card.curly(l['value'])}" for l in c['lines'])
    if c['footnote']:
        alt += f"\n({card.curly(c['footnote'])})"
    return alt


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--only', dest='source', choices=sorted(select_mod.harvest.HARVESTERS))
    args = ap.parse_args()

    lock = open(LOCK, 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit('Another london_index_post run is in progress; bowing out.')

    print(f'--- run at {datetime.now(LONDON_TZ):%Y-%m-%d %H:%M:%S} BST ---')

    pool, errors = select_mod.build_pool(args.source)
    if errors:
        print(f'{len(errors)} source(s) failed: {list(errors)}', file=sys.stderr)
    if not pool:
        sys.exit('No facts harvested; nothing to post.')

    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    try:
        sel = select_mod.select(pool, state)
    except select_mod.NothingFresh as e:
        # A skipped slot, on purpose: every fact left has already been
        # posted at this value, and a repeat is the fault this bot actually
        # had (see select.py's spent-facts section). Exit 0, since this is
        # the guard working, not the run failing; bot_health_check.py still
        # sees a feed that has gone quiet if it happens for a day.
        print(f'Slot skipped: {e}.')
        return
    c = compose_mod.compose(sel, pool)

    # The last line of defence, added 12 September 2026 alongside the spent
    # filter: whatever the selector did, a card whose lines match one
    # already posted does not go out. The filter should make this
    # unreachable; this is what says so if it ever isn't (a --only run, a
    # future selection path, a history file the filter could not read).
    key = select_mod.card_lines_key(c['lines'])
    if key in select_mod.posted_cards(CARD_LOG):
        sys.exit('Refusing to post: this card, line for line, has already '
                 f'been posted. Lines: {key}')

    print(f"{c['opener']['emoji']} {c['opener']['text']}")
    for l in c['lines']:
        print(f"  {l['label']}: {l['value']}")
    if c['footnote']:
        print(f"  ({c['footnote']})")
    print(f"Source: {c['source_text']}")

    fallback = False
    try:
        out_path, size = card.render_card(
            c['opener'], c['lines'], HERE / 'card.png',
            footnote=c['footnote'], dateline=c['dateline'])
        image_bytes = Path(out_path).read_bytes()
    except card.CardRenderError as e:
        print(f'Card render failed ({e}); falling back to plaintext.', file=sys.stderr)
        fallback = True
        image_bytes = None
        size = None

    if args.dry_run:
        if not fallback:
            print(f'\n(dry run — wrote {out_path} at {size[0]}x{size[1]}, not posting)')
        else:
            print('\n(dry run — not posting)')
        # The state file is NOT written on a dry run, since 12 September
        # 2026. Until then it was, so a hand dry-run at 9:00 stamped that
        # vein into vein_last_at and put it on the 20-hour cooldown for the
        # 12:30 run, and its ids into recent_ids: a rehearsal changing the
        # performance. Only a real post changes state.
        print('(dry run — state file untouched)')
        return

    password = keychain_password(HANDLE, KEYCHAIN_SERVICE)

    from atproto import Client, client_utils, models
    bsky = login_with_retry(Client, HANDLE, password)

    posted_uri = None
    if not fallback:
        # curly(), not _esc(): this text goes to Bluesky as plain alt text,
        # never through HTML, so only the typographer's-quotes half of
        # london_index_card.py's _esc() applies — html.escape() would wrongly
        # turn a literal "&" into "&amp;" here. Added 8 September 2026: this
        # alt was built straight from compose()'s raw strings with no curling
        # at all, so every apostrophe in it (museum names, possessives) shipped
        # as U+0027 while the card IMAGE right next to it, built through
        # london_index_card.py's own curly()-via-_esc, correctly shipped
        # U+2019 — confirmed live, e.g. "Sir John Soane's Museum" in the alt
        # of https://bsky.app/profile/london-index.bsky.social/post/3muyhgkaasd2n.
        # The dateline is in the alt since 12 September 2026: with the
        # qualifier moved off the footnote and onto that line, leaving it
        # out would drop "within a mile of each town hall" for every
        # screen-reader user. bot_variety_check.py's masthead sweep reads
        # only "label: value" rows, and this line carries no ": ".
        alt = card_alt(c)
        ar = models.AppBskyEmbedDefs.AspectRatio(width=size[0], height=size[1])
        p1 = bsky.send_image(text='', image=image_bytes, image_alt=alt,
                             langs=['en'], image_aspect_ratio=ar)
        posted_uri = p1.uri
        root_ref = models.create_strong_ref(p1)
        parent_ref = root_ref

        # The spotlight's map: the borough filled, a one-mile circle around
        # its town hall, threaded between the card and the source link.
        # Chris's call, 12 September 2026. A failed map is logged and the
        # thread continues without it, since the card is already live; the
        # boundary file's licence terms ride the reply text (OGL v3, OS
        # Crown copyright), which is what lets the outlines be posted.
        if c.get('map_pin'):
            pin = c['map_pin']
            try:
                map_path = HERE / 'map.png'
                spot = (pin['lat'], pin['lng']) if pin.get('lat') is not None else None
                _, msize = card.render_borough_map(
                    pin['name'], spot, map_path, title=pin['name'],
                    caption=('The circle is one mile around the town hall, the area the figures cover'
                             if spot else ''))
                map_alt = (f"Map of Greater London’s 33 boroughs in outline with {pin['name']} "
                           f"filled in" + (", its town hall marked and a one-mile circle around it, "
                                           "the area the card’s figures cover." if spot else "."))
                mtb = client_utils.TextBuilder()
                mtb.text('Boundaries: ').link('Office for National Statistics',
                                              'https://geoportal.statistics.gov.uk/')
                mtb.text(', Open Government Licence v3.0. Contains OS data © Crown '
                         'copyright and database right 2024.')
                pm = bsky.send_image(text=mtb, image=map_path.read_bytes(), image_alt=map_alt,
                                     langs=['en'],
                                     reply_to=models.AppBskyFeedPost.ReplyRef(parent=root_ref, root=root_ref),
                                     image_aspect_ratio=models.AppBskyEmbedDefs.AspectRatio(
                                         width=msize[0], height=msize[1]))
                parent_ref = models.create_strong_ref(pm)
                print('Posted the borough map as a reply.')
            except Exception as e:  # noqa: BLE001 - the card is live; never let the map take the thread down
                print(f'Borough map failed ({type(e).__name__}: {e}); thread continues without it.',
                      file=sys.stderr)

        # A stored zone boundary (the Congestion Charge zone), same shape of
        # reply as the borough map: Chris's call, 12 September 2026. The
        # boundary is TfL's, via the London Datastore under the OGL, and the
        # outlines beneath it are the ONS's, so the reply credits both.
        if c.get('map_zone') == 'congestion_charge_zone':
            try:
                map_path = HERE / 'map.png'
                _, msize = card.render_zone_map(
                    card.load_zone(), map_path, title='The Congestion Charge zone',
                    caption='Boundary: TfL, via the London Datastore')
                map_alt = ('Map of central London with the Congestion Charge zone filled in red '
                           'over the borough outlines, the Thames running through it.')
                mtb = client_utils.TextBuilder()
                mtb.text('Zone boundary: TfL via the ').link('London Datastore', 'https://data.london.gov.uk/dataset/ultra-low-emissions-zone')
                mtb.text(', Open Government Licence. Borough outlines: ').link(
                    'Office for National Statistics', 'https://geoportal.statistics.gov.uk/')
                mtb.text(', OGL v3.0, contains OS data © Crown copyright and database right 2024.')
                pm = bsky.send_image(text=mtb, image=map_path.read_bytes(), image_alt=map_alt,
                                     langs=['en'],
                                     reply_to=models.AppBskyFeedPost.ReplyRef(parent=root_ref, root=root_ref),
                                     image_aspect_ratio=models.AppBskyEmbedDefs.AspectRatio(
                                         width=msize[0], height=msize[1]))
                parent_ref = models.create_strong_ref(pm)
                print('Posted the zone map as a reply.')
            except Exception as e:  # noqa: BLE001 - the card is live; never let the map take the thread down
                print(f'Zone map failed ({type(e).__name__}: {e}); thread continues without it.',
                      file=sys.stderr)

        # Just the link(s) - no "Source: " label, no period credit. Chris's
        # call, 31 August 2026: the explanation of what a card's numbers
        # mean now lives on the card itself as its footnote (see
        # compose.py), so the reply's only job left is a real, clickable
        # way to reach the data. This also drops period_credit from every
        # vein's reply, not just tfl_crowding's (which never carried one -
        # live picks always suppress it, see _is_live/_period_credit) - a
        # dated vein (police, cycle_hires, dcms_museums) loses that
        # disclosure here unless it's re-added to the card's own footnote
        # the same way context_note was.
        tb = client_utils.TextBuilder()
        for i, (name, url) in enumerate(c['sources']):
            if i:
                tb.text(' · ')
            tb.link(name, url)
        bsky.send_post(text=tb, reply_to=models.AppBskyFeedPost.ReplyRef(
            parent=parent_ref, root=root_ref), langs=['en'])
        print('\nPosted (thread: card' + (', map' if parent_ref is not root_ref else '')
              + ', source reply).')
    else:
        # curly() here too, for the same reason as the alt-text path above:
        # this text goes to Bluesky as a plain post, never through HTML, so
        # only the typographer's-quotes half applies. Added 9 September 2026 -
        # the alt-text fix on 8 September only touched the not-fallback
        # branch, leaving this rarer render-failure path shipping straight
        # apostrophes with nothing to catch it, since it fires only when
        # card.render_card() itself raises.
        body = f"{card.curly(c['opener']['text'])}\n"
        if c['dateline']:
            body += f"{card.curly(c['dateline'])}\n"
        body += '\n'.join(
            f"{card.curly(l['label'])}: {card.curly(l['value'])}" for l in c['lines'])
        body += f"\nSource: {card.curly(c['source_text'])}"
        if len(body) > MAX_POST_CHARS:
            sys.exit(f'Plaintext-fallback post too long ({len(body)} chars, max {MAX_POST_CHARS}).')
        p1 = bsky.send_post(text=body, langs=['en'])
        posted_uri = p1.uri
        print('\nPosted (plaintext fallback, render failed).')

    state = select_mod.update_state(state, sel)
    write_json_atomic(STATE, state, indent=2)
    log_card(c, posted_uri, HANDLE, fallback)


if __name__ == '__main__':
    # Gated on __name__, not installed at module level — this file is
    # imported by test suites, and mutating subprocess.run at import time
    # would leak into every other test sharing the process. See
    # api_call_log.py's own docstring. Covers london_index_harvest.py's
    # own curl() too, since it's imported by this file and subprocess.run
    # is one shared module-level attribute for the whole process.
    import api_call_log
    api_call_log.install('london_index_post.py')
    main()
