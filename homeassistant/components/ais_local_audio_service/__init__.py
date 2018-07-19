# -*- coding: utf-8 -*-
"""
Support for AIS local audio

For more details about this component, please refer to the documentation at
https://ai-speaker.com
"""
import asyncio
import logging
import os
import json
from homeassistant.components import ais_cloud
from homeassistant.ais_dom import ais_global
aisCloud = ais_cloud.AisCloudWS()

DOMAIN = 'ais_local_audio_service'
G_LOCAL_FILES_ROOT = '/sdcard/dom'
_LOGGER = logging.getLogger(__name__)
G_FOLDERS = []
G_FILES = []


@asyncio.coroutine
def async_setup(hass, config):
    """Register the service."""
    config = config.get(DOMAIN, {})
    _LOGGER.info("Initialize the folders and files list.")
    data = hass.data[DOMAIN] = LocalData(hass, config)
    yield from data.async_load_all()

    # register services
    def browse_path(call):
        _LOGGER.info("browse_path")
        data.browse_path(call)

    hass.services.async_register(
        DOMAIN, 'browse_path', browse_path)

    return True


class LocalData:
    """Class to hold local folders and files data."""

    def __init__(self, hass, config):
        """Initialize the books authors."""
        self.hass = hass
        self.folders = []
        self.files = []
        self.path = ""
        self.config = config


    def browse_path(self, call):
        """Load subfolders for the selected folder."""
        if "path" not in call.data:
            _LOGGER.error("No path")
            return []
        else:
            if call.data["path"] == "..":
                k = self.path.rfind("/" + os.path.basename(self.path))
                self.path = self.path[:k]
            else:
                self.path = G_LOCAL_FILES_ROOT + call.data["path"]

        if os.path.isdir(self.path):
            # browse dir
            self.folders = [ais_global.G_EMPTY_OPTION]
            if self.path != G_LOCAL_FILES_ROOT:
                self.folders.append('..')
            dirs = os.listdir(self.path)
            for dir in dirs:
                self.folders.append(self.path.replace(G_LOCAL_FILES_ROOT, "") + "/" + dir)
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.folder_name",
                    "options": sorted(self.folders)})
        else:
            # file was selected
            if self.path.endswith('.txt'):
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": "Czytam zawartość pliku"
                    })
                with open(self.path) as file:
                    self.hass.services.call(
                        'ais_ai_service',
                        'say_it', {
                            "text": file.read()
                        })
            elif self.path.endswith('.mp3'):
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": "Włączam"
                    })
                _url = self.path
                # TODO search the image in the folder
                # "IMAGE_URL": "file://sdcard/dom/.dom/dom.jpeg",
                _audio_info = {"NAME": os.path.basename(self.path),
                               "MEDIA_SOURCE": ais_global.G_AN_LOCAL}
                _audio_info = json.dumps(_audio_info)

                if _url is not None:
                    player_name = self.hass.states.get(
                        'input_select.file_player').state
                    player = ais_cloud.get_player_data(player_name)
                    self.hass.services.call(
                        'media_player',
                        'play_media', {
                            "entity_id": player["entity_id"],
                            "media_content_type": "audio/mp4",
                            "media_content_id": _url
                        })
                    # set stream image and title
                    if player["device_ip"] is not None:
                        self.hass.services.call(
                            'media_player',
                            'play_media', {
                                "entity_id": player["entity_id"],
                                "media_content_type": "ais_info",
                                "media_content_id": _audio_info
                            })
            else:
                _LOGGER.info("Tego typu plików jeszcze nie obsługuję." + str(self.path))
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": "Tego typu plików jeszcze nie obsługuję."
                    })


    @asyncio.coroutine
    def async_load_all(self):
        """Load all the folders and files."""

        def load():
            self.path = os.path.abspath(G_LOCAL_FILES_ROOT)
            dirs = os.listdir(self.path)
            self.folders = [ais_global.G_EMPTY_OPTION]
            for d in dirs:
                self.folders.append(self.path.replace(G_LOCAL_FILES_ROOT, "") + '/' + d)

            """Load the folders and files synchronously."""
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.folder_name",
                    "options": sorted(self.folders)})

        yield from self.hass.async_add_job(load)
