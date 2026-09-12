# London Index — session summary (29 August 2026)

Sister project to Seoul Index: a Harper's-Index-style Bluesky bot for London,
built from open data. This session did the scouting, harvest layer, and
avatar — no posting pipeline exists yet.

## What's built and working

**`london_index_harvest.py`** — 8 veins, all verified against live data, no
fabricated numbers:
- `tfl_bikes` — Santander Cycles availability (BikePoint)
- `tfl_crowding` — live footfall at 12 curated stations vs typical baseline
  (`/crowding/{naptanId}/Live`, undocumented endpoint)
- `flood` — active EA flood warnings/alerts
- `river_levels` — 6 curated London gauges vs their own typical range
- `police` — central London crime, latest available month (data.police.uk)
- `police_boroughs` — 8 curated boroughs compared, crimes/mile of town hall
- `cycle_hires` — daily hire counts from London Datastore's own XLSX
- `laqn` — highest current air quality reading, London Air Quality Network

Run: `python3 london_index_harvest.py` (full pool) or `--source <name>`.
Last full run: 17 facts, zero errors.

**TfL API key** — subscribed via api-portal.tfl.gov.uk ("500 Requests per
min" product, bundles all TfL APIs). Stored in Keychain:
`security find-generic-password -a "london-index" -s "tfl-api-key" -w`.
Wired into the harvester (`tfl_get_json()`), falls back to key-free/slower
mode if the Keychain entry goes missing. **Gotcha that cost real time**: TfL
returns HTTP 429 for an invalid key too — it's not always a rate limit,
check the response body ("Invalid app_key is provided."). The first attempt
failed because the Profile page's primary and secondary keys got pasted
together into one 66-character string; a real key is 32 hex characters.

**Avatar** — `london_index_avatar.svg`, now at v14. Went through many
directions before landing: several Big Ben silhouette attempts (rejected,
never read as recognisable), the bare clock face (rejected — didn't say
"London"), back to full silhouette (still rejected), then a full pivot to
**the Underground roundel** — the existing 40-digit ring (matching Seoul
Index's own avatar motif) doubling as the roundel's circle, crossed by a bar
reading "LONDON INDEX". This landed well. Current state: cream background,
digits and bar text both 38pt/weight 800, ring re-spaced to 10° increments
(30 digits, gaps left empty where the bar crosses, checked with margin not
guessed), colour `#2c4c70` — a **visual estimate** (not a pixel sample) of a
blend between a photo's sky and Thames water the user shared. Also exists:
`london_avatar_nameonly.svg` (bar reads "LONDON" only, same ring/style).

**Sample post mockups** — `sample_card_1/2/3.png` (+ `.html` sources), built
from real pool numbers (transport, borough crime, rivers). These are
mockups only — no real card-composition/line-fitting logic like Seoul
Index's `seoul_index_card.py` exists for London yet.

**Bio drafted** (not yet confirmed as final or posted):
```
📊 London in figures
📈 TfL, the Environment Agency, data.police.uk, London Datastore +more · sister bot to @seoul-index.bsky.social · A.I. 🤖
👤 Run by @stanfordc.bsky.social
```
Modelled on Seoul Index's actual live bio (fetched, not recalled). No
pinned-methodology-post reference yet since that thread doesn't exist.

**Possible launch date discussed, not decided**: 10 January (Underground's
1863 opening) was the recommendation, vs 3 April (GLA founding) or no
symbolism at all (Seoul Index's own precedent).

## Rival check (Bluesky)

No Harper's-Index-style London bot found after two passes (the second one
specifically checking alt-text-based card bots, which the first missed).
**`tflbot.bsky.social`** is real and live (line status since Oct 2024,
10k+ posts) — deliberately avoided that vein. **`ldndata.bsky.social`** is
the official GLA account, human-run, low-cadence, not a rival.

## Data sources: full status

| Source | Status |
|---|---|
| TfL (bikes, crowding) | ✅ Live, key wired in |
| Environment Agency (flood, rivers) | ✅ Live, no key ever needed |
| data.police.uk | ✅ Live, no key ever needed |
| London Datastore (cycle hires) | ✅ Live, no key ever needed |
| London Air Quality Network | ✅ Live, no key ever needed |
| MPS Crime Dashboard (Datastore) | ❌ Ruled out — frozen since July 2024 data |
| ONS | ❌ Ruled out — not London-specific enough |
| London Fire Brigade | ❌ Ruled out — monthly-only, no live API |
| Historic England | ❌ Ruled out — fits a photo bot, not this one |
| **Met Office DataHub** (forecast) | ⏳ Signup in progress, unresolved (see below) |
| **UK Hydrographic Office Admiralty API** (tide times) | ⏳ Found, free tier confirmed, not started |
| **National Rail Darwin** (live departures) | ⏳ Found, free tier confirmed, not started |

## Open / unresolved threads

1. **Met Office DataHub signup** — user was navigating api-portal-equivalent
   (`acct.metoffice.gov.uk/services/data/met-office-weather-datahub`),
   repeatedly landing on marketing pages instead of the actual portal. Last
   state: logged in, told to use Pricing & Plans → subscribe to **Global
   Spot** specifically (NOT the Blended Probabilistic Forecast/BPF product —
   that's a model blend of probabilities, not a single published figure,
   which breaks the "accuracy over wit" principle Seoul Index's own weather
   post is built on). Then hit "none of the links on this page are
   clickable" — asked for a screenshot/diagnosis, never got a follow-up.
   **Needs picking back up.**
2. **Bluesky profile "changes aren't saving"** — user reported this against
   `london-index.bsky.social`, asked for specifics (what's failing, what
   error), never got a follow-up. **Unresolved.**
3. **Admiralty API and Darwin API** — identified as real, free-tier, needs
   separate email-only signups. Not started.
4. **Avatar colour** — `#2c4c70` is a guess, not measured. Worth revisiting
   with real pixel sampling if the photo can be saved to disk next time.

## Design principles carried from Seoul Index

- **Accuracy over wit**: prefer an authority's own published figure over a
  third-party model's estimate (this killed Open-Meteo and the Met Office's
  BPF product as candidates).
- **Verify coordinates/IDs live, never from memory** — a real mistake this
  session: three Environment Agency station IDs picked from memory turned
  out to belong to Reading, Boveney Lock, and nothing at all. Real ones came
  from an actual `/stations?...` query.
- **Curated lists over full coverage** (12 stations, 6 gauges, 8 boroughs),
  matching Seoul Index's own "spotlight places" pattern rather than trying
  to cover everything.

## Not yet started

- Full posting pipeline: card renderer, Bluesky posting script, selection
  logic (Seoul Index's `claude -p` curation step), `weather_history.jsonl`equivalent logging.
- Pinned methodology thread.
- launchd scheduling.
- Weather harvester (blocked on Met Office key).

## Session 2 — 29 August 2026

Picked up the four open threads from session 1. Bluesky profile save issue
was resolved by the user outside this session (no diagnosis needed). Met
Office DataHub, Darwin/rail, and museums/events were all worked.

### Met Office DataHub — still blocked, root cause now understood
The marketing page's "pricing plans **here**" and "map images pricing
**here**" links are genuinely dead in the live HTML — `<strong>here</strong>`
with no `<a href>` at all, a real content bug on Met Office's own site, not a
rendering issue on our end. The actual developer/signup portal is a
completely different domain: `metoffice.apiconnect.ibmcloud.com` (IBM API
Connect), found via the page's FAQ link
(`.../metoffice/production/faq-page`). **That exact URL 404s** when the user
tried it directly — so the FAQ link itself may be broken on Met Office's end,
same family of bug as the dead "here" links. Our browser tool also refuses to
navigate to `ibmcloud.com` domains outright (policy block, not a site error),
so this can't be driven from here even once a working URL is found. **Next
step, if picked back up**: hunt for the actual portal root a different way
(their support/contact channel, or a fresh search) rather than guessing at
paths off the known-broken FAQ link.

### Darwin / rail data — resolved, registration submitted
The old NRDP portal (`opendata.nationalrail.co.uk`) carries a banner saying
it's being superseded by "Darwin Evolution", migrating users to a new
platform called **RDM (Rail Data Marketplace)**, at `raildata.org.uk` — live
since a June 2021 government-funded project, not something still in
progress. Verified live and confirmed the real target product: **"Live
Departure Board" (LDBWS)**, not the raw Darwin Push Port stream (which is a
continuous message-queue feed, not a simple polled API — wrong shape for
this project). LDBWS is request/response, queried by CRS station code, "Live"
update frequency, covers England/Scotland/Wales.

Licence terms (from the product's own Licence tab, not assumed): **free**,
Open licence, no SLA, 1-year auto-renewing term with 1 week's notice to
cancel, must delete retained data within 1 year (irrelevant for a poll-and-post
bot), and — importantly — **"the raw data may be made freely available or
otherwise distributed to third parties"**, so publishing derived facts
publicly is explicitly fine. Attribution required: Rail Delivery Group.
Real documentation exists: a PDF spec, a Swagger/OpenAPI JSON file, and
`realtime.nationalrail.co.uk/LDBWS/docs/documentation.html`.

✅ **User has registered an account** on raildata.org.uk (submitted, pending
GLA-style manual review, "usually 1 to 2 working days" per the portal's own
copy). **Next step once approved**: sign in, open the Live Departure Board
product page, hit Subscribe to get an API key.

### Museums — DCMS annual figures found; Cultural Infrastructure Map ruled out
Searched London Datastore's full catalogue properly, two ways: the
browser-based search UI, and — better — the site's own Export API
(`https://data.london.gov.uk/api/v3/datasets/export.json`, no auth needed for
reads, confirmed live, 1,293 datasets). Checked every one of the 50
"Art and Culture"-tagged datasets directly, not just keyword matches.
**Conclusion: London Datastore has no live museum or events data at all.**
Everything found is either stale (surveys 6–17 years old) or not about
visitor/attendance numbers.

⚠️ **The "Cultural Infrastructure Map" (2019/2023/2024/2025 editions) is
NOT museum data**, despite the name — downloaded the actual 2025/2026
spreadsheet (`GLA_Cultural_Infrastructure_Map_data_2026.xlsx`, 1,557 rows)
and read every row's `typology` field. It's a creative-industries
*production*-space audit — jewellery/textile/fashion design studios, music
recording/rehearsal studios, artist workspaces, makerspaces — not places the
public visits. Only `theatre` (260) and `arts_centres` (25) are even
plausibly public venues, and neither is confirmed to mean what "museum"
implies. **Do not build a museums vein from this file.** Kept at
`scratch/GLA_Cultural_Infrastructure_Map_data_2026.xlsx` for reference; not
wired into anything.

✅ **Real source found**: DCMS's "Sponsored museums and galleries: annual
performance indicators 2024/25" (GOV.UK, published 23 April 2026, next
update early 2027). DCMS sponsors 15 national museums with free entry to
their permanent collections; the data tables (ODS, downloaded to
`scratch/DCMS_museums_2024_25_tables.ods`) include **Table 1: per-museum
annual visitor figures, 2008/09 through 2024/25** — verified real by reading
every row: shows the actual COVID collapse in 2020/21 (e.g. British Museum
160,105 that year vs 6.5–6.8M in normal years) and recovery since. Most of
the 17 institutions are London-based (British Museum, National Gallery, V&A,
Natural History Museum, Science Museum Group, Tate, Imperial War Museums,
National Portrait Gallery, Royal Museums Greenwich, Sir John Soane's Museum,
Wallace Collection, Museum of the Home) — a handful aren't (National Museums
Liverpool, Museum of Science and Industry in Manchester, National Coal
Mining Museum, Royal Armouries, Tyne and Wear Museums) and would need
filtering out for a London-only vein. Not live — annual, like `police_boroughs`
— but genuinely authoritative and current. Other tables in the same file cover
under-16 visitors, overseas visitors, website visits, loan venues, and three
income streams, all also split by museum and year, not yet reviewed in
detail.

