#!/usr/bin/env python3
"""
Selection step for London Index: harvest a pool via london_index_harvest,
then ask `claude -p` to pick facts that read well together (2-4 in
single-vein mode, 3-4 once cross-vein pairing is turned back on — see
APPLES_TO_APPLES_ONLY below) and write a neutral opener. Python still owns
every number — the selector only orders and words; it never emits a value,
and compose() reuses the harvester's exact value string verbatim.

Deliberately NOT built here (see the approved posting-pipeline plan):
cross-vein collision detection. London Index had no posting history to
build rotation/cooldown/vein-floor against when this file was first
written — that changed 6 September 2026 (see apply_cooldown() and
promote_starved() below, ported from Seoul Index once 20 real posts showed
exactly the failure those exist to prevent: station_usage and
daily_footfall were two-thirds of every post while four other veins led
none).

Public API:
    build_pool(source=None) -> list[dict]
        Runs the harvesters in-process (no subprocess), same facts
        london_index_harvest.py prints, each tagged with a stable `id`.
    select(pool, state) -> {"opener": {"emoji": str, "text": str}, "ids": [str, ...]}
"""

import argparse
import collections
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import london_index_harvest as harvest

HERE = Path(__file__).parent
CLAUDE_MODEL = 'claude-sonnet-5'
CLAUDE_TIMEOUT = 90
RECENT_IDS_KEEP = 12
CLAUDE_TOKEN_ACCOUNT = 'londonbot'
CLAUDE_TOKEN_SERVICE = 'claude-oauth-token'


def claude_env():
    """The ambient CLI login is not enough for an unattended script call —
    see scan_filer.py's and Seoul Index's own claude_env() for the same
    lesson learned the hard way. Falls back to the plain environment if the
    Keychain entry is missing, so the caller's own error message (not a
    silent hang or an opaque auth failure) explains what to do."""
    env = os.environ.copy()
    r = subprocess.run(['security', 'find-generic-password', '-a', CLAUDE_TOKEN_ACCOUNT,
                        '-s', CLAUDE_TOKEN_SERVICE, '-w'], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        env['CLAUDE_CODE_OAUTH_TOKEN'] = r.stdout.strip()
    return env


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:40]


def build_pool(source=None):
    keys = [source] if source else sorted(harvest.HARVESTERS)
    pool = []
    errors = {}
    for key in keys:
        facts, err = harvest.HARVESTERS[key]()
        if err:
            errors[key] = err
            continue
        for f in facts:
            f['vein'] = key
            # A stable id for anti-repeat tracking: the harvester itself
            # assigns none, so one is derived from vein + label rather than
            # the value (which changes every run for live veins).
            f['id'] = f"{key}:{_slug(f['label'])}"
            pool.append(f)
    return pool, errors


# For now, every card is restricted to a single vein's own built-in
# comparison rather than a cross-vein pairing. Flip to False once there is
# enough posting history to judge whether a cross-vein pairing reads as a
# genuine comparison rather than a forced one — Chris's call, 29 August 2026.
APPLES_TO_APPLES_ONLY = True

_VEIN_RULE_SINGLE = """- SINGLE VEIN ONLY, for now. Pick 2 to 4 facts from ONE vein. Do NOT mix
  facts from different veins onto one card — a bike-dock count next to a
  crime count is not a comparison, however similar the two numbers look.
  Cross-vein pairings are reserved for once there is more posting history to
  judge them against; do not attempt one now even if a pairing looks
  tempting.
- PAIRS holds pre-detected sharp juxtapositions: Python has already found,
  for each vein, one or more of: the widest gap between its candidates (a
  "_gap" pair — the busiest station against the quietest, the fullest river
  against the driest), a genuine near-tie (a "_heat" pair — two candidates
  whose real values happen to land almost exactly together, out of a much
  larger set Python sampled but did not otherwise surface), or a ranked list
  of more than two entries (a "_top" group — e.g. the most congested tube
  stations right now, already sorted highest first). STRONGLY prefer
  building a card around one whole PAIR/group — that near-tie, wide gap or
  ranking IS the joke, and it is a real fact about the data, not a framing
  choice.
  - "_heat": do NOT call out the tie explicitly in the opener (no "Neck and
    neck", "Tied for the moment", "Dead heat", or similar) — reversed
    1 September 2026 after Chris flagged it directly on a live post
    ("Station usage, neck and neck" over Ruislip Gardens 825,357 vs
    Upminster Bridge 825,358): once two near-identical numbers sit side by
    side on the card, the coincidence is obvious on its own, and naming it
    in words on top of that is a redundant characterization, not
    information. Use a plain description of the vein instead, exactly as
    for "_gap"/"_top" below.
  - "_gap" and "_top" do not need that either: each fact's own label already says
    what the contrast is (whatever Python wrote it as — e.g. "Most above
    normal"/"Most below normal", never invent a punchier synonym like
    "Busiest"/"Quietest" the label doesn't say, since for some veins that
    would claim an absolute ranking the underlying data can't support — see
    tfl_crowding's own labels for why), and a "_top" group's own ranked
    order already says what the list is. A "_top" group is picked WHOLE,
    all of it, in the given order — never split or reordered, and never
    blended with that vein's own "_gap" facts onto the same card; pick one
    card shape or the other.
  - For any of these three, add 0-2 more facts from the same vein around a
    "_gap" or "_heat" pair only if they round the card out without diluting
    its contrast — a "_top" group already fills the card on its own.
  A vein offering more than one of "_gap"/"_heat"/"_top" is that many
  different possible cards, not one card with everything on it — pick
  whichever is the sharper unit for today and leave the rest for another
  day. A vein with nothing in PAIRS is still a legitimate pick on its own
  (2-4 of its facts), never padded out with a fact from a different vein to
  reach a count.
  - "_all": every fact of that vein shares the tag, meaning any 2 to 4 of
    them make a card together; there is no ranking or contrast to keep
    whole. Prefer the ones that read as one idea (a total and what happened
    to it, say) over four unrelated counts.
- Vein "tfl_journeys" facts without a pair (the all-modes total and its
  change on a year earlier) take an opener saying "Journeys on TfL" or
  similar; the card's second line already states the four-week period.
- Vein "house_prices" facts without a pair (London's average, its change on
  a year earlier, its change on the month) take an opener saying "House
  prices" or "London house prices" — nothing about "the market", and no
  adjective about direction; the values say which way it moved."""

