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

import re
from datetime import date, datetime, timezone, timedelta

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


def _mixed_period_day(picks):
    """When the picks' periods genuinely disagree — not live, not a shared
    single day, not a shared month/year aggregate — but exactly one
    distinct DAY-LEVEL period appears among them, return it: the more
    specific date, used to anchor the dateline even though a companion
    pick (a running average, say) covers a different span.

    Chris's call, 18 September 2026, after the "Cycle hire in London" card
    (cycle_hires: a same-day count next to a "2026 to date" average)
    shipped with no dateline at all, so the day the count was FOR sat only
    in a small italic footnote below the rows —
    https://bsky.app/profile/london-index.bsky.social/post/3mvqfhjc3wh24.
    His rule: a card's date belongs on the second line under the title,
    not buried in the footnote.

    Two or more distinct day-level periods (or none at all — two mixed
    months, say) return None, and the card falls back to the older mixed
    behaviour: no dateline, the disagreement stated on the source line
    instead (_period_credit) — picking one day over an equally-specific
    other day, or promoting a day over a genuinely different kind of
    period, would misattribute it."""
    days = {f['period'] for f in picks if f.get('period') and _period_unit(f['period']) == 'date'}
    return next(iter(days)) if len(days) == 1 else None


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
    restated in the opener is. And suppressed for _mixed_period_day, added
    18 September 2026 for the same reason: once one distinct day-level
    period anchors the dateline, restating it here (or beside the other,
    less specific period it disagrees with) is the same redundancy. Only a
    set of periods _mixed_period_day can't resolve to one day still reaches
    this line."""
    if _is_live(picks) or _is_single_day(picks) or _is_period_aggregate(picks) or _mixed_period_day(picks):
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
    these figures are from a specific past day, not from now), for a
    month/year aggregate every pick shares (_is_period_aggregate - the real
    period itself, "June 2026", never today's date), OR for a genuinely
    mixed set of periods that still resolves to one distinct day-level
    period among them (_mixed_period_day — the day-level pick's own date,
    even though a companion pick covers a different span).

    That last case was added 18 September 2026: his rule, stated plainly
    after seeing the "Cycle hire in London" card carry no dateline at all —
    a card's date belongs on the second line under the title, in cards
    like https://bsky.app/profile/london-index.bsky.social/post/3mvqfhjc3wh24,
    never buried in the footnote alone. The more-specific date wins; the
    less-specific companion period (an average "to date", say) is left to
    its own line or a trimmed footnote rather than crowding the dateline
    with two disagreeing dates.

    The earlier month/year-aggregate case was added 2 September 2026,
    replacing a design that deliberately gave these cards no dateline at
    all and put the period in the opener instead ("Reported crimes in June
    2026") on the theory that stating today's date next to June's figures
    would be a false claim. That theory was right but the fix was wrong:
    nothing here ever proposed showing TODAY's date on an aggregate card,
    only the real period, and a real card ("Reported crimes in June 2026"
    as a title, "Most: Camden" / "Fewest: Bromley" beneath it) showed the
    actual cost — the period crowded the title instead of sitting under
    it. So the period now rides the dateline, matching the single-day and
    live cases exactly, and the opener drops it (see SELECT_PROMPT). A card
    whose picks disagree on their period AND resolve to no single day-level
    period (two mixed months, say) still gets no dateline, and the mixed
    period still rides the source credit instead — see _period_credit."""
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
    day = _mixed_period_day(picks)
    if day:
        return datetime.strptime(day, '%Y-%m-%d').strftime('%-d %B %Y')
    return ''