The dead-end (checked and ruled out): "Daily Visitors to DCMS Sponsored
Museums and Galleries" — a COVID-era experimental series, confirmed
"Paused during lockdown" since November 2020, "Next update: TBC". Do not use.

### Events — Ticketmaster Discovery API chosen
Two real candidates checked and compared head-to-head, not just the one
found first:

| | Ticketmaster Discovery API | Skiddle API |
|---|---|---|
| Maturity | Versioned (v2.0), actively documented | Still labelled "Beta"; **GitHub docs repo archived (read-only) since 30 April 2024** |
| Rate limit | Documented: 5,000/day, 5/sec | Undocumented, "continually changed, contact us" |
| UK coverage | Explicitly confirmed in docs | UK-focused by design |
| Use restriction | Commercial allowed with restrictions | Non-commercial only |
| Content terms | Must remove content within 24h of a rights-holder request; no long-term caching/storage; must disclose a privacy policy | Not documented anywhere found |
| Signup | Self-serve API key | Manual application ("apply here") |

**Decision: Ticketmaster.** Skiddle's archived documentation and vague rate
limits are a real reliability risk for a bot meant to run unattended for
years — an actively-maintained API with stricter-but-clear terms beats a
philosophically-closer fit that looks stagnant. Root URL:
`https://app.ticketmaster.com/discovery/v2/`; relevant endpoint:
`/discovery/v2/events` with `postalCode`/`geoPoint`/`radius` and
`startDateTime`/`endDateTime` filters. **Not yet registered** — needs a
self-serve signup (account creation, so the user needs to do this step).

