from flask import Flask, jsonify, send_from_directory
import logging
from threading import Thread
import os
import time

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
            # Refresh token if needed
            if time.time() - self.spotify_manager.last_token_refresh > 3000 or not self.spotify_manager.spotify:
                self.spotify_manager.initialize_client()

            # Call spotipy directly — it's a synchronous library, no event loop needed
            current_track = self.spotify_manager.spotify.current_user_playing_track()

            if current_track and 'item' in current_track:
                track = current_track['item']
                album_art_url = track['album']['images'][0]['url'] if track['album']['images'] else ''
                self.last_track_id = track['id']

                self.current_spotify_info = {
                    "track_name": track['name'],
                    "artist_name": track['artists'][0]['name'],
                    "album_name": track['album']['name'],
                    "album_art_url": album_art_url,
                    "progress_ms": current_track.get('progress_ms', 0) or 0,
                    "duration_ms": track.get('duration_ms', 0) or 0,
                    "is_playing": current_track.get('is_playing', False)
                }
            else:
                self.current_spotify_info = {}
        except Exception as e:
            logging.error(f"Error updating Spotify info: {e}")

    def get_spotify_info(self):
        self.update_spotify_info()
        response = jsonify(self.current_spotify_info)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    def serve_widget(self):
        return send_from_directory(self.overlays_dir, 'spotify_watsonos.html')

    def serve_file(self, filename):
        return send_from_directory(self.overlays_dir, filename)

    def start(self):
        thread = Thread(target=lambda: self.app.run(host='127.0.0.1', port=7500, debug=False), daemon=True)
        thread.start()