def _period_unit(p):
    """The DISPLAY unit for a fact's raw `period` string, for _latest_note()
    alone: 'date' for 'YYYY-MM-DD', 'month' for 'YYYY-MM', 'year' for a bare
    'YYYY' or a UK financial-year label ('2024-25', DCMS's own shape for
    museum_facts -- the year it starts, a dash, the last two digits of the
    year it ends). None for anything else.

    A financial year has the exact same 7-character shape as 'YYYY-MM', so
    it must be told apart by more than length: '2024-25' as a month fails
    strptime (25 isn't one), and only then is it tried as a financial year.
    Before this existed, _latest_note() picked its unit from len(p) alone,
    which called the British Museum's "2024-25" a month in a live post, 14
    September 2026, since a financial year has that same 7-character shape.

    Deliberately NOT used by _period_end()/_is_stale(): a financial year's
    true end date is somewhere in the following March, not a plain calendar
    year end, and staleness has always treated an unrecognised shape like
    this one as worth naming regardless -- correct here by accident, but
    safer to leave alone than to teach the freshness math a fiscal year's
    real boundary for no evidenced need."""
    if len(p) == 10:
        try:
            datetime.strptime(p, '%Y-%m-%d')
            return 'date'
        except ValueError:
            return None
    if len(p) == 7:
        try:
            datetime.strptime(p, '%Y-%m')
            return 'month'
        except ValueError:
            pass
        m = re.fullmatch(r'(\d{4})-(\d{2})', p)
        if m and int(m.group(2)) == (int(m.group(1)) + 1) % 100:
            return 'year'
        return None
    if len(p) == 4 and p.isdigit():
        return 'year'
    return None


def _period_end(p):
    """Parse a fact's raw `period` string into (end_date, unit) for
    _is_stale(): 'YYYY-MM-DD' -> a date, 'date'; 'YYYY-MM' -> the 1st of
    that month, 'month'; a bare 'YYYY' -> 1 January that year, 'year'. None
    for anything else (a mixed/unrecognised shape -- including a financial
    year like '2024-25', see _period_unit()), which _latest_note() treats
    as always worth naming, matching its pre-13-September behaviour."""
    if len(p) == 10:
        try:
            return datetime.strptime(p, '%Y-%m-%d').date(), 'date'
        except ValueError:
            return None
    if len(p) == 7:
        try:
            return datetime.strptime(p, '%Y-%m').date(), 'month'
        except ValueError:
            return None
    if len(p) == 4 and p.isdigit():
        return date(int(p), 1, 1), 'year'
    return None


def _is_stale(p, now=None):
    """True when the real period `p` ends more than one degree removed
    from today's own, necessarily-incomplete day/month/year: a fresher
    period of the same kind could, in principle, already exist. False when
    it's already as fresh as a period of its kind can possibly be
    (yesterday for a date, last calendar month for a month, last calendar
    year for a year) -- the case _latest_note() drops its sentence for,
    Chris's call, 13 September 2026: saying "the latest" is trivial when a
    period is plainly, unavoidably the newest that could exist yet.
    Unrecognised shapes are treated as stale (the note is kept), since
    there's nothing here to say it's trivially fresh."""
    parsed = _period_end(p)
    if not parsed:
        return True
    end, unit = parsed
    if now is None:
        now = datetime.now(LONDON_TZ).date()
    if unit == 'date':
        return (now - end).days > 1
    if unit == 'month':
        return (now.year - end.year) * 12 + (now.month - end.month) > 1
    return now.year - end.year > 1


