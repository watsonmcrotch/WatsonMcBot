# WatsonOS Stream Overlay — OBS Setup Guide

All overlays are browser sources served from `C:\WatsonMcBot\overlays\`.
The bot's Flask server (port 5555) serves these files. Shared assets live in `assets/css/watsonos.css` and `assets/js/watsonos.js`.

## Prerequisites
- WatsonMcBot running (WebSocket server on port 8555)
- OBS Studio with Browser Source support
- Flask server running on port 5555 (serves all overlays and assets)
- Spotify widget server running on port 7500 (serves Spotify data)

---

## Scene: Main (Camera Right)

### 1. Background
- **Type:** Browser Source
- **URL:** `http://localhost:5555/background_main.html`
- **Width:** 1920 | **Height:** 1080
- **Position:** 0, 0
- Place this as the BOTTOM-MOST source (teal WatsonOS desktop with taskbar)

### 2. Gameplay Overlay
- **Type:** Browser Source
- **URL:** `http://localhost:5555/gameplay_overlay.html`
- **Width:** 1920 | **Height:** 1080
- **Position:** 0, 0 (fills left area, 1500px wide)
- Place your **Game Capture** source *inside* this browser source's transparent viewport area

### 3. Camera Overlay
- **Type:** Browser Source
- **URL:** `http://localhost:5555/camera_overlay.html`
- **Width:** 1920 | **Height:** 1080
- **Position:** 0, 0 (auto-positions top-right, 420x280)
- Place your **Video Capture Device** (webcam) source *behind* this overlay, cropped to fit the viewport

### 4. Chat Overlay (Small)
- **Type:** Browser Source
- **URL:** `http://localhost:5555/chat_watsonos_small.html`
- **Width:** 420 | **Height:** 772
- **Position:** 1500, 280 (below camera, right side, same width as camera)

### 5. Spotify Widget
- **Type:** Browser Source
- **URL:** `http://localhost:7500/spotify_watsonos.html`
- **Width:** 520 | **Height:** 163
- **Position:** Bottom-left, Y: 889 (fits between gameplay window and taskbar)

### 6. Stream Stats Widget
- **Type:** Browser Source
- **URL:** `http://localhost:5555/stats_watsonos.html`
- **Width:** 520 | **Height:** 163
- **Position:** Bottom-left, next to Spotify widget (X: 520, Y: 889) — or wherever preferred

### 7. Alerts Overlay (REQUIRED — add to ALL scenes)
- **Type:** Browser Source
- **URL:** `http://localhost:5555/alerts_overlay.html`
- **Width:** 1920 | **Height:** 1080
- **Position:** 0, 0
- **IMPORTANT:** Place this on TOP of all other sources
- Enable: "Shutdown source when not visible" = OFF
- Enable: "Refresh browser when scene becomes active" = OFF

### 8. Companion Overlay
- **Type:** Browser Source
- **URL:** `http://localhost:5555/companion.html`
- **Width / Height:** Match the companion widget dimensions
- This overlay is independent from the WatsonOS theme and must remain unchanged

---

## Scene: Fullscreen (Camera)

### 1. Background
- **Type:** Browser Source
- **URL:** `http://localhost:5555/background_fullscreen.html`
- **Width:** 1920 | **Height:** 1080
- **Position:** 0, 0
- Place as the BOTTOM-MOST source

### 2. Fullscreen Camera Overlay
- **Type:** Browser Source
- **URL:** `http://localhost:5555/fullscreen_camera_overlay.html`
- **Width:** 1920 | **Height:** 1080
- **Position:** 0, 0 (centred, 1280x720)
- Place webcam source behind, sized to fill the centred viewport

### 3. Chat Overlay (Large)
- **Type:** Browser Source
- **URL:** `http://localhost:5555/chat_watsonos_large.html`
- **Width:** 700 | **Height:** 900
- **Position:** Left side of screen (adjust to preference)

### 4. Alerts Overlay
- Same as above — add `alerts_overlay.html` on top

---

## Scene: BRB

### 1. BRB Scene
- **Type:** Browser Source
- **URL:** `http://localhost:5555/brb_scene.html`
- **Width:** 1920 | **Height:** 1080
- **Position:** 0, 0

---

## Scene: Intro

