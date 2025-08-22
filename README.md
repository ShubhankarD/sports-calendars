# US Open 2025 Subscribeable Calendar (GitHub Pages)

This repo builds an `.ics` feed hourly and publishes it to GitHub Pages.

## Subscribe URL

After enabling Pages (see below), your URL will be:

https://<ShubhankarD>.github.io/<sports-calendars>/usopen_schedule.ics

Apple Calendar users can also try:

webcal://<ShubhakarD>.github.io/<sports-calendars>/usopen_schedule.ics

## How it works

- `src/usopen_calendar.py` fetches US Open feeds and writes `usopen_schedule.ics`.
- A GitHub Action runs hourly and pushes the file to the `gh-pages` branch.
- GitHub Pages serves the file at a stable URL that calendar apps can poll.

## Setup

1. Create the repo with these files on the default branch (usually `main`).
2. Go to **Settings → Pages**:
   - **Source**: select **Deploy from a branch**
   - **Branch**: choose `gh-pages` / `/ (root)`
3. Run the workflow manually once (**Actions → Publish ICS (hourly) → Run workflow**).
4. Copy the `.ics` URL and subscribe in your calendar:
   - **Google Calendar**: Settings → *Add calendar* → *From URL* → paste HTTPS URL
   - **Apple Calendar**: *File → New Calendar Subscription…* → paste `webcal://` or HTTPS
   - **Outlook**: *Add calendar → Subscribe from web* → paste HTTPS URL

## Notes

- Events have stable `UID`s so updates won’t duplicate entries.
- Default event duration is 2 hours; clients will update as the feed changes.
- The Action adds `.nojekyll` so Pages serves the raw `.ics` correctly.