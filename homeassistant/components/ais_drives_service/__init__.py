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
import mimetypes
import subprocess
from homeassistant.components import ais_cloud
from homeassistant.ais_dom import ais_global
aisCloud = ais_cloud.AisCloudWS()

DOMAIN = 'ais_drives_service'
G_LOCAL_FILES_ROOT = '/data/data/pl.sviete.dom/files/home/dom'
G_CLOUD_PREFIX = '/dyski-zdalne/'
G_RCLONE_CONF = '--config=/sdcard/rclone/rclone.conf'
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

    def sync_locations(call):
        _LOGGER.info("sync_locations")
        data.sync_locations(call)

    hass.services.async_register(
        DOMAIN, 'browse_path', browse_path)
    hass.services.async_register(
        DOMAIN, 'refresh_files', refresh_files)
    hass.services.async_register(
        DOMAIN, 'sync_locations', sync_locations)

    return True


class LocalData:
    """Class to hold local folders and files data."""

    def __init__(self, hass, config):
        """Initialize the books authors."""
        self.hass = hass
        self.folders = []
        self.folders_json = []
        self.config = config
        self.current_path = ""
        self.text_to_say = None
        self.rclone_serving_process = None

    @staticmethod
    def list_dir(path):
        dirs = os.listdir(path)
        dirs_filtered = []
        for d in dirs:
            if not d.startswith('.'):
                dirs_filtered.append(d)
        return dirs_filtered

    def refresh_files(self, call):
        self.current_path = os.path.abspath(G_LOCAL_FILES_ROOT)
        dirs = self.list_dir(self.current_path)
        self.folders = [ais_global.G_EMPTY_OPTION]
        for d in dirs:
            self.folders.append(self.current_path.replace(G_LOCAL_FILES_ROOT, "") + '/' + d)
        # cloud remotes from rclone
        self.folders.append(G_CLOUD_PREFIX)
        """Load the folders and files synchronously."""
        self.hass.services.call(
            'input_select',
            'set_options', {
                "entity_id": "input_select.folder_name",
                "options": sorted(self.folders)})

    def browse_path(self, call):
        """Load subfolders for the selected folder."""
        say = False
        if "say" in call.data:
            say = call.data["say"]
        if "path" not in call.data:
            _LOGGER.error("No path")
            return []

        if call.data["path"] == "..":
            # do not allow to browse outside root
            if self.current_path == G_LOCAL_FILES_ROOT:
                return []
            # check if this is cloud drive
            if self.is_rclone_path(self.current_path):
                if self.current_path == G_CLOUD_PREFIX:
                    self.current_path = G_LOCAL_FILES_ROOT
                elif self.current_path == G_CLOUD_PREFIX + self.rclone_remote_from_path(self.current_path):
                    self.current_path = G_CLOUD_PREFIX
                    self.rclone_append_listremotes(say)
                    return
                elif self.current_path.count("/") == 2:
                    k = self.current_path.rfind(":")
                    self.current_path = self.current_path[:k+1]
                    self.rclone_browse(self.current_path, say)
                    return
                else:
                    k = self.current_path.rfind("/")
                    self.current_path = self.current_path[:k]
                    self.rclone_browse(self.current_path, say)
                    return
            # local drive
            else:
                k = self.current_path.rfind("/" + os.path.basename(self.current_path))
                self.current_path = self.current_path[:k]
        elif call.data["path"] == G_CLOUD_PREFIX:
            self.current_path = G_CLOUD_PREFIX
            self.rclone_append_listremotes(say)
            return
        else:
            # check if this is cloud drive
            if self.is_rclone_path(call.data["path"]):
                self.current_path = call.data["path"]
                self.rclone_browse(call.data["path"], say)
                return
            self.current_path = G_LOCAL_FILES_ROOT + call.data["path"]

        if os.path.isdir(self.current_path):
            # browse dir
            self.folders = [ais_global.G_EMPTY_OPTION]
            if self.current_path != G_LOCAL_FILES_ROOT:
                self.folders.append('..')
            else:
                self.folders.append(G_CLOUD_PREFIX)
            dirs = self.list_dir(self.current_path)
            for dir in dirs:
                self.folders.append(self.current_path.replace(G_LOCAL_FILES_ROOT, "") + "/" + dir)
            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.folder_name",
                    "options": sorted(self.folders)})
            if say:
                if self.current_path == G_LOCAL_FILES_ROOT:
                    l_dir = "Wszystkie dyski"
                else:
                    l_dir = os.path.basename(self.current_path)
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": l_dir
                    })
            else:
                # beep
                self.hass.services.call(
                    'ais_ai_service',
                    'publish_command_to_frame', {
                        "key": 'tone',
                        "val": 97
                    })
        else:
            # file was selected, check mimetype and play if possible
            mime_type = mimetypes.MimeTypes().guess_type(self.current_path)[0]
            if mime_type is None:
                mime_type = ""
            if mime_type.startswith('text/'):
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": "Czytam: "
                    })
                with open(self.current_path) as file:
                    self.hass.services.call(
                        'ais_ai_service',
                        'say_it', {
                            "text": file.read()
                        })
            elif mime_type.startswith('audio/'):
                _url = self.current_path
                # TODO search the image cover in the folder
                # "IMAGE_URL": "file://sdcard/dom/.dom/dom.jpeg",
                _audio_info = {"NAME": os.path.basename(self.current_path),
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
                _LOGGER.info("Tego typu plików jeszcze nie obsługuję." + str(self.current_path))
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": "Tego typu plików jeszcze nie obsługuję."
                    })

    def sync_locations(self, call):
        if "source_path" not in call.data:
            _LOGGER.error("No source_path")
            return []
        if "dest_path" not in call.data:
            _LOGGER.error("No dest_path")
            return []
        if "say" in call.data:
            say = call.data["say"]
        else:
            say = False

        if say:
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Synchronizuję lokalizację " + call.data["source_path"] + " z " + call.data["dest_path"]
                    + " modyfikuję tylko " + call.data["source_path"]
                })

        rclone_cmd = ["rclone", "sync", call.data["source_path"], call.data["dest_path"],
                      "--transfers=1", "--stats=0", G_RCLONE_CONF]
        proc = subprocess.run(rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        #  will wait for the process to complete and then we are going to return the output
        if "" != proc.stderr:
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Błąd podczas synchronizacji: " + proc.stderr
                })
        else:
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Synchronizacja zakończona."
                })


    def is_rclone_path(self, path):
        if path.startswith(G_CLOUD_PREFIX):
            return True
        return False

    def rclone_remote_from_path(self, path):
        remote = path.replace(G_CLOUD_PREFIX, "")
        k = remote.find(":")
        remote = remote[:k+1]
        return remote

    def rclone_append_listremotes(self, say):
        self.folders = [ais_global.G_EMPTY_OPTION]
        self.folders.append('..')
        rclone_cmd = ["rclone", "listremotes", G_RCLONE_CONF]
        proc = subprocess.run(rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        #  will wait for the process to complete and then we are going to return the output
        if "" != proc.stderr:
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Nie można pobrać informacji o połączeniach do dysków: " + proc.stderr
                })
        else:
            for l in proc.stdout.split("\n"):
                    if len(l) > 0:
                        self.folders.append(G_CLOUD_PREFIX + l.strip())

            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.folder_name",
                    "options": sorted(self.folders)})
            if say:
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": G_CLOUD_PREFIX.replace("/", "")
                    })
            else:
                # beep
                self.hass.services.call(
                    'ais_ai_service',
                    'publish_command_to_frame', {
                        "key": 'tone',
                        "val": 97
                    })

    def rclone_browse_folder(self, path):
        rclone_cmd = ["rclone", "lsjson", path, G_RCLONE_CONF, '--drive-formats=txt']
        proc = subprocess.run(rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        #  will wait for the process to complete and then we are going to return the output
        if "" != proc.stderr:
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Nie można pobrać zawartości folderu " + proc.stderr
                })
        else:
            self.folders = [ais_global.G_EMPTY_OPTION]
            self.folders.append('..')
            self.folders_json = json.loads(proc.stdout)
            for item in self.folders_json:
                if self.current_path.endswith(':'):
                    self.folders.append(self.current_path + item["Path"])
                else:
                    self.folders.append(self.current_path + "/" + item["Path"])

            self.hass.services.call(
                'input_select',
                'set_options', {
                    "entity_id": "input_select.folder_name",
                    "options": sorted(self.folders)})
            if self.text_to_say is not None:
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": self.text_to_say
                    })
            else:
                # beep
                self.hass.services.call(
                    'ais_ai_service',
                    'publish_command_to_frame', {
                        "key": 'tone',
                        "val": 97
                    })

    def rclone_copy_and_read(self, path, item_path):
        # TODO clear .temp files...
        rclone_cmd = ["rclone", "copy", path, G_LOCAL_FILES_ROOT + '/.temp/', G_RCLONE_CONF, '--drive-formats=txt']
        proc = subprocess.run(rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if "" != proc.stderr:
            self.hass.services.call(
                'ais_ai_service',
                'say_it', {
                    "text": "Nie udało się pobrać pliku " + proc.stderr
                })
        else:
            try:
                with open(G_LOCAL_FILES_ROOT + '/.temp/' + item_path) as file:
                    self.hass.services.call(
                        'ais_ai_service',
                        'say_it', {
                            "text": file.read()
                        })
            except Exception as e:
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": "Nie udało się otworzyć pliku "
                    })

    def rclone_play_the_stream(self, path, item_path):
        rclone_cmd = ["rclone", "serve", 'http', path, G_RCLONE_CONF, '--addr=:8080']

        # try to kill previous serve if exists
        if self.rclone_serving_process is not None:
            self.rclone_serving_process.kill()
        #
        self.rclone_serving_process = subprocess.Popen(
                rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # import time
        # time.sleep(3)
        # start new serve
        url_to_stream = "http://127.0.0.1:8080/" + str(item_path)
        player_name = self.hass.states.get(
            'input_select.file_player').state
        player = ais_cloud.get_player_data(player_name)
        self.hass.services.call(
            'media_player',
            'play_media', {
                "entity_id": player["entity_id"],
                "media_content_type": "audio/mp4",
                "media_content_id": url_to_stream
            })
        _audio_info = {"NAME": os.path.basename(url_to_stream),
                       "MEDIA_SOURCE": ais_global.G_AN_LOCAL}
        _audio_info = json.dumps(_audio_info)
        # to set the stream image and title
        if player["device_ip"] is not None:
            self.hass.services.call(
                'media_player',
                'play_media', {
                    "entity_id": player["entity_id"],
                    "media_content_type": "ais_info",
                    "media_content_id": _audio_info
                })


    def rclone_browse(self, path, say):
        if say:
            if path == G_CLOUD_PREFIX + self.rclone_remote_from_path(path):
                self.text_to_say = self.rclone_remote_from_path(path)
            else:
                k = path.find(":")
                self.text_to_say = os.path.basename(path[k:])
        else:
            self.text_to_say = None

        is_dir = True
        mime_type = ""
        item_name = ""
        item_path = ""
        # check what was selected file or folder
        for item in self.folders_json:
            # now check if item is a dictionary
            if path.endswith(item["Path"]):
                item_path = item["Path"]
                is_dir = item["IsDir"]
                item_name = item["Name"]
                if "MimeType" in item:
                    mime_type = item["MimeType"]

        if is_dir:
            # browse the cloud drive
            path = path.replace(G_CLOUD_PREFIX, "")
            self.rclone_browse_folder(path)

        else:
            # file was selected, check the MimeType
            # "MimeType":"audio/mp3" and "text/plain" are supported
            path = path.replace(G_CLOUD_PREFIX, "")
            if mime_type is None:
                mime_type = ""
            if mime_type.startswith("audio/") or mime_type.startswith("video/"):
                # StreamTask().execute(fileItem);
                info = "Pobieram i odtwarzam: " + str(item_name)
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": info
                    })
                self.rclone_play_the_stream(path, item_path)
            elif mime_type.startswith("text/"):
                info = "Pobieram i czytam: " + str(item_name)
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": info
                    })
                self.rclone_copy_and_read(path, item_path)
            else:
                info = "Jeszcze nie obsługuję plików typu: " + str(mime_type)
                self.hass.services.call(
                    'ais_ai_service',
                    'say_it', {
                        "text": info
                    })


    @asyncio.coroutine
    def async_load_all(self):
        """Load all the folders and files."""

        def load():
            self.current_path = os.path.abspath(G_LOCAL_FILES_ROOT)
            try:
                dirs = self.list_dir(self.current_path)
                self.folders = [ais_global.G_EMPTY_OPTION]
                for d in dirs:
                    self.folders.append(self.current_path.replace(G_LOCAL_FILES_ROOT, "") + '/' + d)

                # list remotes from rclone
                self.folders.append(G_CLOUD_PREFIX)

                """Load the folders and files synchronously."""
                self.hass.services.call(
                    'input_select',
                    'set_options', {
                        "entity_id": "input_select.folder_name",
                        "options": sorted(self.folders)})
            except Exception as e:
                _LOGGER.error("Load all the folders and files, problem: " + str(e))

        yield from self.hass.async_add_job(load)