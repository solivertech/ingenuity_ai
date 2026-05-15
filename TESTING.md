# TESTING.md — IngenuityAI Manual Test Guide

This document covers end-to-end manual testing of the full system. Work through the sections in order — each section assumes the previous one passed.

---

## Prerequisites

Before testing anything, confirm you have:

- Python 3.11 installed (`python --version`)
- Node.js 18+ installed (`node --version`)
- All Python dependencies installed (`pip install -r requirements.txt`)
- Chromium installed (`playwright install chromium`)
- A `.env` file created from `.env.example` with at least one LLM API key set

Minimum viable `.env` for testing (Gmail and SMS are optional — mark those sections skipped if not configured):

```dotenv
ANTHROPIC_API_KEY=sk-ant-...   # or NVIDIA_API_KEY / CEREBRAS_API_KEY

GMAIL_SENDER=you@gmail.com
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_REFRESH_TOKEN=...        # run: python setup_gmail_oauth.py

EMAIL_FROM_NAME=IngenuityAI
```

---

## 1. Automated tests

Run the full test suite first. All tests should pass before proceeding to manual testing.

```bash
python -m pytest tests/ -v
```

**Expected:** All tests pass (green). Note any failures and resolve them before continuing.

---

## 2. Config validation

```bash
python main.py --check-setup
```

**Expected output:**
- Each enabled LLM backend reports `OK` or `UNAVAILABLE` (not an exception/traceback)
- Gmail reports `OK` if credentials are configured, or a clear skip message if not
- No Python errors on exit

---

## 3. CLI — core scraper modes

### 3.1 Dry run (no save, no email)

```bash
python main.py --dry-run --no-llm
```

**Expected:**
- Scraper runs and prints listings to the console
- No CSV written to `search_results/`
- No email sent
- No database writes (run `python main.py --history` after — this run should not appear)

### 3.2 Full run, rules only

```bash
python main.py --once --no-llm --no-email
```

**Expected:**
- Listings scraped, filtered, and scored
- CSV written to `search_results/`
- A new entry appears in `python main.py --history`
- No email sent

### 3.3 Full run with LLM

```bash
python main.py --once --no-email
```

**Expected:**
- LLM analysis runs (backend name printed in logs)
- CSV includes LLM output or analysis metadata
- History entry shows the backend used

### 3.4 Force a specific backend

Test each backend you have configured:

```bash
python main.py --dry-run --backend nvidia
python main.py --dry-run --backend cerebras
python main.py --dry-run --backend api      # Anthropic
python main.py --dry-run --backend ollama   # only if OLLAMA_NETWORK_HOST is set
```

**Expected:** Logs confirm the forced backend was used; no silent fallback to another.

### 3.5 Profile filtering

```bash
python main.py --once --no-email --no-llm --profile my_search
```

**Expected:** Only the `my_search` profile runs. Other profiles do not appear in logs.

### 3.6 Run history

```bash
python main.py --history
```

**Expected:** Table of past runs with dates, listing counts, and backend names. Pricing trends printed if enough runs exist.

### 3.7 Debug logging

```bash
python main.py --dry-run --no-llm --debug
```

**Expected:** DEBUG-level lines appear in output (more verbose than normal).

---

## 4. Dashboard — startup

Start all three services:

**Terminal 1:**
```bash
uvicorn dashboard.backend.app:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2:**
```bash
cd dashboard/frontend
npm run dev
```

Open `http://localhost:5173` in a browser.

**Expected:** Dashboard loads with a sidebar and the Run view visible.

---

## 5. Dashboard — Run view

### 5.1 Manual run

1. Leave all profiles unchecked (runs all profiles)
2. Set backend to **Auto**
3. Click **Run now**

**Expected:**
- Log terminal streams live output
- Run completes without Python tracebacks
- A success message appears at the end of the log

### 5.2 Dry run with email preview

1. Check **Dry run + preview**
2. Click **Run now**

**Expected:**
- Log streams as normal
- After completion, a rendered HTML email preview appears below the log
- The preview includes a listings table and (if LLM ran) an analysis section

### 5.3 Force backend from UI

1. Select **NVIDIA** (or any backend you have configured) from the backend dropdown
2. Click **Run now**

**Expected:** Logs confirm that specific backend was used.

### 5.4 Cancel a running job

1. Click **Run now**
2. While logs are streaming, click **Cancel**

**Expected:** Run stops; logs end with a cancellation message; no partial CSV written.

---

## 6. Dashboard — Profiles view

### 6.1 View profiles

Navigate to **Profiles**.

**Expected:** All profiles from `profiles.yaml` are listed with their key fields visible.

### 6.2 Create a profile

1. Click **+ New profile**
2. Fill in a unique `profile_id`, a label, select a domain, and add an email address
3. Save

**Expected:**
- Profile appears in the list
- `profiles.yaml` is updated on disk (check the file)

### 6.3 Edit a profile

1. Click edit on an existing profile
2. Change the label
3. Save

**Expected:** Updated label shown in the list; file updated on disk.

### 6.4 Delete a profile

1. Click delete on the profile you created in 6.2
2. Confirm deletion