def _latest_note(picks, dateline_text):
    """One sentence for the footnote saying the period on the second line
    is the newest the publisher has: "June 2026 is the latest month for
    which data is available." Chris's call, 12 September 2026, made first
    for Seoul Index's bus cards and then every dated card on both accounts,
    since a card cites a day, month or year some way behind the calendar
    and nothing on it said why. Stated as a rule rather than a lag count,
    so it stays true on the morning a harvest stalls. Every dated vein
    reads its source's newest published period (see README's table), which
    is what makes the sentence true by construction. Empty for a live card
    (the clock on the second line is now) and for a mixed-period card,
    which has no single period to name.

    A spelled-out period (dateline_text) is restated as it stands, except
    TfL's "Four weeks, 28 June to 25 July 2026", which reads as a sentence
    only turned round: "The four weeks to 25 July are the latest period
    for which data is available". Capital T and a plural verb, his call,
    22 September 2026, on the live card of that day; the year goes for the
    reason below. No full stop, since footnotes on this account carry none
    (see MUSEUM_NOTE_GROUP); compose() joins it to the context note with a
    middle dot.

    Narrowed 13 September 2026, his call: dropped entirely when the real
    period (`p`, whatever the displayed dateline_text says) is no more
    than one degree removed from today's own, still-incomplete day/month/
    year -- see _is_stale(). Saying "the latest" is trivial when a period
    is plainly, unavoidably the newest that could exist yet.

    A month or a day drops its YEAR, his call, 20 September 2026: "July is
    the latest month for which data is available" under a second line
    already reading "July 2026" (a live house-prices card that day said
    "July 2026" twice, two lines apart). TfL's four weeks followed on
    22 September ("the four weeks to 25 July 2026" under "28 June to
    25 July 2026", the same duplication). A bare year has nothing else to
    say, and any other spelled-out dateline_text is restated as the
    publisher gives it, so neither changes.
    """
    if _is_live(picks):
        return ''
    periods = {f.get('period') for f in picks}
    p = next(iter(periods)) if len(periods) == 1 else None
    if p and not _is_stale(p):
        return ''
    if dateline_text:
        if dateline_text.startswith('Four weeks, ') and p and _is_single_day(picks):
            return (f'The four weeks to {_period_sans_year(p)} are the latest period '
                    'for which data is available')
        return f'{dateline_text} is the latest period for which data is available'
    if not p:
        return ''
    if _is_single_day(picks):
        return f'{_period_sans_year(p)} is the latest date for which data is available'
    if _is_period_aggregate(picks):
        unit = _period_unit(p) or 'period'
        return f'{_period_sans_year(p)} is the latest {unit} for which data is available'
    return ''


def _period_sans_year(p):
    """_readable_period() without the year, for _latest_note() alone:
    "2026-07" -> "July", "2026-07-31" -> "31 July". Anything else (a bare
    year, a financial year) is returned as _readable_period() gives it,
    since there the year IS the period."""
    for fmt, out in (('%Y-%m-%d', '%-d %B'), ('%Y-%m', '%B')):
        try:
            return datetime.strptime(p, fmt).strftime(out)
        except ValueError:
            continue
    return _readable_period(p)


def compose(sel, pool):
    by_id = {f['id']: f for f in pool}
    picks = [by_id[i] for i in sel['ids'] if i in by_id][:MAX_LINES]
    if len(picks) < 2:
        raise ValueError(f'compose() needs at least 2 valid picks, got {len(picks)}')

    # A row's own 'emoji' rides through only when a vein set one on the
    # fact — see fact()'s docstring for why animals_top is currently the
    # only vein that does; every other line renders exactly as before.
    lines = [{'label': f['label'], 'value': f['value'],
             **({'emoji': f['emoji']} if f.get('emoji') else {})} for f in picks]

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
    # A spelled-out period the facts agree on ("Four weeks to 25 July 2026")
    # replaces the derived one; a disagreement means a mixed card, which
    # keeps the derived (mixed, so empty) dateline. Added 12 September 2026
    # for TfL's four-week periods and the ONS rolling quarter.
    texts = {f.get('dateline_text') for f in picks}
    dateline_text = next(iter(texts)) if len(texts) == 1 else None
    if dateline_text:
        dateline = dateline_text
    lead = next((f['dateline_lead'] for f in picks if f.get('dateline_lead')), None)
    if lead:
        dateline = f'{lead}, {dateline}' if dateline else lead
    # The footnote ends by saying that period is the newest published
    # (see _latest_note); it follows the context note after a middle dot,
    # past the cap, since a sentence cut mid-word is worse than a long
    # footnote.
    latest = _latest_note(picks, dateline_text)
    if latest:
        footnote = f'{footnote} · {latest}' if footnote else latest

    return {
        'opener': sel['opener'],
        'lines': lines,
        'footnote': footnote,
        'dateline': dateline,
        'sources': sources,
        'source_text': source_text,
        'period_credit': period_credit,
        # A borough to highlight on a threaded map reply, when the facts
        # ask for one (see fact()'s map_pin). Added 12 September 2026.
        'map_pin': next((f['map_pin'] for f in picks if f.get('map_pin')), None),
        'map_zone': next((f['map_zone'] for f in picks if f.get('map_zone')), None),
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
