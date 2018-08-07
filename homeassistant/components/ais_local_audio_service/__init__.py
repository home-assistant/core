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
G_LOCAL_FILES_ROOT = '/data/data/pl.sviete.dom/files/home/dom'
G_CURRENT_PATH = ''
_LOGGER = logging.getLogger(__name__)


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

    def refresh_files(call):
        _LOGGER.info("refresh_files")
        data.refresh_files(call)

    hass.services.async_register(
        DOMAIN, 'browse_path', browse_path)
    hass.services.async_register(
        DOMAIN, 'refresh_files', refresh_files)

    return True


class LocalData:
    """Class to hold local folders and files data."""

    def __init__(self, hass, config):
        """Initialize the books authors."""
        self.hass = hass
        self.folders = []
        self.files = []
        self.config = config

    def refresh_files(self, call):
        global G_CURRENT_PATH
        G_CURRENT_PATH = os.path.abspath(G_LOCAL_FILES_ROOT)
        dirs = os.listdir(G_CURRENT_PATH)
        self.folders = [ais_global.G_EMPTY_OPTION]
        for d in dirs:
            self.folders.append(G_CURRENT_PATH.replace(G_LOCAL_FILES_ROOT, "") + '/' + d)
        """Load the folders and files synchronously."""
        self.hass.services.call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.folder_name",
                "options": sorted(self.folders)})

    def browse_path(self, call):
        """Load subfolders for the selected folder."""
        global G_CURRENT_PATH
        if "path" not in call.data:
            _LOGGER.error("No path")
            return []
        else:
            if call.data["path"] == "..":
                k = G_CURRENT_PATH.rfind("/" + os.path.basename(G_CURRENT_PATH))
                G_CURRENT_PATH = G_CURRENT_PATH[:k]
            else:
                G_CURRENT_PATH = G_LOCAL_FILES_ROOT + call.data["path"]

        if os.path.isdir(G_CURRENT_PATH):
            # browse dir
            self.folders = [ais_global.G_EMPTY_OPTION]
            if G_CURRENT_PATH != G_LOCAL_FILES_ROOT:
                self.folders.append('..')
            dirs = os.listdir(G_CURRENT_PATH)
            for dir in dirs:
                self.folders.append(G_CURRENT_PATH.replace(G_LOCAL_FILES_ROOT, "") + "/" + dir)
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.folder_name",
                    "options": sorted(self.folders)})
        else:
            # file was selected
            if G_CURRENT_PATH.endswith('.txt'):
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": "Czytam: "
                    })
                with open(G_CURRENT_PATH) as file:
                    self.hass.services.call(
                        'ais_ai_service',
                        'say_it', {
                            "text": file.read()
                        })
            elif G_CURRENT_PATH.endswith('.mp3'):
                _url = G_CURRENT_PATH
                # TODO search the image cover in the folder
                # "IMAGE_URL": "file://sdcard/dom/.dom/dom.jpeg",
                _audio_info = {"NAME": os.path.basename(G_CURRENT_PATH),
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
                _LOGGER.info("Tego typu plików jeszcze nie obsługuję." + str(G_CURRENT_PATH))
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": "Tego typu plików jeszcze nie obsługuję."
                    })


    @asyncio.coroutine
    def async_load_all(self):
        """Load all the folders and files."""

        def load():
            global G_CURRENT_PATH
            G_CURRENT_PATH = os.path.abspath(G_LOCAL_FILES_ROOT)
            try:
                dirs = os.listdir(G_CURRENT_PATH)
                self.folders = [ais_global.G_EMPTY_OPTION]
                for d in dirs:
                    self.folders.append(G_CURRENT_PATH.replace(G_LOCAL_FILES_ROOT, "") + '/' + d)

                """Load the folders and files synchronously."""
                self.hass.services.call(
                    'input_select',
                    'set_options', {
                        "entity_id": "input_select.folder_name",
                        "options": sorted(self.folders)})
            except Exception as e:
                _LOGGER.error("Load all the folders and files, problem: " + str(e))

        yield from self.hass.async_add_job(load)