_VEIN_RULE_CROSS = """- APPLES TO APPLES ONLY. Every pick's value must be the same KIND of
  measurement as the others — not just the same numeric shape (a percentage,
  a count), but actually comparable: a crowding percentage against another
  crowding percentage, a river's fullness against another river's, one
  borough's crime count against another borough's. "Comes from a different
  vein than the others" is NOT a reason to pick something, and is never
  worth it on its own. Concretely: start from ONE vein's own natural
  built-in comparison (crowding's busiest/quietest, rivers' fullest/driest,
  boroughs' most/fewest crime) as the anchor, and only add a fact from a
  different vein if its value is genuinely the same kind of thing as the
  anchor's, not merely a similar-looking number. A bad real example, do not
  repeat this shape: "Within a mile of central London: 4,449" (a crime
  count) + "Docking points across the scheme: 20,732" (a bike-dock count)
  + "Quietest: Bank: 5% of baseline" (a crowding percentage) + "Boroughs
  with a monitor: 33" (an air-quality count) under the opener "Around
  London" — four different KINDS of number from four veins, none of them
  actually comparable to any other despite three being nominally "counts",
  so the card reads as four random numbers rather than one idea.
- TWO MORE REAL FAILURES, from Seoul Index (its sibling bot, same
  mechanism) once its cross-vein pairing went live: a static, undated
  running total (library membership by age band) paired against a live,
  momentary headcount (crowd at a named spot) purely because the two
  magnitudes landed close together, two unrelated GROUPS of people whose
  counts happen to be similar sized are not thereby a comparison, and this
  shape slipped through TWICE. And a single day's figure (one station's
  boardings on one date) paired against a whole month's figures (a month
  of visitor totals) under one opener naming only the month, so the card
  silently implied the daily figure was also a month's total. Before ever
  pairing two veins, confirm both the SUBJECTS are actually comparable
  (not just the number) and that they cover the SAME TIME WINDOW, or say so.
- ACTIVELY LOOK FOR a genuine cross-vein pairing before settling for a
  single vein — a single-vein pick is a perfectly good fallback, never the
  default of first resort. "Same KIND of measurement" is broader than "same
  vein": a percentage-of-its-own-normal is the same kind of thing whether
  it is TfL crowding's "% of baseline" or a river's "% of range" — both
  answer "how full/busy is this relative to what's typical for it", so
  pairing London's busiest station against its fullest river is a
  legitimate, interesting cross-vein contrast, not a forced one. Only fall
  back to picking 3-4 facts from ONE vein when no cross-vein pairing in the
  pool is actually this kind of genuine match — never pick from only one
  vein merely because it is the easiest option."""

_PICK_COUNT = '2 to 4' if APPLES_TO_APPLES_ONLY else '3 to 4'

