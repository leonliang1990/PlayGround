# Instagram Following Filter (Local)

A local Streamlit tool to import Instagram export data, filter followed accounts, run region/profession matching, and open profile pages quickly.

## Features

- Import following data from Instagram export JSON files.
- Sort by follow timestamp and filter by date range.
- Region classification from text rules with editable keyword list.
- Hybrid search: rule filtering + similarity ranking for free-text input (for example: `designer`, `seoul`, `ny photographer`).
- Interaction-aware ranking from export signals:
  - Likes count
  - Saved count
  - Collection/category tags (when discoverable from saved export JSON)
- Semi-auto metadata draft generator (public profile best-effort crawl to CSV)
- On-demand avatar loading from public profile metadata (best effort).
- One-click open Instagram profile page.

## Quick Start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run:

```bash
streamlit run app/main.py
```

## Input Data

- Preferred: Instagram export JSON package containing `followers_and_following/following*.json`.
- Optional but recommended in the same export package:
  - `likes/**/*.json` or `likes*.json`
  - `saved/**/*.json`, `*saved*.json`, `collections/**/*.json`
- Optional metadata CSV with columns:
  - `username` (required)
  - `bio`, `full_name`, `location`, `profession` (optional)

## Notes

- Everything is processed locally in SQLite (`data/app.db`).
- Avatar loading may fail for some accounts due to public page restrictions; the app falls back to placeholders.
- Interest signals are extracted with best-effort heuristics because Instagram export structure can vary by account/version.

## Chrome Extension (MVP)

A Chrome extension that brings Instagram mobile's "sort following by date" feature to the desktop browser.

### What it does

- Fetches your following list via Instagram's mobile API (same data source as the phone app's "Sort By → Date Followed")
- Displays the list in a popup sorted by follow date (newest or oldest first)
- Text search to filter by username or display name
- Click any user to open their Instagram profile
- 10-minute local cache to avoid repeated API calls

### Install

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked** and select the `extension/` folder from this project
4. Log in to [instagram.com](https://www.instagram.com) in your browser
5. Click the **IG** icon in the toolbar to open the popup

### Technical notes

- Uses `i.instagram.com/api/v1/friendships/{uid}/following/?order=date_followed_latest`
- Authentication via browser's existing Instagram session cookies
- All data stays local (chrome.storage); nothing is sent to external servers
- The API returns the list sorted by date but does NOT include actual timestamp values (same as the mobile app)

### Background

See [docs/feasibility_report.md](docs/feasibility_report.md) for the full feasibility analysis.