### 1. Intro Card (Starting Soon)
- **Type:** Browser Source
- **URL:** `http://localhost:5555/intro_card.html`
- **Width:** 1920 | **Height:** 1080
- **Position:** 0, 0
- Use as a "Starting Soon" holding screen

### 2. Intro Transition
- **Type:** Browser Source
- **URL:** `http://localhost:5555/intro_transition.html`
- **Width:** 1920 | **Height:** 1080
- **Position:** 0, 0
- This plays the full WatsonOS boot sequence
- **Tip:** Enable "Refresh browser when scene becomes active" so the boot replays each time
- Total duration: ~7 seconds, then shows teal desktop. Switch to Main scene after.

---

## Scene: Outro

### 1. Outro Transition
- **Type:** Browser Source
- **URL:** `http://localhost:5555/outro_transition.html`
- **Width:** 1920 | **Height:** 1080
- **Position:** 0, 0
- Enable "Refresh browser when scene becomes active"
- Total duration: ~10 seconds shutdown sequence

### 2. Outro Card (Stream Ended)
- **Type:** Browser Source
- **URL:** `http://localhost:5555/outro_card.html`
- **Width:** 1920 | **Height:** 1080
- **Position:** 0, 0
- Use as a final "Thanks for watching" screen

---

## Sound Placeholders

The alerts overlay expects sound files in `C:\WatsonMcBot\overlays\assets\sounds\`:

| File | Used By |
|------|---------|
| `follower.mp3` | Follow alerts |
| `bit_small.mp3` | 1-9 bit cheers |
| `bit_mid.mp3` | 10-99 bit cheers |
| `bit_mega.mp3` | 100+ bit cheers |
| `nice.mp3` | 69 bit spam |
| `error.mp3` | BSOD (1000+ bits) |
| `raid_warning.mp3` | Raid warning phase |
| `raid_accept.mp3` | Raid accepted phase |
| `sub_alert.mp3` | Subscription alerts |
| `giftsub.mp3` | Gift sub alerts |
| `giftsub_mass.mp3` | Mass gift sub alerts |

The intro/outro also use sounds from the same directory:
- `intro.mp3` — Intro transition boot sequence
- `outro.mp3` — Outro transition shutdown sequence

Place all sound files in `C:\WatsonMcBot\overlays\assets\sounds\`. If a file is missing, the alert will still display — only the sound will be silent.

---

## Architecture

All WatsonOS overlays share a common stack:

- **`assets/css/watsonos.css`** — Windows 95 theme variables and base styles
- **`assets/js/watsonos.js`** — WebSocket connection (port 8555), event bus, and shared utilities
- **`services/overlay_manager.py`** — Server-side alert coordinator; broadcasts events (`watsonos_follow`, `watsonos_bits`, `watsonos_raid`, `watsonos_sub`, `watsonos_giftsub`) to all connected overlays via WebSocket
- **`services/flask_server.py`** — Serves all overlay files and assets on port 5555
- **`services/spotify_widget_handler.py`** — Serves Spotify data on port 7500

Overlays connect to the WebSocket automatically on load and reconnect every 3 seconds if disconnected.

---

## Browser Source Settings (All Sources)

- **Custom CSS:** Leave empty
- **FPS:** 60
- **Hardware Acceleration:** Enabled (recommended)
- **Reroute Audio:** Enabled if you want OBS to capture alert sounds

---

## Troubleshooting

- **Overlays not loading?** Ensure the Flask server is running on port 5555. All overlay files are served from `http://localhost:5555/`.
- **Alerts not showing?** Check that WatsonMcBot is running and the WebSocket server is active on port 8555. The alerts overlay must be present in every scene.
- **Chat not appearing?** The chat overlays listen for `chat-message` events via WebSocket. Ensure the bot is connected to Twitch and broadcasting chat events.
- **Spotify widget blank?** Verify the Spotify widget server is running on port 7500 and Spotify is authenticated. This is a separate Flask instance from the main server.
- **Boot sequence not replaying?** Enable "Refresh browser when scene becomes active" on the intro transition source.
- **No sound on alerts?** Enable "Reroute Audio" on the browser source, and ensure sound files exist in `overlays/assets/sounds/`.
- **Styles broken?** Check that `assets/css/watsonos.css` and `assets/js/watsonos.js` are accessible at `http://localhost:5555/assets/css/watsonos.css`.
