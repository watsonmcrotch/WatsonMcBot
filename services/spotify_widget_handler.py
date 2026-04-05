from flask import Flask, jsonify, send_from_directory
import logging
from pathlib import Path
import asyncio
from threading import Thread
import os
import sys

logging.getLogger('werkzeug').setLevel(logging.ERROR)

class SpotifyWidgetHandler:
    def __init__(self, spotify_manager):
        self.overlays_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'overlays')
        os.makedirs(self.overlays_dir, exist_ok=True)
        
        self.app = Flask(__name__, static_url_path='', static_folder=self.overlays_dir)
        self.app.logger.disabled = True
        
        self.spotify_manager = spotify_manager
        self.last_track_id = None
        self.current_spotify_info = {}
        
        self.app.route('/spotify_info')(self.get_spotify_info)
        self.app.route('/')(self.serve_widget)
        self.app.route('/<path:filename>')(self.serve_file)

    def update_spotify_info(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            current_track = loop.run_until_complete(self.spotify_manager.get_current_track())

            if current_track:
                track_id = current_track['id']
                
                if track_id != self.last_track_id:
                    self.last_track_id = track_id
                    self.current_spotify_info = {
                        "track_name": current_track['name'],
                        "artist_name": current_track['artist'],
                        "album_name": current_track['album'],
                        "album_art_url": current_track.get('album_art_url', ''),
                        "progress_ms": current_track.get('progress_ms', 0),
                        "duration_ms": current_track.get('duration_ms', 0),
                        "is_playing": current_track.get('is_playing', False)
                    }
        except Exception as e:
            logging.error(f"Error updating Spotify info: {e}")

    def get_spotify_info(self):
        self.update_spotify_info()
        return jsonify(self.current_spotify_info)

    def serve_widget(self):
        return send_from_directory(self.overlays_dir, 'spotify_widget.html')

    def serve_file(self, filename):
        return send_from_directory(self.overlays_dir, filename)

    def start(self):
        thread = Thread(target=lambda: self.app.run(host='127.0.0.1', port=7500, debug=False), daemon=True)
        thread.start()