### London Datastore API key — clarified, probably not needed
User set up a London Datastore API key via 1Password mid-session. Checked
the actual API docs (`datapress.com/docs/api/`, the platform data.london.gov.uk
runs on): **the key is only for editing/updating the catalogue** ("if you're
an editor on your site, you'll need an API key"). Read-only access — all
this project needs — explicitly requires **no authentication**:
`GET https://data.london.gov.uk/api/v3/datasets/export.json` works
unauthenticated (confirmed live, used above to search the full catalogue).
Unresolved: why the user has editor access to data.london.gov.uk, and
whether the key is worth keeping for some other reason. Not wired into the
harvester since it isn't needed for reads.

## Updated data source status

| Source | Status |
|---|---|
| TfL (bikes, crowding) | ✅ Live, key wired in |
| Environment Agency (flood, rivers) | ✅ Live, no key ever needed |
| data.police.uk | ✅ Live, no key ever needed |
| London Datastore (cycle hires) | ✅ Live, no key ever needed |
| London Air Quality Network | ✅ Live, no key ever needed |
| **National Rail Darwin (LDBWS, via RDM)** | ⏳ Right product identified, licence verified, account registration submitted — pending approval, then Subscribe for API key |
| **DCMS museum visitor figures** | ✅ Live, wired in 30 August 2026 as the `dcms_museums` vein, filtered to the 13 London-based institutions |
| **Ticketmaster Discovery API (events)** | ⏳ Decided on, terms verified, account not yet registered |
| Met Office DataHub (forecast) | ⛔ Still blocked — real portal domain found but its own FAQ link 404s, and our browser can't reach `ibmcloud.com` anyway |
| MPS Crime Dashboard (Datastore) | ❌ Ruled out — frozen since July 2024 data |
| ONS | ❌ Ruled out — not London-specific enough |
| London Fire Brigade | ❌ Ruled out — monthly-only, no live API |
| Historic England | ❌ Ruled out — fits a photo bot, not this one |
| GLA Cultural Infrastructure Map | ❌ Ruled out for museums — verified it's creative-production spaces, not visitor venues |
| UK Hydrographic Office Admiralty API (tide times) | ⏳ Found, free tier confirmed, not started |

## Session 3 — 29 August 2026, later — posting pipeline built and verified

Built the whole posting pipeline the plan file at
`~/.claude/plans/fluttering-cuddling-graham.md` describes: `london_index_select.py`
(claude -p selection, simplified from Seoul Index's — no cross-vein
collisions, no rotation/cooldown/vein-floor, just a basic "don't repeat the
last N ids" check), `london_index_card.py` (renderer, adapted from Seoul's
sentinel-crop technique onto the already-agreed `sample_card_1.html`
template — dateline moved under the title per feedback during the session),
`london_index_compose.py` (small compose step, no label-accuracy audit, no
masthead logic), `london_index_post.py` (orchestrator: harvest → select →
compose → render → post as a 2-post thread, card + clickable source reply,
plaintext fallback if rendering fails). All four adapt real patterns read
directly from `~/Projects/seoul-index/` rather than guessed from memory.

✅ **Verified end to end with `--dry-run`**: real harvest (17 facts, 8
sources, zero errors), real `claude -p` selection, real compose, real
render. Confirmed working from both inside this session and from a genuine
standalone terminal.

⚠️⚠️ **The token-setup saga, worth recording at length because it cost most
of a session and the actual cause was mundane.** `select()` calls `claude -p`
authenticated via a Keychain-stored long-lived token (`londonbot` /
`claude-oauth-token`, mirroring Seoul Index's `seoulbot` pattern) rather than
the ambient CLI login, exactly as `scan_filer.py` and Seoul Index both
already do and for the same reason. Getting a *working* token into that
Keychain slot took roughly a dozen failed attempts across three different
wrong theories before finding the real one:

1. **First attempt failed outright**: `claude setup-token` needs a real TTY
   for its OAuth flow ("Raw mode is not supported on the current
   process.stdin"), so it cannot be run from a sandboxed Bash tool at all —
   only from a genuine interactive terminal.
2. **Every subsequent stored token still failed** with `claude -p` either
   hanging for 90s×3 (via the Python pipeline) or returning a clean
   `401 OAuth access token is invalid` (via a bare terminal test). This
   looked at various points like: a nested-Claude-Code-session limitation
   (ruled out — the same hang reproduced from a genuine standalone
   terminal), Keychain corruption (ruled out — direct byte inspection of
   the stored value showed a clean 81-byte string with the correct
   `sk-ant-oat` prefix and no embedded whitespace), and a stale CLI version
   (this Mac had **two separate installs**: the desktop app's bundled
   Claude Code at 2.1.247, and a completely different Homebrew/npm-global
   CLI at 2.1.76 actually in `$PATH` — upgrading the latter via
   `npm update -g @anthropic-ai/claude-code` to 2.1.251 was a real fix
   worth having made, but did NOT fix this particular bug).
3. **The actual cause**: `claude setup-token` prints the token inside a
   bordered box that wraps at the terminal's width, and copying that
   visually-wrapped text carries the line break along with it. Every
   `export CLAUDE_CODE_OAUTH_TOKEN=<paste>` was silently capturing only the
   *first half* of the token — proven when a later attempt actually
   surfaced the failure loudly instead of silently: the second half of a
   token ran as a bare shell command (`zsh: command not found:
   npiSsv3eFW0kbXr9X5tA-kJZalwAA`). Every "invalid token" error before that
   had been a **truncated** token, not a wrong or expired one. Fixed by
   widening the terminal window before running `claude setup-token` so the
   token prints unwrapped on one line, and by writing the resulting shell
   variable straight into Keychain (`security add-generic-password -U -a
   "londonbot" -s "claude-oauth-token" -w "$CLAUDE_CODE_OAUTH_TOKEN"`)
   rather than re-copying it a second time from the terminal — which also
   sidesteps needing to paste the secret anywhere ever again. The final
   stored value is 109 bytes against the earlier truncated 81, which is
   itself confirmation of what had been going wrong.
4. ⛔ **The token was pasted directly into chat once during this process,
   against explicit instruction not to.** Treated as compromised;
   regenerated afterward via the corrected (wide-terminal) method rather
   than reused. Worth remembering as a real failure mode: a user
   troubleshooting a stuck credential flow is exactly the moment they're
   most likely to paste a secret somewhere it shouldn't go.

⚠️ **A real bug survived past the first successful dry-run and was caught
by actually reading the output rather than trusting a clean exit code.**
`compose.py`'s `_footnote()` treated "this fact has a `period` value" as
synonymous with "this is a non-live annual/monthly figure worth flagging" —
wrong, because `tfl_crowding` and `river_levels` both stamp `period` with
the *live observation timestamp*, not a calendar period. The first real
run's footnote read `(2026-08-29 11:16:00; 2026-08-29 11:21:00;
2026-08-29T10:00:00Z)` — three jumbled, meaningless timestamps. Fixed by
excluding any `period` containing `:` (a time-of-day component) from
footnote consideration, verified against both the real jumbled data (now
empty) and genuine calendar periods like `2026-06` (still shown correctly).

## Card design polish, same session, after the first working end-to-end card

A long back-and-forth over real rendered cards, each change verified against
live data before moving to the next:

- **No per-line emoji** — the opener's own emoji is now the only one on the
  card; repeating the same icon on every line beneath it read as clutter.
  `VEIN_EMOJI` and the whole per-line emoji mechanism were removed from
  `compose.py`, not just hidden.
- **Dotted leader** between label and value on every line (`.leader`,
  `border-bottom:2px dotted`), matching Seoul Index's own card design.
- **`##` in blue, opener text in black** — a deliberate two-colour split
  (`.opener{color:#000}` / `.opener .md{color:INK}`), not the single-colour
  treatment used everywhere else on the card.
- **Dateline (when shown) is bold solid blue**, not the original muted 60%-
  opacity grey — matches Seoul Index's own masthead-date treatment.
- **Curly quotes everywhere**, via a `curly()` in `london_index_card.py`
  copied from Seoul Index's own implementation and run inside `_esc()`, so
  it catches hardcoded strings AND the `claude -p` selector's own generated
  opener text, not just one or the other. One real hardcoded straight
  apostrophe was also fixed at the source (`King's Cross St Pancras` in
  `TFL_STATIONS`), following the established house rule to type the curly
  mark directly rather than rely solely on a runtime curler.
- **a.m./p.m., not 24-hour time** — `_dateline()` was showing bare `%H:%M`
  ("12:08"), ambiguous and against house style; now builds "12:08 p.m."
  by hand (Python's `%p` gives uppercase "PM" with no periods, wrong shape).
- **"% of baseline", not "% of typical"** — a real, unresolved verification
  gap. Checked seven sources for what TfL's `percentageOfBaseline` field
  actually means (their tech forum, blocked by a bot-challenge even via the
  Wayback Machine; official API docs, silent; a third-party tutorial and a
  GitHub analysis project, both silent). **Could not verify it means
  "typical" specifically**, so switched to TfL's own neutral field name
  rather than assert something unconfirmed. Longer-term fix discussed but
  not built: a `london_index_crowd_log.py` hourly sampler mirroring Seoul
  Index's `crowd_history.jsonl`, so London Index could derive its own
  empirical "usual for this hour" independent of TfL's opaque baseline —
  explicitly not instant (Seoul's own equivalent line took three weeks of
  samples to activate) and not started this session.
- **Emoji must be concretely on-topic**, never a figurative reach — caught
  live: the selector picked ⚖️ (scales of justice) for an opener reading
  "Full and empty" (a river/station contrast), a metaphorical stretch with
  nothing to do with rivers or stations. `SELECT_PROMPT` now requires the
  emoji depict something literally present in the picked facts.
- **Tightened harvester labels app-wide** to match the mockup's terse
  style (`london_index_harvest.py`): "Crimes recorded within a mile of
  central London, {ym}" → "Reported crimes within a mile of central
  London" → **"Within a mile of central London"** (the "reported crimes"
  part moved to the opener once that became the only place stating it);
  "Most/Fewest reports" → "Most/Fewest"; "Average daily hire count so far
  in {year}" → "Average daily hires". Verified after each pass against
  real harvested output, not just read back from the diff.
- **No relative date phrasing in the opener, ever.** `SELECT_PROMPT`
  originally suggested "Crime this month" as an example opener — factually
  wrong, since `_latest_police_month()` already documents a ~2-month API
  lag, so "this month" while a card posts in August can describe June's
  data. Fixed in two passes: first to name the actual period ("Reported
  crimes in June"), then to **include the year** ("...in June 2026") after
  it was pointed out the card image alone (if ever shared without its
  reply) would otherwise carry no year anywhere. Also caught and fixed:
  the selector was appending "now"/", now" to already-live openers
  ("London's bike share, now") when the card's own live dateline already
  says so — redundant, not just harmless, per the same principle.
- **No masthead date for period-based (non-live) cards at all** — the
  original design showed today's date under the title regardless of what
  the figures actually covered, which is an outright false claim next to
  June's crime data posted in August. `_dateline()` now returns `''` for
  any card whose picks are not live; the real period moves to the **source
  credit** in the reply instead (`_period_credit()`, e.g. "data.police.uk,
  June 2026"), never bare on the card image. The trailing `<hr class="rule">`
  is now conditional on a non-empty footnote too, so a card with no
  footnote (which, with the period gone, is now most of them) doesn't end
  in a pointless line with nothing below it.
- ⚠️ **Real bug caught by reading actual output, not by design review**:
  a card mixing a live vein (`tfl_bikes`) with a dated one (`cycle_hires`)
  produced a credit reading "TfL BikePoint, 2026; 31 July 2026" — the
  period genuinely belonged to the cycle-hires facts, but landed after the
  *last* listed source name regardless, since the credit line only ever
  lists sources, never which pick contributed which period. There is no
  clean way to attribute a period to one source out of several sharing one
  line, so `_period_credit()` now suppresses entirely whenever any pick on
  the card is live (`_is_live()`, shared with `_dateline()` so the two stay
  mutually exclusive) — the live dateline already anchors that kind of card
  well enough on its own.
- **Bluesky handle hardcoded**, not read from a config file — matching
  `kbo_post.py`'s `HANDLE = '...'` pattern rather than Seoul Index's
  config-file convention, since (once the TfL key and Bluesky/Claude
  credentials all moved to Keychain) the config file held nothing but the
  handle. `london_index_config.json` and `.example.json` both deleted.

## Recurring scheduling — live as of 29 August 2026

`~/Library/LaunchAgents/com.chrisstanford.londonindex.plist` (validated with
`plutil -lint`, bootstrapped, and confirmed via `launchctl print` — path,
program, environment and all four `StartCalendarInterval` entries checked
individually, not just a clean bootstrap exit code). Mirrors Seoul Index's
plist structure exactly: same Python interpreter
(`/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`), same
`PATH`/`HOME` environment, log file at
`~/Library/Logs/london_index_bot.log`.

**Fires 8:00 a.m., 12:30 p.m., 5:30 p.m., 8:30 p.m. London time** — chosen
for general UK social-engagement patterns (commute/lunch/commute/evening
leisure), explicitly **not** derived from real account data, since the
account has never posted. This is a real gap against how the *other* five
bots in this estate are handled: `bot_health_check.py` carries a permanent
engagement report for them, which already drove one real, measured
scheduling change (Holmes's posting time, moved after measuring actual
audience active hours). **London Index is not in that mechanism yet** —
adding it once real posts accumulate, and revisiting this schedule against
real data after a couple of weeks, is the honest next step, not treating
today's times as final.

## The selector's `claude -p` call is confined — 11 September 2026

`select()` now runs `claude -p --restricted --tools ""`: no tools at all.
It is text in, JSON out, and needs none; unconfined, `claude -p` is an
agent with Bash in the Mini's home directory, and the everygeorgia
transcriber was found that day cropping images through a dozen tool calls
and once running the project's own code from inside such a call. Seoul
Index's selector and label check got the same treatment the same day
(`CONFINED` in `seoul_index_post.py` carries the incident). `--restricted`
also ignores the user's settings files, so no hook fires from inside a
scheduled post, and the call passes `stdin=DEVNULL` because the CLI
otherwise waits three seconds for stdin on every hand-run call. Verified
with a real `select()` on a five-fact synthetic pool: the vein floor
promoted `police`, and the confined call returned the same JSON shape in
about five seconds. `test_london_index_select.py` passes unchanged; it
mocks `subprocess.run` and reads only the prompt, so it cannot see the
flags. Check the argv, not the tests.

## Not yet done

- **A real live post has never been made** — everything is verified via
  `--dry-run` only, even though the job is now live and will fire
  unattended at the next scheduled slot. Worth watching the first
  automated run's log (`~/Library/Logs/london_index_bot.log`) rather than
  assuming it went well.
- London Index is not yet in `bot_health_check.py`'s engagement tracking —
  see scheduling section above.
- Ticketmaster and Darwin/RDM keys still not wired into the harvester (both
  registrations are further along now — Ticketmaster account created,
  Darwin registration submitted — but neither has an actual API key yet).
- ✅ **DCMS museum data turned into a harvester vein 30 August 2026**
  (`dcms_museums` in `london_index_harvest.py`): filtered to the 13
  London-based institutions out of 18 DCMS sponsors nationally (see
  `LONDON_DCMS_MUSEUMS`), fetched fresh from GOV.UK's own ODS attachment
  each run, same shape as `cycle_hires`. Verified end to end through
  `london_index_post.py --dry-run --only=dcms_museums`.
- ✅ **Pinned methodology thread built 30 August 2026**
  (`london_index_methodology.py`, mirroring Seoul Index's own): 4 English
  cards ("About this account", "the figures", "the crowding figures", "the
  museum figures") plus a clickable source-credit reply covering every live
  vein's publisher (TfL, the Environment Agency, data.police.uk, the London
  Datastore, the London Air Quality Network, GOV.UK/DCMS) — not Ticketmaster
  or Darwin, neither of which is wired in yet. Verified via `--dry-run`
  (renders, byte-exact source facets checked against `build_facets()`); not
  yet posted or pinned live, which needs an explicit go-ahead since the
  account currently has zero posts by design (see the "Not yet done" entry
  above about no real post having gone out).
- A `london_index_crowd_log.py` hourly crowding sampler was discussed (see
  "% of baseline" above) as the honest long-term fix for the unverifiable
  TfL baseline definition, but not built this session.
- ✅ **Vein rotation (cooldown + starve-floor) built 6 September 2026**, in
  `london_index_select.py`, ported from Seoul Index's own
  `apply_cooldown()`/`promote_starved()`. Triggered by two real posts,
  16 hours apart (bsky.app/.../3muppich4zm27, a daily_footfall card, and
  .../3murf3zphbj2x, a station_usage card) read as the same "busiest
  station" card twice: with `tfl_crowding` paused, `station_usage` and
  `daily_footfall` alone were two-thirds of the preceding 15 posts, while
  `tfl_bikes`, `flood`, `police` and `cycle_hires` led none of them. Until
  this date the only anti-repeat guard was fact-id-level (`recent_ids`,
  last 12) — this file's own Session 3 entry above notes that was a
  deliberate simplification "London Index has no posting history yet to
  build [rotation] against"; 20 real posts later, it did.
  - `BUSIEST_STATION_VEINS = {station_usage, daily_footfall}` share ONE
    2-day cooldown, not two separate ones — they're different data sources
    answering the same reader-facing question, and a per-vein cooldown
    alone would have let the bot alternate between them and still post a
    "busiest station" card daily.
  - Every other vein gets `promote_starved()`: 2 days unstamped and the
    pool narrows to that vein alone. `flood` stays out of rotation by
    falling under `STARVE_MIN_FACTS=2` (it only ever harvests one fact,
    see `harvest_flood()`) rather than by a hardcoded exception — a real,
    separate limitation, not something this change fixes. Extending
    `harvest_flood()` with a second comparable figure (e.g. warnings vs.
    alerts, both counts) would be the honest way to bring it back in.
  - Chris's call, this date: build the full two-part machinery (matching
    Seoul Index) rather than the narrower single-purpose fix, deliberately
    more than London Index's current 10-vein roster strictly needs, so
    there's headroom to grow into.
  - `london_index_state.json` (gitignored, so untracked by git) migrated
    once: `vein_last_at` backfilled from `card_history.jsonl`'s real post
    timestamps, converting each London-local `at` string to UTC. Without
    this the very first live run after deploy would have read every vein
    as "never posted" and picked among them by an arbitrary (alphabetical)
    tie-break rather than honouring the real history.
  - Covered by `test_london_index_select.py` (16 tests): both refusal
    cases per guard (a malformed/missing timestamp fires no cooldown or
    promotion; a cooldown that would empty the pool is abandoned), the
    shared-cooldown-group behaviour, the starve floor's `flood` exclusion,
    and one end-to-end test confirming cooled/starved veins never reach
    the `claude -p` prompt at all (subprocess mocked, no network). Verified
    by mutation: removing the pool-floor guard, the `STARVE_MIN_FACTS`
    check, and the tie-break's third sort key were each confirmed to fail
    the suite and pass again on restore.

## Session — 12 September 2026: the same card twice, and where the variety went

Chris flagged two posts five hours apart on 11 September that were the same
card, line for line (bsky.app/.../3mvahvdld5f27 at 12:34 BST and
.../3mvayox7dnd24 at 17:34): "Reported crime / July 2026 / Most: Camden
3,179 / Fewest: Bromley 449". Then: "Every time that card is posted, it's
Camden and Bromley", "Other theft always seems to be the most common", and
"We need much more variety".

**Measured, from `card_history.jsonl`: of 44 cards posted since 30 August,
34 were distinct.** The two crime cards were 9 of the last 12 posts, and
Camden/Bromley had already gone out twice in one day on 9 September. And
against the live pool harvested that morning, **22 of 31 facts had already
been posted at exactly that value**: station_usage and dcms_museums are
annual, police and police_boroughs monthly, cycle_hires dated 31 July,
daily_footfall nine days lagged. Only tfl_bikes and laqn change between
runs. Four slots a day over that pool cannot help repeating.

### Why the guard failed
The 12:30 run's log: busiest-station veins on cooldown (87h of 96h), DCMS on
cooldown, and `flood`, `laqn`, `river_levels` all failed (the Environment
Agency's API was timing out, and still was on the 12th). Four veins left.
The only fact-level guard was `AVOID_IDS`, a soft "do not pick if a
reasonable alternative exists" the model ignored at 12:30 and again at
17:30. Nothing compared the finished card with the history. The 8
September fix (`248da73`) had added a 4-day cooldown for dcms_museums and
lengthened the station one, but each cooldown is a hardcoded group, and
police_boroughs had none.

### The fix, three layers (`e7c4fe2`)
1. **Spent facts.** `select()` reads `card_history.jsonl` and drops every
   fact whose `(label, value)` is already on a posted card, and the whole
   pair group with it (a ranked list missing its top entry is a wrong card,
   not a shorter one). A live vein's values change every run, so it is
   never spent; a monthly vein's facts are spent for the rest of the month.
   The history, never the state file, is the record: it holds what actually
   posted. If nothing pickable survives, `select()` raises `NothingFresh`
   and the poster **skips the slot at exit 0**, with a log line saying so.
   A missed slot is the lesser fault, and the one this bot had never once
   chosen over a repeat.
2. **General cooldown.** Any vein that led within `GENERAL_COOLDOWN_HOURS`
   (20) is withheld, on top of the two 4-day groups, with the usual
   abandonment rule. Without it the spent filter leaves the two live veins
   alternating three times a day with fresh numbers, which to a reader is
   the same card.
3. **The last line.** `london_index_post.py` refuses, line for line, any
   card whose `card_lines_key()` is already in the history, whatever the
   selector did. The filter should make it unreachable; this is what says
   so if a `--only` run or a future path ever isn't.
⚠️ The spent filter runs FIRST, before the cooldowns: a cooldown that is
abandoned "because nothing else is pickable" must not be abandoned on the
strength of facts about to be dropped anyway. 20 new tests in
`test_london_index_select.py` (36 total); the two real cards are the
fixtures.

### Variety: four card shapes from one month of borough crime
`harvest_police_boroughs()` used to produce two facts (the gap) and, on a
lucky month, a near-tie. Now `borough_facts()` (pure, tested) produces
five shapes: the gap; the near-tie; **`police_top`** (the four busiest,
ranked); **`police_change`** (biggest rise and biggest fall, or smallest
rise when every borough rose, on the previous month, which is fetched too);
and **`police_types_top`** (the borough with the most of each of violent
crime, shoplifting, vehicle crime, burglary, bicycle theft and robbery,
ranked by count, top four). Live on 12 September: Hackney +20 percent and
Newham +2 percent since June; violent crime Camden 544, shoplifting
Camden 411, vehicle crime Newham 123, robbery Camden 98 (Camden three
times on one card is the sample's truth, not a fault: it is the biggest of
the eight, and the footnote says what was sampled).
⚠️ **Every borough fact now carries `BOROUGH_NOTE` as its footnote**:
"Within a mile of each town hall; eight boroughs sampled: …". Until now
"Most: Camden 3,179" under "Reported crime" read as Camden's monthly
total, and it is a one-mile sample around the town hall. The card never
said so.
`harvest_police()` (central London) gained "Change since June" (+6 percent)
and **`central_top`**, the four most-reported categories ranked, so the
central card is no longer only "4,728 / Other theft 1,097" for a month.
Both fixed-opener maps grew to match; a shape that recurs monthly should
carry the same title each time.
⚠️ `_latest_police_month()` used to walk back `30 days × n` from the first
of the month, which can land on one month twice; it is real month
arithmetic now (`_shift_month`).

### Four new veins, none needing a key
| vein | source | cadence | shapes |
|---|---|---|---|
| `stop_search` | data.police.uk, `stops-force?force=metropolitan` | monthly | searches, arrests, no further action, for drugs, for weapons (`stops_all`) |
| `house_prices` | HM Land Registry UK HPI, linked-data JSON | monthly, ~2 months behind | London average and changes; flat vs detached; all 33 boroughs: most/least expensive, top four, biggest annual rise/fall |
| `road_works` | TfL `Road/all/Disruption` | live | disruptions on TfL roads, moderate or worse, planned works (`roads_all`) |
| `lfb_animals` | London Datastore, LFB animal rescues XLSX (2.9 MB) | monthly | rescues, borough with most, kinds of animal ranked, notional cost |
- The prompt gained an **`_all`** pair rule: every fact of the vein shares
  the tag, any 2 to 4 make a card, no order to keep; it exists so a fixed
  opener can attach to a vein with no natural gap or ranking.
- `house_prices` refuses the borough shapes under `HPI_MIN_BOROUGHS` (30)
  answering, and `_hpi_month()` reads an unpublished month (the API answers
  `result: "elda:missingEndpoint"`, a bare string) as no data. The borough
  slugs are the index's own local-authority names; four were verified live
  and the rest are checked on every run, with any that fail logged.
- `lfb_animals` takes the newest month in the file that is not the current
  calendar month, and refuses under `ANIMALS_MIN_ROWS` (10). Plurals come
  from `ANIMAL_PLURALS`; a kind not in it (the file's "Unknown - …"
  groups) never reaches the ranked list.
- `stop_search` refuses a month under 1,000 records as still loading; the
  Met records five figures a month (12,088 in July 2026).
- `flood` now counts warnings and alerts separately from `severityLevel`,
  the second comparable figure that lets it clear `STARVE_MIN_FACTS` and
  rejoin rotation; items without the field fall back to the old single
  fact. ✅ Verified live at 01:21 BST on 12 September once the EA API came
  back: 0 warnings, 1 alert, both from `severityLevel`.
- `test_london_index_harvest.py` (22 tests) pins the pure builders: the
  sign and wording of every change line, ranking order, the labels, and the
  refusals.

### Not built, on purpose, pending Chris
- Wikipedia page views for London landmarks (daily, no key): real figures,
  but not civic data, and this account's remit is "London in figures" from
  its publishers.
- The full LFB incident file: 81 MB per download, four times a day.
- Dropping to three posts a day: the honest answer to a pool this static,
  but a schedule change is his.
- Thames tide times: the EA has no London tide gauge (checked
  `type=TideGauge` and `qualifier=Tidal Level` within 25 km), so this still
  needs the Admiralty signup. Rail Data Marketplace, Ticketmaster and the
  Met Office portal are all still blocked on his own signups.
- ⚠️ `london_index_methodology.py` was dirty in the tree from another
  session and was not touched; its source-credit reply needs HM Land
  Registry added once that session's work lands.
- ⚠️ `london_index_post.py --dry-run` still writes `vein_last_at` to the
  state file, so a hand dry-run at 9:00 puts that vein on the 20-hour
  cooldown for the 12:30 run. Pre-existing; noted, not changed.
