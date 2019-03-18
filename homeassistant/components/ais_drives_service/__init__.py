# -*- coding: utf-8 -*-
"""
Support for AIS local audio

For more details about this component, please refer to the documentation at
https://ai-speaker.com
"""
import asyncio
import logging
import os
import signal
import json
import mimetypes
import subprocess
import time
from homeassistant.components import ais_cloud
from homeassistant.ais_dom import ais_global

aisCloud = ais_cloud.AisCloudWS()

DOMAIN = 'ais_drives_service'
G_LOCAL_FILES_ROOT = '/data/data/pl.sviete.dom/files/home/dom'
G_CLOUD_PREFIX = 'dyski-zdalne:'
G_RCLONE_CONF = '--config=/data/data/pl.sviete.dom/files/home/dom/rclone.conf'
G_RCLONE_URL_TO_STREAM = 'http://127.0.0.1:8080/'
G_LAST_BROWSE_CALL = None
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
        global G_LAST_BROWSE_CALL
        time_now = time.time()
        secs = 2
        if G_LAST_BROWSE_CALL is None:
            G_LAST_BROWSE_CALL = time_now
        else:
            secs = time_now - G_LAST_BROWSE_CALL
            G_LAST_BROWSE_CALL = time_now

        if secs < 1:
            _LOGGER.info("This call is blocked, secs: " + str(secs))
            return
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
        self.current_path = os.path.abspath(G_LOCAL_FILES_ROOT)
        self.text_to_say = None
        self.rclone_url_to_stream = None

    def beep(self):
        self.hass.services.call('ais_ai_service', 'publish_command_to_frame', {"key": 'tone', "val": 97})

    def say(self, text):
        self.hass.services.call('ais_ai_service', 'say_it', {"text": text})

    def refresh_files(self, call):
        pass
        # dirs = self.list_dir(self.current_path)
        # self.folders = [ais_global.G_EMPTY_OPTION]
        # for d in dirs:
        #     self.folders.append(self.current_path.replace(G_LOCAL_FILES_ROOT, "") + '/' + d)
        # # cloud remotes from rclone
        # self.folders.append(G_CLOUD_PREFIX)
        # """Load the folders and files synchronously."""
        # self.hass.services.call(
        #     'input_select',
        #     'set_options', {
        #         "entity_id": "input_select.folder_name",
        #         "options": sorted(self.folders)})

    def play_file(self):
        mime_type = mimetypes.MimeTypes().guess_type(self.current_path)[0]
        if mime_type is None:
            mime_type = ""
        if mime_type.startswith('text/'):
            self.say("Czytam: ")
            with open(self.current_path) as file:
                self.say(file.read())
        elif mime_type.startswith('audio/'):
            _url = self.current_path
            # TODO search the image cover in the folder
            # "IMAGE_URL": "file://sdcard/dom/.dom/dom.jpeg",
            _audio_info = {"NAME": os.path.basename(self.current_path),
                           "MEDIA_SOURCE": ais_global.G_AN_LOCAL,
                           "ALBUM_NAME": os.path.basename(os.path.dirname(self.current_path))}
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
                # skipTo
                position = ais_global.get_bookmark_position(_url)
                if position != 0:
                    self.hass.services.call(
                        'media_player',
                        'media_seek', {
                            "entity_id": player["entity_id"],
                            "seek_position": position
                        })
        else:
            _LOGGER.info("Tego typu plików jeszcze nie obsługuję." + str(self.current_path))
            self.say("Tego typu plików jeszcze nie obsługuję.")

        self.dispalay_current_path()

    def display_root_items(self, say):
        self.hass.states.set(
            "sensor.dyski", '', {
                0: {"name": "Dysk wewnętrzny", "icon": "harddisk",
                    "path": G_LOCAL_FILES_ROOT + "/dysk-wewnętrzny"},
                1: {"name": "Dyski zewnętrzne", "icon": "sd",
                    "path": G_LOCAL_FILES_ROOT + "/dyski-zewnętrzne"},
                2: {"name": "Dyski zdalne", "icon": "onedrive",
                    "path": G_CLOUD_PREFIX}})
        if say:
            self.say("Dyski")

    def dispalay_current_path(self):
        state = self.hass.states.get('sensor.dyski')
        items_info = state.attributes
        self.hass.states.set("sensor.dyski", self.current_path.replace(G_LOCAL_FILES_ROOT, ''), items_info)

    def display_current_items(self, say):
        local_items = []
        try:
            local_items = os.scandir(self.current_path)
        except Exception as e:
            _LOGGER.error("list_dir error: " + str(e))
        si = sorted(local_items, key=lambda en: en.name)
        self.folders = []
        for i in si:
            self.folders.append(i)

        items_info = {0: {"name": ".", "icon": "", "path": G_LOCAL_FILES_ROOT},
                      1: {"name": "..", "icon": "", "path": ".."}}
        for idx, entry in enumerate(si):
            items_info[idx + 2] = {}
            items_info[idx + 2]["name"] = entry.name
            items_info[idx + 2]["icon"] = self.get_icon(entry)
            items_info[idx + 2]["path"] = entry.path

        self.hass.states.set(
            "sensor.dyski", self.current_path.replace(G_LOCAL_FILES_ROOT, ''), items_info)
        if say:
            self.say("ok")

    def display_current_remotes(self, remotes):
        self.folders = []
        items_info = {0: {"name": ".", "icon": "", "path": G_LOCAL_FILES_ROOT},
                      1: {"name": "..", "icon": "", "path": ".."}}
        for idx, entry in enumerate(remotes):
            items_info[idx + 2] = {}
            items_info[idx + 2]["name"] = entry
            items_info[idx + 2]["icon"] = "folder-google-drive"
            items_info[idx + 2]["path"] = self.current_path + entry
            self.folders.append(entry)

        self.hass.states.set(
            "sensor.dyski", self.current_path, items_info)

    def display_current_remote_items(self):
        self.folders = []
        items_info = {0: {"name": ".", "icon": "", "path": G_LOCAL_FILES_ROOT},
                      1: {"name": "..", "icon": "", "path": ".."}}

        if self.current_path.endswith(':'):
            self.folders.append(self.current_path + ais_global.G_DRIVE_SHARED_WITH_ME)
            items_info[2] = {"name":  ais_global.G_DRIVE_SHARED_WITH_ME, "icon": "account-supervisor-circle",
                             "path": self.current_path + ais_global.G_DRIVE_SHARED_WITH_ME}
        li = len(items_info)
        for item in self.folders_json:
            li = li + 1
            if self.current_path.endswith(':'):
                path = self.current_path + item["Path"].strip()
            else:
                path = self.current_path + "/" + item["Path"].strip()

            items_info[li] = {}
            items_info[li]["name"] = item["Path"].strip()[:50]
            if item["IsDir"]:
                items_info[li]["icon"] = "folder-google-drive"
            else:
                items_info[li]["icon"] = "file-outline"
                if "MimeType" in item:
                    if item["MimeType"].startswith("text/"):
                        items_info[li]["icon"] = "file-document-outline"
                    elif item["MimeType"].startswith("audio/"):
                        items_info[li]["icon"] = "music-circle"
                    elif item["MimeType"].startswith("video/"):
                        items_info[li]["icon"] = "file-video-outline"
            items_info[li]["path"] = path
            self.folders.append(path)

        self.hass.states.set(
            "sensor.dyski", self.current_path, items_info)

    def get_icon(self, entry):
        if entry.is_dir():
            return "folder"
        elif entry.name.lower().endswith(".txt"):
            return "file-document-outline"
        elif entry.name.lower().endswith(('.mp3', '.wav', '.mp4', '.flv')):
            return "music-circle"

    def browse_path(self, call):
        """Load subfolders for the selected folder."""
        # test
        # say = False
        say = True
        if "say" in call.data:
            say = call.data["say"]
        if "path" not in call.data:
            _LOGGER.error("No path")
            return

        if call.data["path"] == "..":
            # check if this is cloud drive
            if self.is_rclone_path(self.current_path):
                if self.current_path == G_CLOUD_PREFIX:
                    self.current_path = G_LOCAL_FILES_ROOT
                elif self.current_path == G_CLOUD_PREFIX + self.rclone_remote_from_path(self.current_path):
                    self.current_path = G_CLOUD_PREFIX
                elif self.current_path.count("/") == 0:
                    k = self.current_path.rfind(":")
                    self.current_path = self.current_path[:k + 1]
                else:
                    k = self.current_path.rfind("/")
                    self.current_path = self.current_path[:k]
            # local drive
            else:
                if os.path.isfile(self.current_path):
                    k = self.current_path.rfind("/" + os.path.basename(self.current_path))
                    self.current_path = self.current_path[:k]
                k = self.current_path.rfind("/" + os.path.basename(self.current_path))
                self.current_path = self.current_path[:k]
        else:
            self.current_path = call.data["path"]

        if self.current_path.startswith(G_CLOUD_PREFIX):
            self.rclone_browse(self.current_path, say)
            return

        if self.current_path == G_LOCAL_FILES_ROOT:
            self.display_root_items(say)
            return

        if os.path.isdir(self.current_path):
            self.display_current_items(say)
        else:
            # file was selected, check mimetype and play if possible
            self.play_file()

    def is_rclone_path(self, path):
        if path.startswith(G_CLOUD_PREFIX):
            return True
        return False

    def rclone_remote_from_path(self, path):
        remote = path.replace(G_CLOUD_PREFIX, "")
        k = remote.find(":")
        remote = remote[:k + 1]
        return remote

    def rclone_fix_permissions(self):
        command = 'su -c "chmod -R 777 /sdcard/rclone"'
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        # process.wait()

    def rclone_append_listremotes(self, say):
        # self.rclone_fix_permissions()
        rclone_cmd = ["rclone", "listremotes", G_RCLONE_CONF]
        proc = subprocess.run(rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        #  will wait for the process to complete and then we are going to return the output
        if "" != proc.stderr:
            self.say("Nie można pobrać informacji o połączeniach do dysków: " + proc.stderr)
        else:
            remotes = []
            for l in proc.stdout.split("\n"):
                if len(l) > 0:
                    remotes.append(l.strip())

            self.display_current_remotes(remotes)

            if say:
                self.say("Masz " + str(len(remotes)) + " zdalnych dysków")
            else:
                self.beep()

    def rclone_browse_folder(self, path, silent):
        if ais_global.G_DRIVE_SHARED_WITH_ME in path:
            rclone_cmd = ["rclone", "lsjson",
                          path.replace(ais_global.G_DRIVE_SHARED_WITH_ME, ''),
                          G_RCLONE_CONF, '--drive-formats=txt', '--drive-shared-with-me']
        else:
            rclone_cmd = ["rclone", "lsjson", path, G_RCLONE_CONF, '--drive-formats=txt']
        proc = subprocess.run(rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        #  will wait for the process to complete and then we are going to return the output
        _LOGGER.error('G ' + path)
        if "" != proc.stderr:
            self.say("Nie można pobrać zawartości folderu " + path + " " + proc.stderr)
            _LOGGER.error('G E ' + path)
        else:
            _LOGGER.error('G OK ' + path)
            self.folders_json = json.loads(proc.stdout)
            self.display_current_remote_items()

            if silent is False:
                if self.text_to_say is not None:
                    self.say(self.text_to_say)
                else:
                    self.beep()

    def rclone_copy_and_read(self, path, item_path):
        # TODO clear .temp files...
        if ais_global.G_DRIVE_SHARED_WITH_ME in path:
            rclone_cmd = ["rclone", "copy", path.replace(ais_global.G_DRIVE_SHARED_WITH_ME, ''),
                          G_LOCAL_FILES_ROOT + '/.temp/', G_RCLONE_CONF,
                          '--drive-formats=txt', '--drive-shared-with-me']
        else:
            rclone_cmd = ["rclone", "copy", path, G_LOCAL_FILES_ROOT + '/.temp/',
                          G_RCLONE_CONF, '--drive-formats=txt']
        proc = subprocess.run(rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if "" != proc.stderr:
            self.say("Nie udało się pobrać pliku " + proc.stderr)
        else:
            try:
                with open(G_LOCAL_FILES_ROOT + '/.temp/' + item_path) as file:
                    self.say(file.read())
            except Exception as e:
                self.say("Nie udało się otworzyć pliku ")

    def rclone_play_the_stream(self):
        player_name = self.hass.states.get(
            'input_select.file_player').state
        player = ais_cloud.get_player_data(player_name)
        self.hass.services.call(
            'media_player',
            'play_media', {
                "entity_id": player["entity_id"],
                "media_content_type": "audio/mp4",
                "media_content_id": self.rclone_url_to_stream
            })
        _audio_info = {"NAME": os.path.basename(self.rclone_url_to_stream),
                       "MEDIA_SOURCE": ais_global.G_AN_LOCAL,
                       "ALBUM_NAME": os.path.basename(os.path.dirname(self.current_path))}
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
        position = ais_global.get_bookmark_position(self.rclone_url_to_stream)
        if position != 0:
            self.hass.services.call(
                'media_player',
                'media_seek', {
                    "entity_id": player["entity_id"],
                    "seek_position": position
                })

    def check_kill_process(self, pstring):
        for line in os.popen("ps ax | grep " + pstring + " | grep -v grep"):
            fields = line.split()
            pid = fields[0]
            os.kill(int(pid), signal.SIGKILL)

    def rclone_serve_and_play_the_stream(self, path, item_path):
        # try to kill previous serve if exists
        self.check_kill_process('rclone')
        # serve and play
        if ais_global.G_DRIVE_SHARED_WITH_ME in path:
            rclone_cmd = ["rclone", "serve", 'http',
                          path.replace(ais_global.G_DRIVE_SHARED_WITH_ME, ""), G_RCLONE_CONF, '--addr=:8080']
        else:
            rclone_cmd = ["rclone", "serve", 'http', path, G_RCLONE_CONF, '--addr=:8080']
        rclone_serving_process = subprocess.Popen(
            rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.rclone_url_to_stream = G_RCLONE_URL_TO_STREAM + str(item_path)
        import threading
        timer = threading.Timer(2, self.rclone_play_the_stream)
        timer.start()

    def rclone_browse(self, path, say):
        if path == G_CLOUD_PREFIX:
            self.rclone_append_listremotes(say)
            return
        if say:
            if path == G_CLOUD_PREFIX + self.rclone_remote_from_path(path):
                self.text_to_say = self.rclone_remote_from_path(path)
            else:
                k = path.find(":")
                self.text_to_say = os.path.basename(path[k:])
        else:
            self.text_to_say = None
        is_dir = None
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
        if is_dir is None:
            # check if this is file selected from bookmarks
            bookmark = ais_global.G_BOOKMARK_MEDIA_CONTENT_ID.replace(G_RCLONE_URL_TO_STREAM, "")
            if bookmark != "" and path.endswith(bookmark):
                is_dir = False
                mime_type = 'audio/'
                item_path = bookmark
                item_name = bookmark
                path = path.replace(G_CLOUD_PREFIX, "", 1)
                path = path.rsplit(bookmark, 1)[0]
                self.rclone_browse_folder(path, True)
            else:
                is_dir = True

        if is_dir:
            # browse the cloud drive
            path = path.replace(G_CLOUD_PREFIX, "", 1)
            self.rclone_browse_folder(path, False)

        else:
            self.dispalay_current_path()
            # file was selected, check the MimeType
            # "MimeType":"audio/mp3" and "text/plain" are supported
            path = path.replace(G_CLOUD_PREFIX, "")
            if mime_type is None:
                mime_type = ""
            if mime_type.startswith("audio/") or mime_type.startswith("video/"):
                # StreamTask().execute(fileItem);
                self.say("Pobieram i odtwarzam: " + str(item_name))
                self.rclone_serve_and_play_the_stream(path, item_path)
            elif mime_type.startswith("text/"):
                self.say("Pobieram i czytam: " + str(item_name))
                self.rclone_copy_and_read(path, item_path)
            else:
                self.say("Jeszcze nie obsługuję plików typu: " + str(mime_type))

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
            self.say("Synchronizuję lokalizację " + call.data["source_path"] + " z " + call.data["dest_path"]
                            + " modyfikuję tylko " + call.data["source_path"])

        rclone_cmd = ["rclone", "sync", call.data["source_path"], call.data["dest_path"],
                      "--transfers=1", "--stats=0", G_RCLONE_CONF]
        proc = subprocess.run(rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        #  will wait for the process to complete and then we are going to return the output
        if "" != proc.stderr:
            self.say("Błąd podczas synchronizacji: " + proc.stderr)
        else:
            self.say("Synchronizacja zakończona.")

    @asyncio.coroutine
    def async_load_all(self):
        """Load all the folders and files."""

        def load():
            self.display_root_items(say=False)

        yield from self.hass.async_add_job(load)
