# IG Following Sort

A Chrome extension that brings Instagram mobile's "sort following by date" feature to the desktop browser.

## What it does

- Fetches your following list via Instagram's mobile API (same data source as the phone app's "Sort By → Date Followed")
- Displays the list in a popup sorted by follow date (newest or oldest first)
- Text search to filter by username or display name
- Click any user to open their Instagram profile
- 10-minute local cache to avoid repeated API calls

## Install

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked** and select the `extension/` folder
4. Log in to [instagram.com](https://www.instagram.com) in your browser
5. Click the **IG** icon in the toolbar to open the popup

## How it works

- Uses `i.instagram.com/api/v1/friendships/{uid}/following/?order=date_followed_latest`
- Authentication via browser's existing Instagram session cookies
- All data stays local (`chrome.storage`); nothing is sent to external servers
- The API returns the list sorted by date but does NOT include actual timestamp values (same behavior as the mobile app)

## Background

See [docs/feasibility_report.md](docs/feasibility_report.md) for the full feasibility analysis on why this approach was chosen.
