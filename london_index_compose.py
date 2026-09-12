#!/usr/bin/env python3
"""
Compose step for London Index: turn a selector's picks into the exact card
payload — opener, ordered lines, footnote, dateline, source credit and
hashtags — restating Python's own value strings, never the selector's.

A small version of Seoul Index's compose() by design (see the approved
posting-pipeline plan): no label-accuracy audit, no cross-vein masthead
logic, no label-dedup trimming. Those all exist in Seoul Index because a
specific measured failure showed up after weeks of real posting; London
Index has none of that history yet.

Public API:
    compose(sel, pool) -> dict with keys:
        opener, lines, footnote, dateline, source_text, source_url, tags
"""

from datetime import datetime, timezone, timedelta

LONDON_TZ = timezone(timedelta(hours=1))  # BST; fine for a first pass, no DST handling yet.

MAX_LINES = 4
MAX_FOOTNOTE_CHARS = 140


def _readable_period(p):
    """Turn a fact's raw `period` string into prose: "2026-06" -> "June
    2026", "2026-07-31" -> "31 July 2026", a bare "2026" stays as-is."""
    for fmt, out in (('%Y-%m-%d', '%-d %B %Y'), ('%Y-%m', '%B %Y')):
        try:
            return datetime.strptime(p, fmt).strftime(out)
        except ValueError:
            continue
    return p


def _is_live(picks):
    """True if ANY pick is a genuinely live "right now" reading (no period
    at all, or a period carrying a time-of-day component). Shared by
    _dateline and _period_credit so the two stay mutually exclusive — see
    both docstrings for why mixing them is actively misleading."""
    return any(f.get('period') is None or ':' in f['period'] for f in picks)