SELECT_PROMPT = """You are curating one post for London Index
(@london-index.bsky.social), a Harper's-Index-style Bluesky bot: short,
factual, dry. You are given POOL, a list of real facts already harvested
from live London data sources. Pick """ + _PICK_COUNT + """ facts that read well together as
one short set — a coherent theme, or a sharp contrast — and write ONE
neutral opener line for them.

Rules:
- Pick fact ids from POOL only. Never invent a fact or alter a value.
""" + (_VEIN_RULE_SINGLE if APPLES_TO_APPLES_ONLY else _VEIN_RULE_CROSS) + """
- Do not pick any id in AVOID_IDS if a reasonable alternative exists.
- The opener names no number and states no metric value itself — it sets
  the scene in as few words as possible, 2 to 5 words, short enough to sit
  on one line (e.g. "London on the move", "Trains, prices and pigeons").
  Prefer the shortest phrasing that still reads naturally; do not pad it out.
- NEVER say "this month" or "this week" or similar relative-to-today
  phrasing. Some sources lag today by weeks or months (a police fact's
  `period` might be "2026-06" while today is in August) — a relative
  phrase would be an outright false claim about when the figures are from.
  If every pick shares one `period` — a single calendar day, or a
  month/year aggregate like reported crime or cycle-hire totals — the card
  gets its own dateline stating the ACTUAL period INCLUDING THE YEAR
  (compose() builds this from the picks' own `period`, not you), so the
  opener must NOT also name it: just describe what's being measured, the
  same way vein "daily_footfall" already does ("Network footfall" alone,
  never "Network footfall, 22 August 2026", which repeats what the
  dateline states). This covers reported-crime facts too, added
  2 September 2026 after a real card's title read "Reported crimes in
  June 2026" — crowded, because the card had no dateline for a month
  aggregate at the time and the date had nowhere else to go. Say
  "Reported crime" now, with no date, and let the dateline carry "June
  2026" beneath it. Only when the picks genuinely DISAGREE on their period
  (a mixed card spanning more than one vein with different periods) does
  the card fall back to no dateline at all, and only then must the opener
  still name the actual period itself, so the card is never
  date-ambiguous if shared or screenshotted alone. For a live "right now"
  reading, do NOT add "now"/"right now"/", now" to the opener — the
  card's own timestamp ("29 August at 12:42 p.m.") already says so, and
  repeating it in the opener too is redundant, not merely harmless.
- The individual line labels do NOT repeat what the opener already states —
  a label like "Within a mile of central London" or "Most: Camden" assumes
  the opener has already said what is being measured. So when every pick
  shares one vein, the opener must be PRECISE about what that is, not just
  short: for reported-crime facts (vein "police" or "police_boroughs"), say
  "Reported crime" or similar (see the dateline rule above — no date in
  this line), never a vaguer "Crime" alone — the reader has no other way
  to know these are police-recorded reports, not verified or convicted
  crimes.
- For vein "daily_footfall", NEVER say "Tube" in the opener — this vein
  spans the whole network (Underground, Overground, DLR, Elizabeth line),
  not Underground alone, and "Tube" specifically means Underground to a
  London reader. A real example this rule exists because of: an opener
  read "Tube footfall, neck and neck" for a pick that included Woodgrange
  Park, which is Overground only. Say "network footfall" or similar
  instead — never invent a claim about which lines are involved that the
  picks themselves don't support.
- Pick one emoji for the opener, or "" for none. It must depict something
  concretely present in the picked facts (a train for a station, a bicycle
  for cycle hires, a police car for crime) — never a figurative or
  metaphorical stretch (scales of justice for "balance", a crystal ball for
  "outlook"). If no single fact suggests an obvious emoji, use "".

Reply with ONLY this JSON, nothing else:
{"opener": {"emoji": "...", "text": "..."}, "ids": ["...", "..."]}
"""