**Expected:** Profile removed from list and from `profiles.yaml`.

---

## 7. Dashboard — History view

> Run `python main.py --once --no-email --no-llm` at least twice before testing this view to ensure there is data.

Navigate to **History**.

**Expected:**
- Metric cards show non-zero values (total runs, listings seen, etc.)
- Runs table shows at least the two runs you triggered
- Price trend charts render (may be flat if prices haven't changed between runs)

---

## 8. Dashboard — Domains view

### 8.1 View existing domains

Navigate to **Domains**.

**Expected:** The built-in `carvana_suvs` domain (and any previously saved domains) appear as cards showing their field list.

### 8.2 Domain Wizard — discover a new domain

> This test requires a working LLM backend and an active internet connection.

1. Click **Discover new domain**
2. Enter a public listing URL (e.g. a Craigslist category page, a real estate site, a job board)
3. Describe the fields you want: e.g. `"price, location, number of bedrooms, date posted"`
4. Enter a `domain_id` slug (letters/numbers/underscores only) and a display name
5. Click **Discover**

**Expected:**
- Log streams in real time showing fetch → LLM → validation steps
- After completion, a field table appears listing discovered fields with their types and paths
- Optionally edit field display names/types, then click **Save**
- The domain card appears in the Domains list

### 8.3 Use a discovered domain in a profile

1. In Profiles, create a new profile with `domain_id` set to the domain you just saved
2. Add a `filter_rules` entry if applicable
3. Run a dry run with that profile selected

**Expected:** Logs show the generic adapter being used; listings from the new domain are extracted and printed.

### 8.4 Delete a domain

1. Click **Delete** on the domain you created in 8.2

**Expected:** Domain card removed; the JSON file in `domains/saved/` is deleted.

---

## 9. Dashboard — Docs view

### 9.1 View docs

Navigate to **Docs**.

**Expected:** Any `.md` files in `reference_data/` are listed.

### 9.2 Create a doc manually

1. Click **+ New doc**
2. Enter a filename (e.g. `test_doc.md`) and write some content
3. Save

**Expected:** Doc appears in the list; file exists in `reference_data/`.

### 9.3 Generate a doc with AI

> Requires Cerebras API key configured and `cerebras_enabled: true`.

1. Click **Generate with AI**
2. Fill in a subject and any context
3. Click **Generate**

**Expected:** AI-generated content populates the editor. Review and save.

### 9.4 Edit and delete

1. Open the doc created in 9.2, modify the content, save
2. Delete the doc

**Expected:** File updated on disk after edit; file removed after delete.

---

## 10. Dashboard — Settings view

### 10.1 Edit a setting

1. Navigate to **Settings**
2. Change `request_delay_seconds` to a different value (e.g. `3`)
3. Save

**Expected:** Change persists — refresh the page and confirm the new value is shown.

### 10.2 Verify secrets are masked

**Expected:** Fields like `ANTHROPIC_API_KEY` display as `***` and are not editable in the UI.

### 10.3 Verify setting takes effect

Run the scraper after changing `request_delay_seconds`. Confirm in the debug logs that the new delay is applied between requests.

---

## 11. Dashboard — System view

Navigate to **System**.

### 11.1 Health checks

**Expected:** Each configured component shows a green (OK) or yellow (warning/not configured) status dot. No unexpected red indicators.

| Component | What to verify |
|---|---|
| Profiles | Green if `profiles.yaml` exists with at least one profile |
| Playwright | Green if Chromium is installed |
| Anthropic API | Green if `ANTHROPIC_API_KEY` is set |
| Cerebras API | Green if `CEREBRAS_API_KEY` is set |
| NVIDIA | Green if `NVIDIA_API_KEY` is set |
| Ollama | Green if `OLLAMA_NETWORK_HOST` is reachable |
| Gmail | Green if OAuth token is valid |

### 11.2 Install Chromium (if Playwright is red)

Click **Install Chromium** and confirm the install completes with a success message in the streamed output.

### 11.3 Live log stream

**Expected:** The log panel updates in real time as backend activity occurs. Trigger a run in a separate tab and confirm log lines appear here too.

---

## 12. Dashboard — Schedule view

### 12.1 Set a schedule

1. Navigate to **Schedule**
2. Enable scheduling
3. Set interval to `1` hour (or set a specific time)
4. Select one or more profiles
5. Save

**Expected:** Schedule is saved; `dashboard_settings.json` reflects the change.

### 12.2 Verify schedule fires (optional — long test)

Wait for the scheduled interval to elapse, then check **History** for a new run entry.

### 12.3 Disable schedule

1. Return to **Schedule**
2. Disable scheduling
3. Save

**Expected:** No further automatic runs occur.

---

## 13. Email alerts

> Requires Gmail configured and `send_email: true` in Settings.

### 13.1 Force send

```bash
python main.py --once --email
```

**Expected:** An HTML email arrives at the address(es) in `email_to` for each profile. The email should contain:
- A listings table with scores
- LLM analysis section (if LLM ran)
- Price trend charts (if history exists)
- CSV attachment

### 13.2 Conditional send (new listings only)

Set `email_only_on_new_or_drops: true` on a profile. Run twice in quick succession.

**Expected:** Email sent on the first run (new listings detected); no email on the second run (same listings, no price changes).

### 13.3 Price drop detection

Manually update a listing's price in `history.db` to simulate a drop, then run again.

**Expected:** Email sent with a price drop indicator on the affected listing.

---

## 14. Web portal

> Requires the backend running (`uvicorn ...`) and the portal built or the webapp dev server running.

Start the webapp dev server if not already running:

```bash
cd dashboard/webapp
npm run dev   # http://localhost:5174
```

Navigate to `http://localhost:5174/portal`.

### 14.1 First-time admin setup

On the first visit with no existing accounts, you should be prompted to create an admin account.

1. Fill in a username and password
2. Submit

**Expected:** Redirected to the admin dashboard.

### 14.2 Admin — Profiles CRUD

1. Create a new profile via the portal UI
2. Edit the profile
3. Delete the profile

**Expected:** Changes reflected in `profiles.yaml` on disk.

### 14.3 Admin — Docs

1. Create and save a reference doc
2. Generate a doc with AI (if Cerebras is configured)
3. Delete the doc

**Expected:** Files created/removed in `reference_data/`.

### 14.4 Admin — Users

1. Create a second user account and assign a profile to them
2. Log out
3. Log in as the new user

**Expected:** User can only see their assigned profile; admin-only actions are not visible.

### 14.5 User — read/edit own profile

As the non-admin user:

1. View the assigned profile
2. Edit a field (e.g. email address)
3. Save

**Expected:** Change saved; user cannot access other profiles or settings.

### 14.6 JWT expiry / logout

Click **Logout**.

**Expected:** Redirected to the login page; subsequent API requests return 401.

---

## 15. LLM fallback chain

Test that the fallback chain works by selectively disabling backends.

### 15.1 Primary fails, falls back

1. In Settings, disable `nvidia_enabled`
2. Run `python main.py --dry-run`

**Expected:** Logs show NVIDIA skipped or failed; Cerebras (or the next enabled backend) is used.

### 15.2 All cloud backends disabled, Ollama used

1. Disable `nvidia_enabled`, `cerebras_enabled`, `anthropic_enabled`
2. Ensure `ollama_enabled: true` and `OLLAMA_NETWORK_HOST` is set
3. Run `python main.py --dry-run`

**Expected:** Logs show Ollama used.

### 15.3 All backends disabled

1. Disable all backends including Ollama
2. Run `python main.py --dry-run`

**Expected:** Run completes without error; logs state no LLM backend available; scoring and output still work.

Re-enable your preferred backends after this test.

---

## 16. Edge cases

### 16.1 Empty search results

Configure a profile with filters strict enough to return zero listings (e.g. `max_price: 1`).

```bash
python main.py --once --no-email --profile <that_profile>
```

**Expected:** Run completes without error; logs report zero listings found; no CSV written (or an empty one); no email sent.

### 16.2 Malformed profiles.yaml

Add a profile with a missing required field (e.g. no `profile_id`) to `profiles.yaml`, then run:

```bash
python main.py --once --no-email
```

**Expected:** Clear validation error message identifying the bad profile; program exits without a traceback.

Restore `profiles.yaml` to a valid state after this test.

### 16.3 Invalid domain_id

Set a profile's `domain_id` to a string that doesn't match any built-in or saved domain, then run.

**Expected:** Clear error identifying the unknown domain; other profiles (if any) continue normally.

### 16.4 Network timeout

Disconnect from the internet (or block the target domain in your firewall), then run:

```bash
python main.py --dry-run --no-llm
```

**Expected:** Scraper handles the timeout gracefully and logs the failure; no crash.

---

## 17. Tauri desktop app (optional)

> Only run if you have Rust installed and want to test the packaged desktop experience.

```bash
cd dashboard/frontend
npx @tauri-apps/cli build --debug
```

Install the generated `.exe` from `src-tauri/target/debug/bundle/nsis/`.

**Expected:**
- App launches and places an icon in the system tray
- Double-clicking the tray icon opens the dashboard window
- All dashboard views work identically to the browser version
- Closing the window hides to tray; right-click → Quit fully exits
- The backend process (`uvicorn`) starts and stops with the app

---

## Pass criteria summary

| Area | Must pass |
|---|---|
| Automated tests | All green |
| Config validation | `--check-setup` exits cleanly |
| CLI modes | dry-run, once, no-llm, force backend, profile filter, history |
| Dashboard startup | Loads at localhost:5173 |
| Run view | Manual run, dry run preview, cancel |
| Profiles | Create, edit, delete |
| History | Runs and trends visible after data exists |
| Domains | Wizard completes and saves; domain usable in a profile |
| Docs | Create, generate (if Cerebras), edit, delete |
| Settings | Change persists across page refresh |
| System | All configured components green |
| Email | HTML email received with expected content |
| Web portal | Admin and user roles work correctly |
| LLM fallback | Chain degrades gracefully when backends are disabled |
| Edge cases | Empty results, bad config, and network failure all handled without crashes |
