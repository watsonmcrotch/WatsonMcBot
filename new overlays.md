# New Stream Assets for 2026

## Style
WatsonOS (mock Windows 95 aesthetic), matching the watsonmcrotch website.  
Full reference: C:\Users\Sam\Stream\Website\public_html

## Logic
Move away from video-based redeems. All alerts/events must be handled via WatsonMcBot using webpage overlays instead. Do not remove or alter any existing chat logic or functionality. Only replace the visual alert layer. OBS will still use existing overlay pages for other bot interactions, so do not break or overwrite them. WatsonMcBot companion overlay must remain completely unchanged.

## Alerts (Webpages)
All alerts must render as WatsonOS-style pop-up windows. Each pop-up must include buttons and a visible pointer/cursor that automatically moves to and clicks the correct button after a short delay to dismiss the alert. All animations and sounds must be synchronised.

### Follows
Use existing follow alert logic but remove video playback. Instead, trigger a WatsonOS pop-up. Attempt to fetch https://twitch.tv/[username] and extract the profile image for display.  
Text content:  
[username] just followed! Thank you!  
[username] has been added to the registry.  
Play sound: C:\WatsonMcBot\sounds\follower.mp3  
Keep existing chat responses (puns, thank-you messages, etc.).

### Bits
Use tiered behaviour based on amount:  
1–9 bits: standard pop-up, minimal animation.  
10–68 and 70–99 bits: increased animation and hype.  
69 bits: spam-style pop-ups (multiple overlapping windows) themed around classic early internet ads (singles in your area, enlarge your penis, etc.), intentionally chaotic.  
100+ bits: major event with large animations, screen disruption, high intensity visuals.  
1000+ bits: trigger a full BSOD-style crash overlay that temporarily takes over the screen and simulates a system crash before recovering.  
All sound effects should be referenced as placeholders and loaded from C:\WatsonMcBot\sounds\.  
Do not alter existing chat behaviour.

### Raid
Sequence: red flashing warning window stating “Incoming connection attempt”, followed by a green confirmation window stating connection accepted. Display raider username, profile image (if available), and viewer count. Use layered overlays and strong visual hierarchy. Creative freedom on styling within WatsonOS constraints.

### Subscribers
Follow the same WatsonOS system style. Display all relevant data (username, tier, duration if available). Scale animation and intensity based on subscription tier. Creative freedom within established visual language.

### Gifted Subs
Display as an old-style file transfer window. Format: “X is sending a subscription to Y”. Include progress bar animation. For large gift quantities, escalate into a more dramatic/multi-window event with stronger animation and audio.

## Transitions

### Intro
Exact recreation of the startup sequence from watsonmcrotch.com. Match timing, visuals, and behaviour precisely.

### Outro
WatsonOS-style shutdown sequence. Should resolve into a quiet, static outro scene.

## Assets Required

1. Camera overlay (3:2 aspect ratio) Top right of overlay.
2. Gameplay overlay fills the screen to the left of the camera.
3. Fullscreen camera scene (larger camera frame variant, centred.)
4. Spotify “Now Playing” widget (WatsonOS themed):
   - Album artwork
   - Track title
   - Artist
   - Playback time/progress
   - Optional old-school EQ visualiser
5. Chat overlay (styled to match WatsonOS) which sits under the camera overlay to the right. 
6. Chat overlay for intro, outro, and fullscreen scenes which is larger.
7. A brb scene which mimics the websites screensaver. 
8. Intro and outro cards with subtle retro visual effects

## Key Considerations
All overlays must be dynamically controlled by the bot in real time, including scene updates and sound playback. Maintain strict separation between new alert systems and existing overlay pages to avoid breaking current functionality. No changes to WatsonMcBot companion overlay.

## Final task
Provide install instructions for OBS.