# Fixed openers for specific (vein, pair) card shapes, keyed by that pair —
# overridden deterministically in Python after the model call, never left to
# the model to reproduce exactly on every run. Same reasoning as select.py's
# own docstring on values ("Python still owns every number ... it never
# emits a value"), extended to the one card shape where the title itself
# needs to be exact rather than merely well-worded: a recurring, recognised
# format reads as a feature when its title is always the same, and as an
# inconsistency if it drifts run to run because a free-text instruction was
# followed closely rather than exactly. Chris's call, 31 August 2026, after
# seeing "Tube station crowding" and "Busiest tube stations" both used for
# the busiest/quietest shape across different runs. crowd_top added the
# same day, for the same reliability reason plus a second one: left to a
# free-text instruction, a run had already written "Busiest tube stations"
# for this exact shape — the same overclaim the crowd_gap labels themselves
# were just fixed to stop making (see harvest_tfl_crowding()), reintroduced
# through the one part of the card a label rename can't reach.
FIXED_OPENERS = {
    ('tfl_crowding', 'crowd_gap'): {'emoji': '🚇', 'text': 'The Tube right now'},
    ('tfl_crowding', 'crowd_top'): {'emoji': '🚇', 'text': 'Busier than usual right now'},
    # daily_footfall's two shapes went through an emoji-only override first
    # (the 🚇 emoji was judged fine even though the vein's own opener rule
    # forbids the WORD "Tube" in text, since the vein spans multiple modes
    # and a reader takes a pictograph as evocative shorthand rather than a
    # literal claim about which lines are included) — promoted to full
    # fixed openers the same day, Chris's own exact wording.
    ('daily_footfall', 'footfall_gap'): {'emoji': '🚇', 'text': 'Transport for London footfall'},
    ('daily_footfall', 'footfall_top'): {'emoji': '🚇', 'text': 'Transport for London: Busiest stations'},
    # Added 2 September 2026, alongside the dateline fix in compose.py's
    # _dateline(): this shape's opener used to carry the period itself
    # ("Reported crimes in June 2026"), which is now the card's dateline
    # instead (see SELECT_PROMPT). Fixed rather than left to free text for
    # the same reliability reason as the two pairs above — Chris's own
    # exact wording, seen on the real card that prompted the change.
    ('police_boroughs', 'police_gap'): {'emoji': '🚓', 'text': 'Reported crime'},
    # Added 3 September 2026, after a real card's opener read the generic
    # "Station usage" — accurate but not the claim the four ranked numbers
    # underneath it are actually making. Unlike daily_footfall, this vein
    # is filtered to Mode == 'LU' only (see harvest_station_usage), so
    # "Tube" is a true claim about which lines are covered, not the
    # overclaim it would be for daily_footfall's multi-mode figures. No
    # year in the text: these facts all share one `period` (the count
    # year), so compose()'s _dateline() already renders it beneath the
    # opener via _is_period_aggregate — repeating it here would be the
    # same redundancy the SELECT_PROMPT rule against restating the period
    # already forbids for every other fixed opener above.
    ('station_usage', 'usage_top'): {'emoji': '🚇', 'text': 'Busiest Tube stations'},
    # Added 12 September 2026 with the new borough card shapes and the four
    # new veins (see london_index_harvest.py). Every pair a vein can offer
    # gets a fixed title, for the reliability reason above: a shape that
    # recurs monthly should read as the same feature each time.
    ('police_boroughs', 'police_heat'): {'emoji': '🚓', 'text': 'Reported crime'},
    ('police_boroughs', 'police_top'): {'emoji': '🚓', 'text': 'Reported crime'},
    ('police_boroughs', 'police_change'): {'emoji': '🚓', 'text': 'Reported crime'},
    ('police_boroughs', 'police_types_top'): {'emoji': '🚓', 'text': 'Reported crime, by type'},
    ('police', 'central_top'): {'emoji': '🚓', 'text': 'Reported crime, central London'},
    ('stop_search', 'stops_all'): {'emoji': '🚓', 'text': 'Stop and search'},
    ('house_prices', 'hp_types_gap'): {'emoji': '🏠', 'text': 'House prices'},
    ('house_prices', 'hp_gap'): {'emoji': '🏠', 'text': 'House prices, by borough'},
    ('house_prices', 'hp_top'): {'emoji': '🏠', 'text': 'Most expensive boroughs'},
    # The comparison lives here, not on each row ("Biggest rise: Barking and
    # Dagenham"), his call 20 September 2026 on a live card that said "on a
    # year earlier" twice in two lines; the borough names say "by borough".
    ('house_prices', 'hp_change'): {'emoji': '🏠', 'text': 'House prices, change on a year earlier'},
    ('road_works', 'roads_all'): {'emoji': '🚧', 'text': 'Roadworks and disruptions'},
    ('lfb_animals', 'animals_top'): {'emoji': '🚒', 'text': 'Animal rescues by the fire brigade'},
    ('flood', 'flood_gap'): {'emoji': '🌊', 'text': 'Flood warnings and alerts'},
    ('rail_departures', 'rail_all'): {'emoji': '🚆', 'text': 'Trains from London’s stations'},
    ('rail_departures', 'rail_top'): {'emoji': '🚆', 'text': 'Busiest London train stations'},
    ('rail_departures', 'rail_ops_top'): {'emoji': '🚆', 'text': 'Trains running late, by operator'},
    # The seven London Datastore series, 12 September 2026.
    ('reservoirs', 'reservoir_all'): {'emoji': '💧', 'text': 'London’s reservoirs'},
    ('tfl_journeys', 'journeys_top'): {'emoji': '🚌', 'text': 'Journeys on TfL, by mode'},
    ('congestion_charge', 'ccz_all'): {'emoji': '🚗', 'text': 'The Congestion Charge zone'},
    ('police_strength', 'strength_all'): {'emoji': '🚓', 'text': 'Metropolitan Police staffing'},
    ('arrests', 'arrests_all'): {'emoji': '🚓', 'text': 'Arrests by the Metropolitan Police'},
    ('unemployment', 'jobless_all'): {'emoji': '', 'text': 'Unemployment'},
    ('lift_releases', 'lifts_all'): {'emoji': '🚒', 'text': 'People stuck in lifts'},
    ('lfb_incidents', 'lfb_all'): {'emoji': '🚒', 'text': 'The London Fire Brigade’s month'},
    ('events', 'events_all'): {'emoji': '🎭', 'text': 'On sale in London'},
    ('events', 'venues_top'): {'emoji': '🎭', 'text': 'Most performances, by venue'},
    # The two annual ticket-sales veins, 19 September 2026. No year in the
    # text: each shares one `period`, which _dateline() puts under the title.
    ('west_end', 'west_end_all'): {'emoji': '🎭', 'text': 'West End theatre'},
    ('london_cinema', 'cinema_all'): {'emoji': '🎬', 'text': 'London’s cinemas'},
    ('west_end_shows', 'shows_top'): {'emoji': '🎭', 'text': 'Longest-running West End shows'},
    # The three further cuts of SOLT's list, the same evening. The closed
    # card's title carries "closed" so its rows need not; the year cuts say
    # what they rank by, since their value column is a year. Under about
    # 44 characters, or the title wraps at this card's width.
    ('west_end_shows', 'shows_closed'): {'emoji': '🎭', 'text': 'Longest-running West End shows, now closed'},
    ('west_end_shows', 'shows_newest'): {'emoji': '🎭', 'text': 'Newest of the West End’s longest runs'},
    ('west_end_shows', 'shows_oldest'): {'emoji': '🎭', 'text': 'Oldest of the West End’s longest runs'},
}


