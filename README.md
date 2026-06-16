# Sports Subscribeable Calendars (GitHub Pages)

This repo builds `.ics` feeds hourly and publishes them to GitHub Pages.

## Subscribe URL

After enabling Pages (see below), your URLs will be:

https://ShubhankarD.github.io/sports-calendars/usopen_schedule.ics

https://ShubhankarD.github.io/sports-calendars/worldcup_schedule.ics

Apple Calendar users can also try:

webcal://ShubhakarD.github.io/sports-calendars/usopen_schedule.ics

webcal://ShubhankarD.github.io/sports-calendars/worldcup_schedule.ics

## How it works

- `run_tournament.py` fetches US Open feeds and writes `usopen_schedule.ics`.
- `run_worldcup.py` fetches the FIFA World Cup 2026 schedule and writes `worldcup_schedule.ics`.
- A GitHub Action runs hourly and pushes the files to the `gh-pages` branch.
- GitHub Pages serves the files at stable URLs that calendar apps can poll.

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
