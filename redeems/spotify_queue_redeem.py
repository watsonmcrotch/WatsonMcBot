import spotipy
import logging
from typing import Optional, Dict
import asyncio
import re
from difflib import SequenceMatcher

class SpotifyQueueHandler:
    def __init__(self, spotify_manager, db_manager):
        self.spotify_manager = spotify_manager
        self.spotify = spotify_manager
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

    def sanitize_search_query(self, query: str) -> str:
        query = query.strip().lower()
        query = re.sub(r'\s*[-:]\s*', ' by ', query)
        query = ' '.join(query.split())
        return query

    def similarity_ratio(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    async def search_track(self, search_query: str) -> Optional[Dict]:
        try:
            cleaned_query = self.sanitize_search_query(search_query)
            self.logger.debug(f"Cleaned query: {cleaned_query}")
            
            track_part = artist_part = cleaned_query
            if " by " in cleaned_query:
                parts = cleaned_query.split(" by ", 1)
                if len(parts) == 2:
                    track_part, artist_part = parts
            
            self.logger.debug(f"Track part: {track_part}, Artist part: {artist_part}")
            
            search_attempts = [
                f"track:\"{track_part}\" artist:\"{artist_part}\"",
                cleaned_query,
                f"track:{track_part} artist:{artist_part}",
            ]
            
            for query in search_attempts:
                results = await asyncio.to_thread(
                    self.spotify.spotify.search,
                    q=query,
                    type='track',
                    limit=10,
                    market='from_token'
                )
                
                if results['tracks']['items']:
                    scored_results = []
                    search_terms = [term.lower() for term in cleaned_query.split() 
                                if term not in {'by', 'from', '-', ':'}]
                    
                    for track in results['tracks']['items']:
                        score = 0
                        track_name = track['name'].lower()
                        artist_name = track['artists'][0]['name'].lower()

                        if track_name == track_part.lower():
                            score += 15
                        if artist_name == artist_part.lower():
                            score += 10

                        track_similarity = self.similarity_ratio(track_name, track_part)
                        artist_similarity = self.similarity_ratio(artist_name, artist_part)
                        score += (track_similarity * 8) + (artist_similarity * 6)

                        if cleaned_query == f"{track_name} by {artist_name}":
                            score += 20
                        
                        track_terms = track_name.split()
                        artist_terms = artist_name.split()
                        
                        for term in search_terms:
                            if term in track_terms:
                                score += 3
                            if term in artist_terms:
                                score += 2

                        lower_query = cleaned_query.lower()
                        is_live_requested = any(term in lower_query for term in ['live', 'concert', 'acoustic'])
                        is_karaoke_requested = 'karaoke' in lower_query
                        is_remix_requested = any(term in lower_query for term in ['remix', 'mix', 'edit', 'version'])

                        if not is_live_requested and any(term in track_name for term in [
                            'live', 'concert', 'acoustic', '(live)', '[live]', 'live at', 'live from'
                        ]):
                            score -= 15

                        if not is_karaoke_requested and any(term in track_name for term in [
                            'karaoke', 'instrumental', 'backing track'
                        ]):
                            score -= 20

                        if not is_remix_requested and any(term in track_name for term in [
                            'remix', ' mix', ' edit', 'version)', 'remaster'
                        ]):
                            score -= 10
                        
                        if len(track_terms) > len(search_terms) + 2:
                            score -= 2
                            
                        scored_results.append((score, track))
                        self.logger.debug(f"Track: {track_name} by {artist_name} - Score: {score}")
                    
                    if scored_results:
                        scored_results.sort(key=lambda x: x[0], reverse=True)
                        best_score = scored_results[0][0]
                        
                        if best_score >= 5:
                            best_match = scored_results[0][1]
                            self.logger.debug(f"Best match: {best_match['name']} by {best_match['artists'][0]['name']} (Score: {best_score})")
                            return best_match
                        
            return None
            
        except Exception as e:
            self.logger.error(f"Error in search_track: {e}")
            return None

    async def process_queue_request(self, channel, username: str, display_name: str, song_request: str) -> bool:
        self.logger.info(f"Processing queue request - User: {username}, Song: {song_request}")

        try:
            track = await self.search_track(song_request)

            if not track:
                await channel.send(f"Sorry {display_name}, I couldn't find that song...")
                return False

            track_uri = track['uri']
            track_name = track['name']
            artist_name = track['artists'][0]['name']

            current_playback = await asyncio.to_thread(
                self.spotify.spotify.current_playback
            )
            
            if not current_playback or not current_playback['is_playing']:
                await channel.send(f"Sorry {display_name}, there's no active playback right now!")
                return False

            if current_playback['item']['uri'] == track_uri:
                await channel.send(f"That's the song that's playing now {display_name} ya muppet.")
                return False

            queue = await asyncio.to_thread(self.spotify.spotify.queue)
            if any(track['uri'] == track_uri for track in queue['queue']):
                await channel.send(f"Good news! That song is already in the queue, {display_name}.")
                return False

            await asyncio.to_thread(
                self.spotify.spotify.add_to_queue,
                track_uri
            )

            self.logger.info(f"Successfully queued song for {username}: {track_name} by {artist_name}")
            await channel.send(f"Added: '{track_name}' by {artist_name} to the queue, {display_name}!")
            return True

        except spotipy.exceptions.SpotifyException as e:
            self.logger.error(f"Spotify API error for user {username}: {e}")
            if 'token expired' in str(e).lower():
                self.spotify.initialize_client()
                await channel.send(f"Had to refresh my connection {display_name}, try again!")
            else:
                await channel.send(f"Sorry {display_name}, something went wrong with Spotify...")
            return False

        except Exception as e:
            self.logger.error(f"Error processing queue request for user {username}: {e}")
            await channel.send("Something went wrong processing your request...")
            return False