# --- Spent facts: a figure is posted once per value -------------------
# Added 12 September 2026, the morning after the same borough card went out
# at 12:30 and 17:30 BST on 11 September, byte-identical (bsky.app/.../
# 3mvahvdld5f27 and .../3mvayox7dnd24). Of the 44 cards posted by then only
# 34 were distinct; the two crime cards alone were 9 of the last 12 posts,
# because data.police.uk is monthly and "Most: Camden" / "Fewest: Bromley" /
# "Most common: Other theft" are the extremes for the whole month. The only
# guard at fact level was AVOID_IDS, a soft instruction the model ignored
# both times once the pool had narrowed to four veins.
#
# The rule is the data's own: a fact already posted with this label AND this
# value is spent, and stays out of the pool until the value changes. A live
# vein's values change every run, so it is never spent; a monthly vein's
# facts are spent for the rest of the month, an annual vein's for the year.
# A pair group loses the WHOLE group if any member is spent, since a ranked
# list missing its top entry is a wrong card, not a shorter one. The
# history is card_history.jsonl, the record of what actually posted, never
# the state file. If nothing pickable survives, select() raises
# NothingFresh and the poster skips the slot: a missed slot is the lesser
# fault, and the one this bot had never once chosen over a repeat.
CARD_HISTORY = HERE / 'card_history.jsonl'


class NothingFresh(Exception):
    """Every fact left in the pool has already been posted at this value."""


def posted_lines(history_path=CARD_HISTORY):
    """The (label, value) of every line on every card ever posted, read from
    the card log. An unreadable line is skipped, never fatal: the log is
    append-only prose the poster writes best-effort."""
    seen = set()
    if not Path(history_path).exists():
        return seen
    for line in Path(history_path).read_text(encoding='utf-8').splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        for l in rec.get('lines') or []:
            if isinstance(l, dict) and 'label' in l and 'value' in l:
                seen.add((l['label'], l['value']))
    return seen


def drop_spent(pool, spent):
    """Remove every fact whose (label, value) is in `spent`, and every fact
    sharing a pair with one. Returns (fresh_pool, withheld_count)."""
    spent_pairs = {f['pair'] for f in pool
                   if f.get('pair') and (f['label'], f['value']) in spent}
    fresh = [f for f in pool
             if (f['label'], f['value']) not in spent
             and f.get('pair') not in spent_pairs]
    return fresh, len(pool) - len(fresh)


def pickable(pool):
    """True if some vein still has enough facts for a card."""
    counts = collections.Counter(f['vein'] for f in pool)
    return any(n >= STARVE_MIN_FACTS for n in counts.values())


def card_lines_key(lines):
    """The identity of a card for the final refusal in london_index_post.py:
    its lines, label and value, in order. The opener is left out on purpose
    (a fresh opener over the same figures is still the same card), as is the
    dateline (it is derived from the same picks)."""
    return tuple((l['label'], l['value']) for l in lines)


def posted_cards(history_path=CARD_HISTORY):
    """Every card ever posted, as card_lines_key() tuples."""
    keys = set()
    if not Path(history_path).exists():
        return keys
    for line in Path(history_path).read_text(encoding='utf-8').splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        lines = rec.get('lines') or []
        if lines and all(isinstance(l, dict) and 'label' in l and 'value' in l
                         for l in lines):
            keys.add(card_lines_key(lines))
    return keys


# Any vein that led a card within this many hours is withheld, on top of
# the two four-day groups below. Added 12 September 2026 with the spent
# filter above: that filter cannot stop a LIVE vein (whose values change
# every run) from leading three cards in one day once the static veins are
# spent, and a "Santander Cycles available now" card at 8:00, 12:30 and
# 17:30 is the same card to a reader whatever the numbers did. 20 hours,
# not 24, so a vein that led the 8:00 p.m. slot is free again for 5:30 p.m.
# the next day. Same abandonment rule as every cooldown here: if withholding
# would leave nothing pickable, it is not applied.
GENERAL_COOLDOWN_HOURS = 20


