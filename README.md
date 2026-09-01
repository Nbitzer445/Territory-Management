# BRM Territory Hub

A local, private territory management app for Nathen Bitzer -- Business
Development Manager, Big Rivers Marketing, covering Nebraska and Iowa.

Accounts, contacts, call history, follow-ups, the manufacturers you
represent, sales performance, and a market/manufacturer news feed, all in
one place, all editable, all saved on your own computer.

## Your data never leaves your computer

- Everything is stored in one local file: `data/territory.db` (SQLite).
  There is no cloud account, no external database, and no sync of any kind.
- The **only** outbound network calls this app makes are public news
  searches for the News page (see "How the News feed works" below), and
  those calls only ever send short search terms (a brand name, "copper
  prices", etc). Your accounts, contacts, calls, and sales figures are
  never included in any request the app makes.
- `.gitignore` excludes the entire `data/` folder (the database, uploaded
  spreadsheets, and backups) so none of it can accidentally end up in git
  or get shared if you ever push this project somewhere.

## Quick start

**You need Python 3.9+ installed.** If you don't have it, get it from
[python.org/downloads](https://www.python.org/downloads/) (check "Add
Python to PATH" during install on Windows).

**Mac / Linux:**
```
./run.sh
```

**Windows:** double-click `run.bat` (or run it from a Command Prompt).

The first run sets up a private Python environment and installs the few
required packages (Flask, openpyxl, requests) -- this takes a minute and
only happens once. Every run after that starts in a couple of seconds.

Once it says `Running on http://127.0.0.1:5000`, open that address in your
browser. Leave the terminal/command window open while you use the app;
closing it stops the app. Your data is safe either way -- it's saved to
disk on every change, not just on exit.

## Your data is already loaded

This copy was set up using the three files you provided:

- **Activity Journal** (596 of your calls, filtered to Sales Rep = Nathen
  Bitzer) -> imported as your Call Log, with Accounts, Contacts, and a
  few Follow-ups created automatically along the way.
- **Sales Numbers through June 2026** -> imported as Sales snapshots:
  53 accounts, 233 account/brand lines, 39 brands, ~$4.65M YTD vs ~$4.94M
  prior-year YTD (about -$288K / -5.8% YoY territory-wide).
- **Companies** -> see the note below; this file contained no account
  rows, so the account list (156 accounts total) was built from the
  company names found in the Journal and Sales files instead.

You can start using the app immediately -- go to **Dashboard** to see
what's due this week, or **Accounts** to browse.

### About the Companies file

`Companies_4.xlsx` had column headers (Name, Street, City, Class, Category,
etc.) but zero data rows -- it was an empty export. Rather than block on
that, accounts were created directly from the account names that appear in
your Journal and Sales files, with **market** (Lincoln/Omaha/Norfolk/
Columbus/Fremont/Sioux City/NW Iowa) guessed from city names embedded in
the account name (e.g. "Kelly Supply Norfolk" -> Norfolk). Address, class,
category, and phone are blank for now -- edit them in-app whenever you
have time, or get a properly populated Companies export and import it from
the **Import** page: it will fill in those blanks without touching any
account you've already edited, or any contacts/notes/follow-ups you've
added.

## Importing fresh monthly exports

Go to the **Import** page any time you get new files from your CRM:

1. Upload the new Activity Journal, Sales Numbers, or Companies file.
2. The app shows a summary of what changed (accounts created, calls
   imported, brand lines added, etc).

Re-importing is safe and non-destructive:
- **Calls** are de-duplicated (matched on date + account + brand + notes),
  so re-uploading a journal that overlaps a previous one won't create
  duplicate visits.
- **Sales** are never overwritten -- each import adds a new snapshot, so
  your sales history accumulates and trends stay visible over time. The
  app always shows the most recent snapshot as "current."
- **Accounts** are matched by name. An import only fills in *blank*
  fields -- if you've already typed something into a field (address,
  notes, market, etc.) an import will never overwrite it.
- **Contacts, notes, and follow-ups you've added by hand are never
  touched** by an import.

## What's in the app

- **Dashboard** -- who to go see next, dormant branches, follow-ups due this
  week, accounts overdue for a visit, biggest YoY sales movers (growth and
  decline), neglected-revenue accounts, and a news feed snapshot.
- **Plan** -- a ranked "who to see next" list and day-trip clusters by market.
  See below for how the ranking works.
- **Opportunities** -- dormant branches and whitespace (lines an account isn't
  buying that comparable accounts are).
- **Groups** -- branches that buy as one account, combined into the number that
  actually means something. See below.
- **Accounts** -- searchable/filterable list (market, type, brand, sort by
  days-since-visit or sales). Click into an account for its full profile:
  contacts, complete visit timeline, sales by brand with YoY, follow-ups,
  tagged news, and editable fields.
- **Log a Call** -- a fast form for logging a visit: account, contact,
  brand(s) discussed, notes, next follow-up. Updates the account's
  last-visit date and timeline immediately. Check "log another" to jump
  straight back into the form for the same account.
- **Follow-ups** -- every open action, sorted by due date, checkable when
  done, filterable by status/market.
- **Brands** -- one row per manufacturer you represent: territory YTD,
  YoY trend, accounts buying it, and its own news feed.
- **News** -- commodity prices (copper, steel, PVC), manufacturer news,
  market/industry moves, and construction demand, refreshed on demand from
  public sources. Tag any article to an account or brand, or paste in your
  own.
- **Import** -- upload fresh monthly exports; full history of past imports.

## How the Plan page decides who you should see

Every account gets a priority score, and the **reasons behind the score are
always shown** so you can disagree with it. Four things feed in:

1. **Cadence** -- how far past its target visit interval the account is.
   Targets come from the account's tier:

   | Tier | Target visit cadence | Auto-assigned when |
   |------|----------------------|--------------------|
   | A    | every 21 days        | $50K+ YTD          |
   | B    | every 42 days        | $10K-$50K YTD      |
   | C    | every 90 days        | $1K-$10K YTD       |
   | D    | every 120 days       | under $1K YTD      |

   Accounts with no sales history (most contractors) default to 60 days.
   Tiers are assigned automatically from sales volume, but you can **set the
   tier or a custom cadence by hand on any account page** and yours wins.

2. **Revenue at stake** -- bigger accounts rank higher, on a log scale so one
   giant account doesn't drown out everything else.
3. **YoY erosion** -- an account bleeding year-over-year gets pushed up, scaled
   by how big the drop is in both percentage and dollar terms.
4. **What you owe them** -- open and overdue follow-ups add weight.

**Day-trip clusters** group your highest-priority stops by market, so picking
"Norfolk" gives you a route's worth of reasons to make the drive.

## Buying groups (why branch numbers lie)

Some chains raise a PO from one branch and transfer product to another. The
revenue lands on a single account while the activity happens somewhere else --
so Kelly Supply Lincoln can show $48K while Norfolk shows $92, even though
you're selling the same chain and the Norfolk relationship is real.

Left alone, that pattern makes the app draw exactly the wrong conclusions:
Norfolk looks dormant, gets auto-tiered "D" with a 120-day visit cadence, and
its whitespace looks enormous because the group's purchases are invisible from
that branch.

The **Groups** page fixes it. Put branches that share POs into one group and:

- **Combined sales become the real number.** The group page shows total YTD,
  prior-year, and sales by brand summed across every branch.
- **Sister-branch comparisons stop firing.** Group members are never flagged
  dormant relative to each other, because an empty branch inside a group is a
  bookkeeping artifact, not a sales problem.
- **Whitespace is judged on the group's whole book.** A line bought on the
  Lincoln account isn't whitespace at Norfolk.
- **Tier and cadence follow the relationship.** A branch in a group worth
  $99K is tiered A and visited every 21 days, whatever happens to be booked
  against that particular branch.
- **Priority reasons stay honest**, e.g. *"$99,060 YTD at stake across Kelly
  Group ($92 booked to this branch)."*

Per-branch **visits** still matter and are still tracked individually -- the
group is who buys, the branch is where you go.

**Kelly Group is set up already.** The Groups page suggests other chains it
detects (Ferguson, Plumbing & Heating Wholesale, Dennis Supply and so on) with
a one-click "Group these" button. They're suggestions, not automatic: some
chains genuinely run each branch as its own book, and merging those would hide
real differences. Group the ones that actually share POs.

One honest caveat: this corrects for *where* revenue books, not for *when*.
If your sales reports lag, a recent month's activity may not have landed yet,
and no amount of grouping fixes that -- treat a very recent YoY swing as
provisional.

## How the Opportunities page works

**Dormant branches** compare each branch against its own sister branches. Same
banner, same buying group, wildly different results usually means a
relationship gap rather than a market gap. The comparison point is the median
of the chain's *top half* -- a plain average lies when a chain has two strong
branches and three asleep, and the plain maximum lies when one member is
really a regional distribution center booking volume for everybody.

**Whitespace** finds lines an account buys none of that comparable accounts do
buy. Comparisons prefer sister branches of the same chain; failing that, other
accounts of the same company type. Estimates are scaled to the account's actual
size and capped for credibility -- they're a starting point for a conversation,
not a forecast.

Whitespace only applies to accounts with direct sales (distributors).
Contractors buy through distributors, so there's nothing to compare -- their
value in this system is the visit history and the pull-through they drive.

## Talking to Claude about your territory (the MCP bridge)

This connects Claude Desktop to your territory database so you can just ask:

> *"Who should I go see in Norfolk this week?"*
> *"What have I talked about at Kelly Supply, and what's unfinished?"*
> *"Which accounts are bleeding MAAX that I haven't seen in 60 days?"*
> *"Log that call: Winsupply Norfolk, walked the Salo line with Jeff, follow up in two weeks."*

**Setup (once):**

1. Install [Claude Desktop](https://claude.ai/download) if you don't have it.
2. Double-click **`setup_mcp.bat`** (Windows) or run `python setup_mcp.py` (Mac).
   It works out the right paths for your computer and writes them into Claude
   Desktop's settings. Anything else you already have connected is left alone,
   and your old settings file is backed up first.
3. **Quit Claude Desktop completely** -- not just closing the window. Right-click
   its taskbar icon and choose Quit (or end it in Task Manager), then reopen it.
4. Ask it a territory question.

**Privacy.** The bridge runs on your machine and talks to Claude Desktop through
a local pipe. It is not a website and nothing about it is reachable from the
internet. Claude receives only the answer to the specific question you ask --
never the whole database. If you ask "who should I see in Norfolk", it gets the
Norfolk shortlist, nothing more.

**What Claude can do through it:**

| Tool | What it does |
|------|--------------|
| `territory_summary` | Overall state: counts, YTD vs prior year, top priorities, dormant branches |
| `who_to_visit` | Ranked visit list with reasons; filter by market or tier |
| `get_account` | One account in full: contacts, sales by brand, whitespace, follow-ups, visit notes |
| `search_calls` | Search every visit note by text, account, brand or attendee |
| `find_opportunities` | Dormant branches and whitespace |
| `brand_performance` | How a line is doing across the territory |
| `open_followups` | Everything owed, overdue flagged |
| `recent_news` | Saved market/manufacturer news |
| `buying_groups` | Branches that buy as one account, with combined sales |
| `line_card` | Your Big Rivers line card |
| `list_markets` | Markets and account counts |
| `log_call` | Log a visit by talking to it |
| `add_followup` | Add a follow-up by talking to it |

The two write tools (`log_call`, `add_followup`) only ever **add** records --
nothing deletes or overwrites your history.

**If Claude Desktop doesn't see it:** make sure you fully quit and reopened the
app, and that the Flask app has been run at least once (that's what creates the
database). Re-running `setup_mcp.bat` is harmless.

## How the News feed works

The News page has three refresh buttons, so you can pull just the part you
want rather than waiting on every search:

- **Refresh NE/IA** -- business insight for your territory: commercial
  construction and development projects, data center builds, groundbreakings
  on hospitals/schools/apartments, economic development announcements, and
  building permits and housing starts across Nebraska and Iowa. This is
  pipeline: who's building what, where.
- **Refresh partners** -- news for every line on your Big Rivers line card,
  plus their corporate parents (A.O. Smith, Aalberts, American Bath Group,
  Lincoln Electric, Zurn and the rest), since acquisitions and leadership
  changes usually break under the parent's name rather than the brand's.
- **Refresh everything** -- the above plus commodity prices (copper, steel,
  PVC resin) for your pricing conversations.

The manufacturer list comes from `brm/linecard.py`, transcribed from your line
card PDF -- not from whatever brand strings happen to appear in a sales export.
That matters in both directions: the card carries lines with no sales yet
(**Shurjoint** currently has zero), and it correctly excludes **CircuitSolver**,
which is a KS/MO/S IL line and not yours. Each entry also carries context terms
so generic names like "Salo", "Harris" or "Stingray" return trade news instead
of noise. Manufacturer articles are automatically tagged to the matching brand,
so they show up on that brand's page.

Searches use Google News' free RSS (no account or API key). Only those short
search terms go out over the network -- nothing about your accounts or sales.
Results are saved locally so they build up over time; duplicate articles (same
URL) aren't added twice.

If your line card changes, edit `brm/linecard.py` -- it's a plain list with a
comment explaining each field.

If you'd rather use a paid news API (e.g. NewsAPI.org) instead of or in
addition to this, set the `BRM_NEWS_API_KEY` environment variable and
extend `brm/news.py` -- it's structured so a new fetch function can be
dropped in and registered alongside the existing one without touching
anything else.

You can always skip live fetching entirely and use **Add a news item
manually** on the News page to paste in an article or write your own note.

## Updating to a newer version of the app

**Double-click `update.bat`.** That's it.

It downloads the current version, backs up your database and your existing
program files, then replaces only the program files. Your `data` folder --
database, imports, backups -- is never touched, so accounts, calls, contacts,
follow-ups, groups and notes all survive exactly as you left them. New database
columns are added in place on the next start.

If the app is running while you update, **it restarts itself within a few
seconds** -- just refresh your browser. You don't need to close the black
window.

Two things worth knowing:

- **It refuses to install anything that isn't this app.** If the download is
  damaged or points at the wrong file, it says so and changes nothing.
- **Every update is reversible.** Your previous program files are kept in
  `data/code_backups/<date-time>/`, and the database is copied to
  `data/backups/` before anything is written.

If the download fails (no internet, a firewall in the way), grab the zip from
GitHub by hand and point the updater at it:

```
python update.py --zip C:\path\to\the.zip
```

### The fast loop for changing things

When you and Claude work out a change together:

1. Claude builds it and pushes.
2. You double-click **`update.bat`**.
3. You **refresh the browser**.

Your own work -- logging calls, checking off follow-ups, assigning groups,
editing accounts, importing spreadsheets -- needs none of that. It's live the
moment you do it, because every score and ranking is recalculated on each page
load rather than cached.

## Backing up your data

Your data lives in `data/territory.db`. To make a timestamped backup:

**Mac/Linux:** `./backup.sh`
**Windows:** double-click `backup.bat`

This copies the database into `data/backups/`. Do this before importing a
big new file if you want extra peace of mind, or just periodically. To
restore a backup, close the app, copy a file from `data/backups/` back to
`data/territory.db`, and restart.

## Project structure

```
app.py                  Flask app / all routes
mcp_server.py           Claude Desktop bridge (stdlib only)
setup_mcp.py/.bat       One-click Claude Desktop setup
brm/
  db.py                 SQLite connection, schema bootstrap + migrations
  schema.sql            Database schema
  importer.py           Parsers for the 3 source spreadsheets + merge logic
  queries.py            Dashboard / sales-intelligence / rollup queries
  intelligence.py       Priority scoring, whitespace, dormant branches, clustering
  linecard.py           Your Big Rivers line card (edit this if it changes)
  news.py               News search + manual entries
templates/              Page templates
static/                 CSS/JS (no build step, no CDN, works offline)
data/                   Your data -- gitignored, never committed
  territory.db          The database
  imports/              Copies of files you've uploaded via Import
  backups/              Backups you've created
  code_backups/         Previous program files, kept by each update
run.sh / run.bat        Start the app
update.py / update.bat  Install the latest version (never touches data/)
backup.sh / backup.bat  Back up your data
```

## Troubleshooting

- **"python3: command not found"** -- install Python from python.org and
  make sure it's on your PATH, then try again.
- **Port 5000 already in use** -- another program (or a previous copy of
  this app) is using that port. Close it, or run
  `PORT=5001 ./run.sh` (Mac/Linux) and open `http://127.0.0.1:5001`
  instead.
- **News refresh says searches failed** -- that's almost always your
  internet connection (or a strict firewall blocking outbound requests).
  Everything else in the app works fully offline; try News again later, or
  add items manually in the meantime.
- **I made a mistake importing a file** -- your data is still safe;
  imports only add/fill in, they don't delete. If something looks wrong,
  restore from a backup (see above) and re-import carefully.