def _is_single_day(picks):
    """True if EVERY pick shares one period and it's a full calendar date
    (YYYY-MM-DD), not a month or year aggregate - daily_footfall's own
    shape, added 31 August 2026. Not "live" (nothing is happening right
    now), but it still names one specific day the way a live reading names
    one specific moment, so it earns the same card-level dateline instead
    of routing through the period credit on the source line the way a
    monthly or annual figure does. Mixed with a live pick or a differently
    dated one, this is deliberately False - a shared single-day dateline
    would misstate the picks that don't agree with it."""
    periods = {f.get('period') for f in picks}
    if len(periods) != 1:
        return False
    p = next(iter(periods))
    if not p:
        return False
    try:
        datetime.strptime(p, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def _is_period_aggregate(picks):
    """True if every pick shares one non-live, non-single-day period — a
    month or year aggregate, crime-by-month and cycle-hire totals being the
    current examples. Callers must check _is_live and _is_single_day first;
    this deliberately returns False for either, so the three stay mutually
    exclusive the same way _is_live and _is_single_day already are. A card
    whose picks DISAGREE on their period (a mixed multi-vein card, e.g. TfL
    bikes' live reading next to a dated cycle-hire total) is not an
    aggregate of one period and returns False here too — see
    _period_credit's own docstring for why a mixed period is credited on
    the source line instead of claimed as a single dateline."""
    periods = {f.get('period') for f in picks}
    return len(periods) == 1 and bool(next(iter(periods))) and not (
        _is_live(picks) or _is_single_day(picks))


def _period_credit(picks):
    """The real calendar period the picks cover, worded for the source
    credit line (e.g. "data.police.uk, June 2026; 31 July 2026") — never
    shown bare on the card itself, and never as today's date next to it.

    Suppressed entirely when ANY pick on the card is live (_is_live), even
    though a dated pick sitting alongside it still has a real period.
    Verified against a real card: TfL bikes (live) picked alongside
    cycle-hire totals (dated "2026-07-31") produced a credit reading
    "TfL BikePoint, 2026; 31 July 2026" — attached after the wrong source,
    since the credit line lists every source but the period only ever
    belonged to one of them. There is no clean way to attribute a period to
    one source out of several on one shared line, so a mixed card shows
    none at all rather than a misattributed one; the live dateline already
    anchors that kind of card well enough on its own. Also suppressed for
    _is_single_day and _is_period_aggregate, for the same reason: once
    every pick shares one period — a single day or a month/year aggregate
    — that date now rides the card's own dateline instead (see _dateline),
    and showing it twice is redundant in exactly the way a live "now"
    restated in the opener is. Only a genuinely MIXED set of periods still
    reaches this line, since that's the one case _dateline can't state as
    a single date without misattributing it."""
    if _is_live(picks) or _is_single_day(picks) or _is_period_aggregate(picks):
        return ''
    periods = {f['period'] for f in picks if f.get('period')}
    if not periods:
        return ''
    readable = sorted(_readable_period(p) for p in periods)
    return '; '.join(readable)[:MAX_FOOTNOTE_CHARS]


def _dateline(picks):
    """The card's masthead date — shown for a genuinely live "right now"
    reading (today's real date and time, since "now" needs an actual
    anchor nothing else on the card states), for a single dated day every
    pick shares (_is_single_day - that exact day, not today's date, since
    these figures are from a specific past day, not from now), OR for a
    month/year aggregate every pick shares (_is_period_aggregate - the real
    period itself, "June 2026", never today's date).

    That last case was added 2 September 2026, replacing a design that
    deliberately gave these cards no dateline at all and put the period in
    the opener instead ("Reported crimes in June 2026") on the theory that
    stating today's date next to June's figures would be a false claim.
    That theory was right but the fix was wrong: nothing here ever proposed
    showing TODAY's date on an aggregate card, only the real period, and a
    real card ("Reported crimes in June 2026" as a title, "Most: Camden" /
    "Fewest: Bromley" beneath it) showed the actual cost — the period
    crowded the title instead of sitting under it. So the period now rides
    the dateline, matching the single-day and live cases exactly, and the
    opener drops it (see SELECT_PROMPT). A card whose picks disagree on
    their period (_is_period_aggregate is False for those) still gets no
    dateline, and the mixed period still rides the source credit instead —
    see _period_credit."""
    if _is_live(picks):
        now = datetime.now(LONDON_TZ)
        ampm = 'a.m.' if now.hour < 12 else 'p.m.'
        return now.strftime(f'%-d %B at %-I:%M {ampm}')
    if _is_single_day(picks):
        p = next(iter({f['period'] for f in picks}))
        return datetime.strptime(p, '%Y-%m-%d').strftime('%-d %B %Y')
    if _is_period_aggregate(picks):
        p = next(iter({f['period'] for f in picks}))
        return _readable_period(p)
    return ''


def compose(sel, pool):
    by_id = {f['id']: f for f in pool}
    picks = [by_id[i] for i in sel['ids'] if i in by_id][:MAX_LINES]
    if len(picks) < 2:
        raise ValueError(f'compose() needs at least 2 valid picks, got {len(picks)}')

    lines = [{'label': f['label'], 'value': f['value']} for f in picks]

    # Credit every distinct source, in the order its first pick appears —
    # this is the reply's job, as a real clickable link per source. The
    # real calendar period (if any) rides along here too, never on the
    # card itself — see _period_credit and _dateline.
    seen = set()
    sources = []
    for f in picks:
        if f['source'] not in seen:
            seen.add(f['source'])
            sources.append((f['source'], f['url']))
    source_text = ' · '.join(name for name, _ in sources)
    period_credit = _period_credit(picks)
    if period_credit:
        source_text = f'{source_text}, {period_credit}'
    # What a "busiest"/"quietest"/ranked-list pick's number actually MEANS
    # and/or is busiest, quietest or highest-ranked OF - the card's own
    # footnote now, not the threaded reply (moved 31 August 2026: Chris's
    # call that the reply should carry nothing but a link, so any
    # explanation has to live somewhere the reader sees it without leaving
    # the post). All picks on a card share one vein under
    # APPLES_TO_APPLES_ONLY, so they carry the same context_note; take the
    # first that has one rather than require every pick to repeat it.
    # Truncated to MAX_FOOTNOTE_CHARS like _period_credit, in case a future
    # vein's note runs long - none currently does.
    context_note = next((f['context_note'] for f in picks if f.get('context_note')), None)
    footnote = context_note[:MAX_FOOTNOTE_CHARS] if context_note else ''

    # The qualifier rides the second line ahead of the date, Seoul Index's
    # convention for its ranked cards and Chris's call here, 12 September
    # 2026: "Within a mile of each town hall, July 2026". A card with a lead
    # but no date (a mixed-period card) shows the lead alone. Facts with no
    # lead render exactly as before.
    dateline = _dateline(picks)
    lead = next((f['dateline_lead'] for f in picks if f.get('dateline_lead')), None)
    if lead:
        dateline = f'{lead}, {dateline}' if dateline else lead

    return {
        'opener': sel['opener'],
        'lines': lines,
        'footnote': footnote,
        'dateline': dateline,
        'sources': sources,
        'source_text': source_text,
        'period_credit': period_credit,
        'primary_vein': picks[0]['vein'],
        'veins': sorted({f['vein'] for f in picks}),
    }


if __name__ == '__main__':
    # Manual check against fixed input, no network, no claude -p call.
    pool = [
        {'id': 'tfl_crowding:euston', 'vein': 'tfl_crowding',
         'label': 'Busiest station: Euston', 'value': '11% of typical', 'source': 'TfL live crowding',
         'url': 'https://api.tfl.gov.uk', 'period': None},
        {'id': 'tfl_crowding:bank', 'vein': 'tfl_crowding',
         'label': 'Quietest: Bank', 'value': '1% of typical', 'source': 'TfL live crowding',
         'url': 'https://api.tfl.gov.uk', 'period': None},
        {'id': 'tfl_bikes:available', 'vein': 'tfl_bikes',
         'label': 'Santander Cycles available now', 'value': '9,504', 'source': 'TfL BikePoint',
         'url': 'https://api.tfl.gov.uk/BikePoint', 'period': None},
    ]
    sel = {'opener': {'emoji': '🚇', 'text': 'London on the move right now'},
           'ids': [f['id'] for f in pool]}
    c = compose(sel, pool)
    print(f"{c['opener']['emoji']} {c['opener']['text']}")
    for l in c['lines']:
        print(f"  {l['label']}: {l['value']}")
    print(f"Source: {c['source_text']}")
    print(f"Dateline: {c['dateline']}")