def recently_led(state, hours=GENERAL_COOLDOWN_HOURS):
    """The veins stamped in vein_last_at within the last `hours`."""
    out = set()
    now = datetime.now(timezone.utc)
    for vein, stamp in (state.get('vein_last_at') or {}).items():
        try:
            age = now - datetime.fromisoformat(stamp)
        except (ValueError, TypeError):
            continue
        if age < timedelta(hours=hours):
            out.add(vein)
    return out


# --- Vein rotation: cooldowns + starve-floor --------------------------
# Ported from Seoul Index's apply_cooldown()/promote_starved() (same file,
# same names, same mechanism) and simplified for London Index's much
# smaller 10-vein roster at the same 4-posts-a-day cadence. Built
# 6 September 2026 after two live posts, 16 hours apart
# (bsky.app/.../3muppich4zm27 and .../3murf3zphbj2x — a daily_footfall and
# a station_usage "busiest station" card), read to a follower as the same
# card twice: with tfl_crowding paused, those two veins alone were
# two-thirds of the preceding 15 posts, while tfl_bikes, flood, police and
# cycle_hires led none of them. Chris's call: build the full two-part
# machinery now, on purpose more than this vein count strictly needs, so
# there's headroom to grow into rather than revisiting this at 20+ veins.

# station_usage and daily_footfall are two different data sources
# answering the same reader-facing question ("which station is busiest")
# — one theme, not two — so they share a single cooldown: leading with
# EITHER one holds BOTH out of the pool. A per-vein cooldown alone would
# have let the bot alternate between them and still post a "busiest
# station" card every single day.
BUSIEST_STATION_VEINS = {'station_usage', 'daily_footfall'}
# Raised 2 -> 4 on 8 September 2026: 2 days was not enough. station_usage is
# ANNUAL data (TfL's Annual Station Counts, same shape as dcms_museums below)
# so a repick past the cooldown reproduces the identical top-4 list every
# time, and daily_footfall runs ~9 days behind TfL's own publication (see
# london_index_harvest.py's docstring), so it can sit on the same lagged day
# across a 2-day gap too. Three exact-repeat cards were found on the real
# feed once bot_variety_check.py was pointed at this bot: "Busiest Tube
# stations" (station_usage) 2d8h apart, "Transport for London: Busiest
# stations" (daily_footfall) 2d8h apart, "Transport for London footfall"
# (daily_footfall) 2d21h apart — every one of them just past the old 2-day
# window. 4 days clears all three with margin, and matches
# DCMS_MUSEUMS_COOLDOWN_DAYS below for the same reason: both veins are
# static-or-near-static data where a short cooldown only delays the repeat
# rather than preventing it.
BUSIEST_STATION_COOLDOWN_DAYS = 4

# Every other vein gets the opposite guard: gone quiet for STARVE_DAYS and
# the pool is narrowed to that vein alone, so the model can't pick around
# it. STARVE_MIN_FACTS=2 matches select()'s own single-vein minimum — a
# vein below it can never form a valid card at all. flood is excluded from
# promotion this way without needing a hardcoded name (Seoul Index's
# 'rush' needed one): harvest_flood() always returns exactly one fact, so
# it never clears this floor and stays out of rotation until its harvester
# grows a second, comparable figure — a real, separate limitation, not
# something this change fixes.
STARVE_MIN_FACTS = 2
STARVE_DAYS = 2
SEVERE_STARVE_DAYS = STARVE_DAYS * 2  # unused for now — see promote_starved()'s docstring

# dcms_museums is DCMS's own annual release (next update not expected until
# 2027, per the harvester's own docstring) — unlike every other vein here, a
# repeat pick of the same PAIR reproduces a BYTE-IDENTICAL card, not just a
# repeat of the same theme. Added 8 September 2026 after exactly that
# happened: the museum_gap pair (British Museum / Sir John Soane's Museum /
# all-London total) led a post on 5 September at 16:04 and again on 8
# September at 16:04, with a third dcms_museums post (a different pair,
# museum_heat) on 7 September in between — one vein, three times in four
# days. It was never added to the busiest-station cooldown above, and
# recent_ids (soft advisory only, 12 slots) had long aged past it by the
# third post. Own cooldown group of one, same mechanism as
# BUSIEST_STATION_VEINS; 4 days is chosen to exceed the 3-day gap that
# produced the actual duplicate.
DCMS_MUSEUMS_VEINS = {'dcms_museums'}
DCMS_MUSEUMS_COOLDOWN_DAYS = 4


