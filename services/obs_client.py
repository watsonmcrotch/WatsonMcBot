import asyncio
import logging
import obsws_python as obs
from typing import Optional

class OBSClient:
    def __init__(self, bot, host: str = 'localhost', port: int = 4455, password: Optional[str] = None):
        self.bot = bot
        self.host = host
        self.port = port
        self.password = password
        self.ws = None
        self.events = None
        self._connected = False
        self.current_scene = None

        self.scene_transitions = {
            ('BRB', 'Main (Camera Right)'): {'type': 'happy', 'data': {}},
            ('Fullscreen', 'Main (Camera Right)'): {'type': 'wave', 'data': {}},
            ('Main (Camera Right)', 'BRB'): {'type': 'brb', 'data': {}},
        }

        logging.info("OBS Client initialized with transitions:")
        for transition, reaction in self.scene_transitions.items():
            logging.info(f"  {transition[0]} -> {transition[1]}: {reaction['type']}")

    def connect(self):
        try:
            logging.info(f"Attempting to connect to OBS WebSocket at {self.host}:{self.port}")
            self.ws = obs.ReqClient(host=self.host, port=self.port, password=self.password)
            self._connected = True

            try:
                resp = self.ws.get_current_program_scene()
                self.current_scene = resp.scene_name
                logging.info(f"Currently active scene: {self.current_scene}")
            except Exception as e:
                logging.error(f"Error getting current scene: {e}", exc_info=True)

            # Set up event listener for scene changes
            self.events = obs.EventClient(host=self.host, port=self.port, password=self.password)
            self.events.callback.register(self.on_current_program_scene_changed)

            logging.info("Successfully connected to OBS WebSocket")
        except Exception as e:
            logging.error(f"Failed to connect to OBS WebSocket: {e}", exc_info=True)
            self._connected = False

    def on_current_program_scene_changed(self, data):
        try:
            previous_scene = self.current_scene
            current_scene = data.scene_name
            self.current_scene = current_scene

            logging.info(f"Scene change detected! {previous_scene} -> {current_scene}")

            transition_key = (previous_scene, current_scene)
            logging.info(f"Checking transition: {transition_key}")

            if transition_key in self.scene_transitions:
                reaction = self.scene_transitions[transition_key]
                logging.info(f"Found matching reaction: {reaction}")

                asyncio.run_coroutine_threadsafe(
                    self.bot.send_companion_event('reaction', {'type': reaction['type']}),
                    self.bot.loop
                )

                logging.info(f"Sent reaction: {reaction['type']}")
            else:
                logging.info(f"No reaction found for this transition")

            # Trigger intro boot sequence when leaving an Intro scene
            if previous_scene and 'intro' in previous_scene.lower():
                if hasattr(self.bot, 'overlay_manager'):
                    try:
                        asyncio.run_coroutine_threadsafe(
                            self.bot.overlay_manager.trigger_intro_transition(),
                            self.bot.loop
                        )
                        logging.info("Triggered intro boot sequence on alerts overlay")
                    except Exception as ie:
                        logging.error(f"Error triggering intro transition: {ie}")

            # Sync WatsonOS taskbar overlay with current scene
            if hasattr(self.bot, 'overlay_manager'):
                try:
                    self.bot.overlay_manager.sync_taskbar_scene(current_scene)
                except Exception as te:
                    logging.error(f"Error syncing taskbar: {te}")

        except Exception as e:
            logging.error(f"Error in scene change handler: {e}", exc_info=True)

    def disconnect(self):
        try:
            if self.events:
                self.events.disconnect()
            if self.ws:
                self.ws.disconnect()
            logging.info("Disconnected from OBS WebSocket")
        except Exception as e:
            logging.error(f"Error disconnecting from OBS: {e}")
        finally:
            self.ws = None
            self.events = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected
