#!/usr/bin/env python3
"""
Entry point for London Index (@london-index.bsky.social). Orchestrates the
whole pipeline: harvest -> select (claude -p) -> compose -> render -> post,
then logs the result. See SESSION_SUMMARY.md and the approved posting-
pipeline plan for what this deliberately does NOT do yet (cross-vein
collisions, spotlight cards, rotation/cooldown/vein-floor/repeat-guard,
label-accuracy audit, bilingual threads) and why.

Posts a 2-post thread: the card image (caption is the hashtags only, so the
image stays visually first), then a reply with the clickable source
credit(s). Falls back to a plaintext post if rendering fails, so a post
always goes out.

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


def write_json_atomic(path, data, **dumps_kwargs):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, **dumps_kwargs))
    tmp.replace(path)


def tag_caption():
    return ' '.join(f'#{t}' for t in TAGS_FALLBACK)


TAGS_FALLBACK = ['LondonIndex']


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
    sel = select_mod.select(pool, state)
    c = compose_mod.compose(sel, pool)

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
        state['recent_ids'] = (state.get('recent_ids', []) + sel['ids'])[-select_mod.RECENT_IDS_KEEP:]
        write_json_atomic(STATE, state, indent=2)
        return

    password = keychain_password(HANDLE, KEYCHAIN_SERVICE)

    from atproto import Client, client_utils, models
    bsky = Client()
    bsky.login(HANDLE, password)

    posted_uri = None
    if not fallback:
        alt = f"{c['opener']['text']}\n" + '\n'.join(
            f"{l['label']}: {l['value']}" for l in c['lines'])
        if c['footnote']:
            alt += f"\n({c['footnote']})"
        ar = models.AppBskyEmbedDefs.AspectRatio(width=size[0], height=size[1])
        p1 = bsky.send_image(text=tag_caption(), image=image_bytes, image_alt=alt,
                             langs=['en'], image_aspect_ratio=ar)
        posted_uri = p1.uri
        root_ref = models.create_strong_ref(p1)

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
            parent=root_ref, root=root_ref), langs=['en'])
        print('\nPosted (2-post thread: card, source reply).')
    else:
        body = f"{c['opener']['text']}\n" + '\n'.join(
            f"{l['label']}: {l['value']}" for l in c['lines'])
        body += f"\nSource: {c['source_text']}\n{tag_caption()}"
        if len(body) > MAX_POST_CHARS:
            sys.exit(f'Plaintext-fallback post too long ({len(body)} chars, max {MAX_POST_CHARS}).')
        p1 = bsky.send_post(text=body, langs=['en'])
        posted_uri = p1.uri
        print('\nPosted (plaintext fallback, render failed).')

    state['recent_ids'] = (state.get('recent_ids', []) + sel['ids'])[-select_mod.RECENT_IDS_KEEP:]
    write_json_atomic(STATE, state, indent=2)
    log_card(c, posted_uri, HANDLE, fallback)


if __name__ == '__main__':
    main()