def apply_cooldown(pool, state, veins, days, label):
    """Drop `veins` from the pool if any of them led a post within the last
    `days` days. The group form (a set, not just one vein) exists for
    BUSIEST_STATION_VEINS, where the reader-facing repetition spans two
    different data sources rather than one.

    Two deliberate refusals to fire, both from Seoul Index's version: an
    unreadable or missing timestamp holds no cooldown (never invent one
    from a hand-edited or pre-migration state file), and a cooldown that
    would leave nothing pickable — no remaining vein with at least 2 facts
    — is abandoned rather than emptying the pool and skipping the post.
    """
    stamps = state.get('vein_last_at', {})
    newest_age = None
    for v in veins:
        stamp = stamps.get(v)
        if not stamp:
            continue
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(stamp)
        except (ValueError, TypeError):
            continue
        if newest_age is None or age < newest_age:
            newest_age = age
    if newest_age is None or newest_age >= timedelta(days=days):
        return pool
    cooled = [f for f in pool if f['vein'] not in veins]
    remaining = collections.Counter(f['vein'] for f in cooled)
    if not any(n >= 2 for n in remaining.values()):
        return pool
    hours = int(newest_age.total_seconds() // 3600)
    print(f'{label} on cooldown ({hours}h of {int(round(days * 24))}h) - '
          f'{len(pool) - len(cooled)} fact(s) withheld.')
    return cooled


def promote_starved(pool, state):
    """Give a long-unposted vein one card to itself.

    Mirrors Seoul Index's promote_starved(), minus the never-posted/severe-
    starve back-to-back override that file's own comment says is needed
    only once the roster is big enough (26 veins there) that an even
    rotation leaves most veins nominally starved most of the time. At 10
    veins and STARVE_DAYS=2, that isn't London Index's situation yet — a
    plain oldest-or-never-posted-first pick is enough, and SEVERE_STARVE_
    DAYS is defined above only so a future widening of the roster has the
    same escape hatch ready without re-deriving it.

    Returns (pool, promoted_vein), with promoted_vein None when nothing is
    promoted and the pool handed back untouched.
    """
    counts = collections.Counter(f['vein'] for f in pool)
    seen = state.get('vein_last_at') or {}
    now = datetime.now(timezone.utc)
    starved = []
    for vein, n in counts.items():
        if n < STARVE_MIN_FACTS:
            continue
        stamp = seen.get(vein)
        age = None
        if stamp:
            try:
                age = now - datetime.fromisoformat(stamp)
            except (ValueError, TypeError):
                age = None
        if age is None or age >= timedelta(days=STARVE_DAYS):
            starved.append((age, vein, n))
    if not starved:
        return pool, None

    # Never-posted first, then longest-waited first, then alphabetical —
    # the last only to make ties (e.g. every vein "never posted" on the
    # very first run after this shipped) deterministic rather than an
    # accident of dict iteration order.
    starved.sort(key=lambda t: (t[0] is not None,
                                -(t[0].total_seconds() if t[0] else 0), t[1]))
    age, vein, n = starved[0]
    waited = 'never posted' if age is None else f'{age.days}d since last led'
    others = ', '.join(v for _, v, _ in starved[1:]) or 'none'
    print(f'Vein floor: promoting {vein} ({waited}); this card is built '
          f'from its {n} facts alone. Also starved: {others}.')
    return [f for f in pool if f['vein'] == vein], vein


def update_state(state, sel):
    """Record one pick into state: `recent_ids` (the existing fact-level
    anti-repeat) and, when the pick is a single vein — the only shape
    APPLES_TO_APPLES_ONLY currently allows — `vein_last_at` (read by
    apply_cooldown() and promote_starved() above). A mixed-vein pick stamps
    no vein, since there is no single vein to credit for it.

    Shared by london_index_post.py's live save point and by this file's own
    main(), so the two state fields can't drift out of sync the way separate
    inline updates risked. A --dry-run in either writes nothing, since
    12 September 2026.
    """
    state['recent_ids'] = (state.get('recent_ids', []) + sel['ids'])[-RECENT_IDS_KEEP:]
    if sel.get('vein'):
        vein_last_at = state.setdefault('vein_last_at', {})
        vein_last_at[sel['vein']] = datetime.now(timezone.utc).isoformat()
    return state


def select(pool, state, history_path=CARD_HISTORY):
    # Spent facts go first, so every later guard judges only what could
    # actually be posted: a cooldown abandoned "because nothing else is
    # pickable" must not be abandoned on the strength of facts that are
    # about to be dropped anyway.
    pool, withheld = drop_spent(pool, posted_lines(history_path))
    if withheld:
        print(f'{withheld} fact(s) already posted at this value - withheld.')
    if not pickable(pool):
        raise NothingFresh('every fact still in the pool has already been '
                           'posted at this value; nothing fresh to post')
    pool = apply_cooldown(pool, state, BUSIEST_STATION_VEINS,
                          BUSIEST_STATION_COOLDOWN_DAYS, 'Busiest-station cards')
    pool = apply_cooldown(pool, state, DCMS_MUSEUMS_VEINS,
                          DCMS_MUSEUMS_COOLDOWN_DAYS, 'DCMS museums')
    recent = recently_led(state)
    if recent:
        pool = apply_cooldown(pool, state, recent, GENERAL_COOLDOWN_HOURS / 24,
                              'Veins that led within the day')
    pool, _promoted = promote_starved(pool, state)

    avoid = state.get('recent_ids', [])[-RECENT_IDS_KEEP:]
    slim = [{'id': f['id'], 'vein': f['vein'], 'label': f['label'],
             'value': f['value'], 'period': f.get('period'),
             'pair': f.get('pair')} for f in pool]
    pairs = {}
    for f in pool:
        if f.get('pair'):
            pairs.setdefault(f['pair'], []).append(f['id'])
    payload = {'POOL': slim, 'PAIRS': pairs, 'AVOID_IDS': avoid}
    prompt = SELECT_PROMPT + '\n\n' + json.dumps(payload, ensure_ascii=False)

    attempts = 3
    for attempt in range(attempts):
        last = attempt == attempts - 1
        try:
            # ⚠️ --restricted --tools "": no tools at all, since 11 September
            # 2026, same as Seoul Index's selector (its CONFINED comment carries
            # the incident). This is text in, JSON out, and needs no tool;
            # unconfined, `claude -p` is an agent with Bash in this Mac's home
            # directory. --restricted also ignores the user's settings files,
            # so no hook fires from inside a scheduled post. stdin=DEVNULL
            # because the CLI otherwise waits three seconds for stdin on every
            # hand-run call.
            r = subprocess.run(['claude', '-p', '--restricted', '--tools', '',
                                '--model', CLAUDE_MODEL, prompt],
                               capture_output=True, text=True, env=claude_env(),
                               stdin=subprocess.DEVNULL, timeout=CLAUDE_TIMEOUT)
        except subprocess.TimeoutExpired:
            if last:
                raise RuntimeError(f'claude -p timed out after {CLAUDE_TIMEOUT}s, {attempts} times')
            continue
        if r.returncode != 0:
            err = (r.stderr or r.stdout or '').strip() or '(no output)'
            if last:
                raise RuntimeError(f'claude -p failed (exit {r.returncode}): {err}')
            time.sleep(5 * (attempt + 1))
            continue
        text = re.sub(r'^```[a-z]*\n?|\n?```$', '', r.stdout.strip()).strip()
        try:
            sel = json.loads(text)
        except json.JSONDecodeError:
            if last:
                raise RuntimeError(f'claude -p returned invalid JSON: {text[:200]!r}')
            continue
        valid_ids = {f['id'] for f in pool}
        sel['ids'] = [i for i in sel.get('ids', []) if i in valid_ids][:4]
        min_ids = 2 if APPLES_TO_APPLES_ONLY else 3
        if len(sel['ids']) >= min_ids:
            by_id = {f['id']: f for f in pool}
            picks = [by_id[i] for i in sel['ids']]
            veins = {f['vein'] for f in picks}
            pairs = {f.get('pair') for f in picks}
            if len(veins) == 1:
                sel['vein'] = next(iter(veins))
            if len(veins) == 1 and len(pairs) == 1:
                fixed = FIXED_OPENERS.get((sel['vein'], next(iter(pairs))))
                if fixed:
                    sel['opener'] = fixed
            # A title Python set on the facts themselves (the spotlight
            # borough's name) wins over the table and the model alike, when
            # every pick carries the same one. Added 12 September 2026.
            carried = {json.dumps(f.get('fixed_opener'), sort_keys=True) for f in picks}
            if len(carried) == 1:
                fo = picks[0].get('fixed_opener')
                if fo:
                    sel['opener'] = fo
            return sel
        if last:
            raise RuntimeError(f'claude -p picked too few valid ids: {sel.get("ids")}')

    raise RuntimeError('select() exhausted retries without a valid pick')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--dry-run', action='store_true', help='harvest + select + print, no side effects')
    ap.add_argument('--source', choices=sorted(harvest.HARVESTERS), help='one vein only')
    args = ap.parse_args()

    pool, errors = build_pool(args.source)
    if errors:
        print(f'{len(errors)} source(s) failed: {list(errors)}', file=sys.stderr)
    if not pool:
        sys.exit('No facts harvested; nothing to select from.')

    state_path = HERE / 'london_index_state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    sel = select(pool, state)
    by_id = {f['id']: f for f in pool}
    print(f"Opener: {sel['opener']['emoji']} {sel['opener']['text']}".strip())
    for i in sel['ids']:
        f = by_id[i]
        print(f"  [{f['vein']}] {f['label']}: {f['value']}")
    if not args.dry_run:
        state = update_state(state, sel)
        state_path.write_text(json.dumps(state, indent=2))


if __name__ == '__main__':
    main()
