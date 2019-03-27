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
from .config_flow import configured_drivers

REQUIREMENTS = ['pexpect==4.2', 'mutagen==1.42.0']

aisCloud = ais_cloud.AisCloudWS()

DOMAIN = 'ais_drives_service'
G_LOCAL_FILES_ROOT = '/data/data/pl.sviete.dom/files/home/dom'
G_CLOUD_PREFIX = 'dyski-zdalne:'
G_RCLONE_CONF_FILE = '/data/data/pl.sviete.dom/files/home/dom/rclone.conf'
G_RCLONE_CONF = '--config=' + G_RCLONE_CONF_FILE
G_RCLONE_URL_TO_STREAM = 'http://127.0.0.1:8080/'
G_LAST_BROWSE_CALL = None
G_DRIVE_CLIENT_ID = None
G_DRIVE_SECRET = None
G_COVER_FILE = "/data/data/pl.sviete.dom/files/home/AIS/www/cover.jpg"
G_RCLONE_REMOTES_LONG = []
_LOGGER = logging.getLogger(__name__)


TYPE_DRIVE = 'drive'
TYPE_MEGA = 'mega'
DRIVES_TYPES = {
    TYPE_DRIVE: ('Google Drive', 'mdi:google-drive'),
    TYPE_MEGA: ('Mega', 'mdi:cloud'),
}


def get_pozycji_variety(n):
    if n == 1:
        return str(n) + ' pozycja'
    elif n in (2, 3, 4) or (n > 20 and (str(n).endswith('2') or str(n).endswith('3') or str(n).endswith('4'))):
        return str(n) + ' pozycje'
    return str(n) + ' pozycji'


@asyncio.coroutine
def async_setup(hass, config):
    """Register the service."""
    _LOGGER.info("Initialize the folders and files list.")
    data = hass.data[DOMAIN] = LocalData(hass)
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

        if secs < 0.5:
            _LOGGER.info("This call is blocked, secs: " + str(secs))
            return
        data.browse_path(call)

    def refresh_files(call):
        _LOGGER.info("refresh_files")
        data.refresh_files(call)

    def sync_locations(call):
        _LOGGER.info("sync_locations")
        data.sync_locations(call)

    def play_next(call):
        _LOGGER.info("play_next")
        data.play_next(call)

    def play_prev(call):
        _LOGGER.info("play_prev")
        data.play_prev(call)

    def remote_next_item(call):
        _LOGGER.info("remote_next_item")
        data.remote_next_item(True)

    def remote_prev_item(call):
        _LOGGER.info("remote_prev_item")
        data.remote_prev_item(True)

    def remote_select_item(call):
        _LOGGER.info("remote_select_item")
        data.remote_select_item(True)

    def remote_cancel_item(call):
        _LOGGER.info("remote_cancel_item")
        data.remote_cancel_item(True)

    hass.services.async_register(
        DOMAIN, 'browse_path', browse_path)
    hass.services.async_register(
        DOMAIN, 'refresh_files', refresh_files)
    hass.services.async_register(
        DOMAIN, 'sync_locations', sync_locations)
    hass.services.async_register(
        DOMAIN, 'play_next', play_next)
    hass.services.async_register(
        DOMAIN, 'play_prev', play_prev)
    hass.services.async_register(
        DOMAIN, 'remote_next_item', remote_next_item)
    hass.services.async_register(
        DOMAIN, 'remote_prev_item', remote_prev_item)
    hass.services.async_register(
        DOMAIN, 'remote_select_item', remote_select_item)
    hass.services.async_register(
        DOMAIN, 'remote_cancel_item', remote_cancel_item)

    return True


async def async_setup_entry(hass, config_entry):
    """Set up drive as rclone config entry."""
    _LOGGER.info("Set up drive as rclone config entry")
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, 'sensor'))
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    time_now = time.time()
    if config_flow.G_DRIVE_CREATION_TIME_CALL is not None:
        secs = time_now - config_flow.G_DRIVE_CREATION_TIME_CALL
    else:
        secs = 10
    if secs > 5:
        _LOGGER.warning("Remove the drive token from rclone conf: " + str(secs))
        open(G_RCLONE_CONF_FILE, 'w').close()
    else:
        _LOGGER.info("Reloading entry: " + str(secs))

    await hass.config_entries.async_forward_entry_unload(config_entry, 'sensor')
    return True


def get_remotes_types_by_name(remote_name):
    # return all types
    names = []
    if remote_name is None:
        for obj in DRIVES_TYPES.values():
            names.append(obj[0])
        return names
    # return one type
    drive_type = ""
    for k, item in DRIVES_TYPES.items():
        if item[0] == remote_name:
            drive_type = k
    return drive_type


def rclone_get_remotes_long():
    global G_RCLONE_REMOTES_LONG
    G_RCLONE_REMOTES_LONG = []
    rclone_cmd = ["rclone", "listremotes", "--long", G_RCLONE_CONF]
    proc = subprocess.run(rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #  will wait for the process to complete and then we are going to return the output
    if "" != proc.stderr:
        _LOGGER.error("Nie można pobrać informacji o połączeniach do dysków: " + proc.stderr)
    else:
        for l in proc.stdout.split("\n"):
            if len(l) > 0:
                ri = l.split(':')
                G_RCLONE_REMOTES_LONG.append({"name": ri[0].strip(), "type": ri[1].strip()})
    return G_RCLONE_REMOTES_LONG


def rclone_get_auth_url(drive_name, drive_type):
    import pexpect
    # code, icon = DRIVES_TYPES[drive_type]
    rclone_cmd = "rclone config create " + drive_name + " " + drive_type\
                 + " " + G_RCLONE_CONF + " --drive-client-id=" + G_DRIVE_CLIENT_ID\
                 + " --drive-client-secret=" + G_DRIVE_SECRET + " config_is_local false"
    child = pexpect.spawn(rclone_cmd)
    child.expect('Enter verification code>', timeout=10)
    info = child.before
    child.kill(0)
    info = str(info, 'utf-8')
    _LOGGER.info(info)
    s = info.find('https://')
    url = info[s:]
    e = url.find('\r')
    url = url[:e]
    return url


def rclone_set_auth_gdrive(drive_name, code):
    try:
        import pexpect
        rclone_cmd = "rclone config " + G_RCLONE_CONF
        child = pexpect.spawn(rclone_cmd)
        # Current remotes:
        child.expect('/q>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('n')
        # name
        child.expect('name>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline(drive_name)
        # Storage
        child.expect('Storage>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('drive')
        # client_id
        child.expect('client_id>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline(G_DRIVE_CLIENT_ID)
        # client_secret>
        child.expect('client_secret>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline(G_DRIVE_SECRET)
        # scope>
        child.expect('scope>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline()
        # root_folder_id>
        child.expect('root_folder_id>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline()
        # service_account_file>
        child.expect('service_account_file>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline()
        # Edit advanced config? (y/n)
        child.expect('y/n>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('n')
        # Use auto config? n - Because Remote config
        child.expect('y/n>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('n')
        # 'Enter verification code>'
        child.expect('Enter verification code>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline(code)
        # Configure this as a team drive?
        child.expect('y/n>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('n')
        # Yes this is OK
        child.expect('y/e/d>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('y')
        # Quit config
        child.expect('e/n/d/r/c/s/q>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('q')
        child.kill(0)
        return 'ok'
    except Exception as e:
        return 'ERROR: ' + str(e)


def rclone_set_auth_mega(drive_name, user, passwd):
    try:
        import pexpect
        rclone_cmd = "rclone config " + G_RCLONE_CONF
        child = pexpect.spawn(rclone_cmd)
        # Current remotes:
        child.expect('/q>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('n')
        # name
        child.expect('name>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline(drive_name)
        # storage
        child.expect('Storage>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('mega')
        # user
        child.expect('user>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline(user)
        # yes type in my own password
        child.expect('y/g>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('y')
        # password
        child.expect('password:', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline(passwd)
        # confirm password
        child.expect('password:', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline(passwd)
        # Edit advanced config? (y/n)
        child.expect('y/n>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('n')
        # Yes this is OK
        child.expect('y/e/d>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('y')
        # Quit config
        child.expect('e/n/d/r/c/s/q>', timeout=10)
        _LOGGER.info(str(child.before, 'utf-8'))
        child.sendline('q')
        #
        child.kill(0)
        return 'ok'
    except Exception as e:
        return 'ERROR: ' + str(e)


def file_tags_extract(path):
    import mutagen.id3
    import mutagen.flac
    import mutagen.mp4
    global G_COVER_FILE
    dir_www = "/data/data/pl.sviete.dom/files/home/AIS/www/"
    dir_name = os.path.basename(os.path.dirname(path)).replace(' ', '')
    ret_path = '/local/' + dir_name + "_cover.jpg"
    f_length = 0
    # file info
    try:
        fi = mutagen.File(path)
        f_length = str(fi.info.length)
    except Exception as e:
        _LOGGER.error("Error " + str(e))

    if G_COVER_FILE == dir_www + dir_name + "_cover.jpg":
        return ret_path, f_length
    # remove all .jpg
    jpgs = os.listdir(dir_www)
    for jpg in jpgs:
        if jpg.endswith("_cover.jpg"):
            os.remove(os.path.join(dir_www, jpg))

    # generate the cover
    G_COVER_FILE = dir_www + dir_name + "_cover.jpg"
    try:
        id3 = mutagen.id3.ID3(path)
        open(G_COVER_FILE, 'wb').write(id3.getall('APIC')[0].data)
    except mutagen.id3.ID3NoHeaderError:
        try:
            flac = mutagen.flac.FLAC(path)
            open(G_COVER_FILE, 'wb').write(flac.pictures[0].data)
        except mutagen.flac.FLACNoHeaderError:
            try:
                mp4 = mutagen.mp4.MP4(path)
                open(G_COVER_FILE, 'wb').write(mp4['covr'][0])
            except Exception as e:
                _LOGGER.error("Error " + str(e))

    return ret_path, f_length


class LocalData:
    """Class to hold local folders and files data."""

    def __init__(self, hass):
        """Initialize the books authors."""
        self.hass = hass
        self.selected_item_idx = 0
        self.folders_json = []
        self.current_path = os.path.abspath(G_LOCAL_FILES_ROOT)
        self.rclone_url_to_stream = None
        self.rclone_pexpect_stream = None

    def beep(self):
        self.hass.services.call('ais_ai_service', 'publish_command_to_frame', {"key": 'tone', "val": 97})

    def say(self, text):
        self.hass.services.call('ais_ai_service', 'say_it', {"text": text})

    def refresh_files(self, call):
        pass

    def play_file(self, say):
        mime_type = mimetypes.MimeTypes().guess_type(self.current_path)[0]
        if mime_type is None:
            mime_type = ""
        if mime_type.startswith('text/'):
            self.say("Czytam: ")
            with open(self.current_path) as file:
                self.say(file.read())
        elif mime_type.startswith('audio/'):
            _url = self.current_path
            # TODO search the album and title ...
            album_cover_path, file_length = file_tags_extract(self.current_path)
            _audio_info = {"NAME": os.path.basename(self.current_path),
                           "MEDIA_SOURCE": ais_global.G_AN_LOCAL,
                           "ALBUM_NAME": os.path.basename(os.path.dirname(self.current_path)),
                           "IMAGE_URL": album_cover_path,
                           "DURATION": file_length}
            _audio_info = json.dumps(_audio_info)

            if _url is not None:
                self.hass.services.call(
                    'media_player',
                    'play_media', {
                        "entity_id": "media_player.wbudowany_glosnik",
                        "media_content_type": "audio/mp4",
                        "media_content_id": _url
                    })
                # set stream image and title
                self.hass.services.call(
                    'media_player',
                    'play_media', {
                        "entity_id": "media_player.wbudowany_glosnik",
                        "media_content_type": "ais_info",
                        "media_content_id": _audio_info
                    })
                # skipTo
                position = ais_global.get_bookmark_position(_url)
                if position != 0:
                    self.hass.services.call(
                        'media_player',
                        'media_seek', {
                            "entity_id": "media_player.wbudowany_glosnik",
                            "seek_position": position
                        })
        else:
            _LOGGER.info("Tego typu plików jeszcze nie obsługuję." + str(self.current_path))
            self.say("Tego typu plików jeszcze nie obsługuję.")

        self.dispalay_current_path()

    def display_root_items(self, say):
        self.hass.states.set(
            "sensor.ais_drives", '', {
                'files': [
                    {"name": "Dysk wewnętrzny", "icon": "harddisk",
                     "path": G_LOCAL_FILES_ROOT + "/dysk-wewnętrzny"},
                    {"name": "Dyski zewnętrzne", "icon": "sd",
                     "path": G_LOCAL_FILES_ROOT + "/dyski-zewnętrzne"},
                    {"name": "Dyski zdalne", "icon": "onedrive",
                     "path": G_CLOUD_PREFIX}]
            })
        if say:
            self.say("Dysk wewnętrzny")

    def dispalay_current_path(self):
        state = self.hass.states.get('sensor.ais_drives')
        items_info = state.attributes
        self.hass.states.set("sensor.ais_drives", self.current_path.replace(G_LOCAL_FILES_ROOT, ''), items_info)

    def display_current_items(self, say):
        local_items = []
        try:
            local_items = os.scandir(self.current_path)
        except Exception as e:
            _LOGGER.error("list_dir error: " + str(e))
        si = sorted(local_items, key=lambda en: en.name)
        items_info = [{"name": ".", "icon": "", "path": G_LOCAL_FILES_ROOT},
                      {"name": "..", "icon": "", "path": ".."}]
        for i in si:
            items_info.append({"name": i.name, "icon": self.get_icon(i), "path": i.path})
        self.hass.states.set("sensor.ais_drives", self.current_path.replace(G_LOCAL_FILES_ROOT, ''), {'files': items_info})
        if say:
            slen = len(si)
            self.say(get_pozycji_variety(slen))

    def display_current_remotes(self, remotes):
        items_info = [{"name": ".", "icon": "", "path": G_LOCAL_FILES_ROOT},
                      {"name": "..", "icon": "", "path": ".."}]
        for i in remotes:
            if i["type"] == 'drive':
                icon = "folder-google-drive"
            else:
                icon = "onedrive"
            items_info.append({"name": i["name"], "icon": icon, "path": self.current_path + i["name"] + ':'})
        self.hass.states.set("sensor.ais_drives", self.current_path, {'files': items_info})

    def display_current_remote_items(self, say):
        items_info = [{"name": ".", "icon": "", "path": G_LOCAL_FILES_ROOT},
                      {"name": "..", "icon": "", "path": ".."}]

        if self.current_path.endswith(':'):
            for remote in G_RCLONE_REMOTES_LONG:
                if 'dyski-zdalne:' + remote["name"] + ':' == self.current_path:
                    if remote["type"] == 'drive':
                        items_info.append({"name":  ais_global.G_DRIVE_SHARED_WITH_ME,
                                           "icon": "account-supervisor-circle",
                                           "path": self.current_path + ais_global.G_DRIVE_SHARED_WITH_ME})
                        break
        for item in self.folders_json:
            if self.current_path.endswith(':'):
                path = self.current_path + item["Path"]
            else:
                path = self.current_path + "/" + item["Path"]

            l_icon = "file-outline"
            if item["IsDir"]:
                l_icon = "folder-google-drive"
            else:
                if "MimeType" in item:
                    if item["MimeType"].startswith("text/"):
                        l_icon = "file-document-outline"
                    elif item["MimeType"].startswith("audio/"):
                        l_icon = "music-circle"
                    elif item["MimeType"].startswith("video/"):
                        l_icon = "file-video-outline"
            items_info.append({"name": item["Path"][:50], "icon": l_icon, "path": path})
        self.hass.states.set("sensor.ais_drives", self.current_path, {'files': items_info})
        if say:
            jlen = len(self.folders_json)
            self.say(get_pozycji_variety(jlen))

    def get_icon(self, entry):
        if entry.is_dir():
            return "folder"
        elif entry.name.lower().endswith(".txt"):
            return "file-document-outline"
        elif entry.name.lower().endswith(('.mp3', '.wav', '.mp4', '.flv')):
            return "music-circle"

    def browse_path(self, call):
        """Load subfolders for the selected folder."""
        if "path" not in call.data:
            _LOGGER.error("No path")
            return
        self._browse_path(call.data["path"], True)

    def _browse_path(self, path, say):
        if path == "..":
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
                    if self.rclone_is_dir(self.current_path):
                        k = self.current_path.rfind("/")
                        self.current_path = self.current_path[:k]
                    else:
                        k = self.current_path.rfind("/")
                        self.current_path = self.current_path[:k]
                        if self.current_path.count("/") > 0:
                            k = self.current_path.rfind("/")
                            self.current_path = self.current_path[:k]
                        else:
                            k = self.current_path.rfind(":")
                            self.current_path = self.current_path[:k+1]

            # local drive
            else:
                if os.path.isfile(self.current_path):
                    k = self.current_path.rfind("/" + os.path.basename(self.current_path))
                    self.current_path = self.current_path[:k]
                k = self.current_path.rfind("/" + os.path.basename(self.current_path))
                self.current_path = self.current_path[:k]
        else:
            self.current_path = path

        if self.current_path.startswith(G_CLOUD_PREFIX):
            self.rclone_browse(self.current_path, say)
            self.selected_item_idx = 0
            return

        if self.current_path == G_LOCAL_FILES_ROOT:
            self.display_root_items(say)
            self.selected_item_idx = 0
            return

        if os.path.isdir(self.current_path):
            self.display_current_items(say)
            self.selected_item_idx = 0
            return
        else:
            # file was selected, check mimetype and play if possible
            self.play_file(say)

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

    def rclone_append_listremotes(self):
        remotes = rclone_get_remotes_long()
        self.display_current_remotes(remotes)
        self.say(get_pozycji_variety(len(remotes)))

    def rclone_browse_folder(self, path, say):
        if ais_global.G_DRIVE_SHARED_WITH_ME in path:
            if ais_global.G_DRIVE_SHARED_WITH_ME + '/' in path:
                path = path.replace(ais_global.G_DRIVE_SHARED_WITH_ME + '/', '')
            else:
                path = path.replace(ais_global.G_DRIVE_SHARED_WITH_ME, '')
            rclone_cmd = ["rclone", "lsjson", path,
                          G_RCLONE_CONF, '--drive-formats=txt', '--drive-shared-with-me']
        else:
            rclone_cmd = ["rclone", "lsjson", path, G_RCLONE_CONF, '--drive-formats=txt']
        proc = subprocess.run(rclone_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        #  will wait for the process to complete and then we are going to return the output
        if "" != proc.stderr:
            self.say("Nie można pobrać zawartości folderu " + path + " " + proc.stderr)
        else:
            self.folders_json = json.loads(proc.stdout)
            self.display_current_remote_items(say)

    def rclone_copy_and_read(self, path, item_path):
        # clear .temp files
        files = os.listdir(G_LOCAL_FILES_ROOT + '/.temp/')
        for file in files:
            os.remove(os.path.join(G_LOCAL_FILES_ROOT + '/.temp/', file))

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
        self.hass.services.call(
            'media_player',
            'play_media', {
                "entity_id": "media_player.wbudowany_glosnik",
                "media_content_type": "audio/mp4",
                "media_content_id": self.rclone_url_to_stream
            })
        _audio_info = {"NAME": os.path.basename(self.rclone_url_to_stream),
                       "MEDIA_SOURCE": ais_global.G_AN_LOCAL,
                       "ALBUM_NAME": os.path.basename(os.path.dirname(self.current_path))}
        _audio_info = json.dumps(_audio_info)
        # to set the stream image and title
        self.hass.services.call(
            'media_player',
            'play_media', {
                "entity_id": "media_player.wbudowany_glosnik",
                "media_content_type": "ais_info",
                "media_content_id": _audio_info
            })
        position = ais_global.get_bookmark_position(self.rclone_url_to_stream)
        if position != 0:
            self.hass.services.call(
                'media_player',
                'media_seek', {
                    "entity_id": "media_player.wbudowany_glosnik",
                    "seek_position": position
                })

    def check_kill_process(self, pstring):
        for line in os.popen("ps ax | grep " + pstring + " | grep -v grep"):
            fields = line.split()
            pid = fields[0]
            os.kill(int(pid), signal.SIGKILL)

    def rclone_serve_and_play_the_stream(self, path, item_path):
        # serve and play
        if ais_global.G_DRIVE_SHARED_WITH_ME in path:
            path = path.replace(ais_global.G_DRIVE_SHARED_WITH_ME, "")
        rclone_cmd = "rclone serve http '" + path + "' " + G_RCLONE_CONF + " --addr=:8080"

        self.rclone_url_to_stream = G_RCLONE_URL_TO_STREAM + str(item_path)
        import pexpect
        try:
            if self.rclone_pexpect_stream is not None:
                self.rclone_pexpect_stream.kill(0)
                self.check_kill_process('rclone')
            self.rclone_pexpect_stream = pexpect.spawn(rclone_cmd)
            # Current remotes:
            self.rclone_pexpect_stream.expect(['Serving on', 'Failed to', pexpect.EOF], timeout=10)
            _LOGGER.info(str(self.rclone_pexpect_stream.before, 'utf-8'))
            if self.rclone_pexpect_stream == 0:
                _LOGGER.info('Serving stream')
            elif self.rclone_pexpect_stream == 1:
                _LOGGER.info('Problem, kill rclone')
                self.rclone_pexpect_stream.kill(0)
                self.check_kill_process('rclone')
            elif self.rclone_pexpect_stream == 2:
                _LOGGER.info('EOF')
            self.rclone_play_the_stream()
        except Exception as e:
            _LOGGER.info('Rclone: ' + str(e))

    def rclone_is_dir(self, path):
        # check if path is dir or file
        for item in self.folders_json:
            if path.endswith(item["Path"]):
                return item["IsDir"]
        return True

    def rclone_browse(self, path, say):
        if path == G_CLOUD_PREFIX:
            self.rclone_append_listremotes()
            return
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
                break
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
                self.rclone_browse_folder(path, say)
            else:
                is_dir = True
        if is_dir:
            # browse the cloud drive
            path = path.replace(G_CLOUD_PREFIX, "", 1)
            self.say("Pobieram")
            self.rclone_browse_folder(path, say)
        else:
            self.dispalay_current_path()
            # file was selected, check the MimeType
            # "MimeType":"audio/mp3" and "text/plain" are supported
            path = path.replace(G_CLOUD_PREFIX, "")
            if mime_type is None:
                mime_type = ""
            if mime_type.startswith("audio/") or mime_type.startswith("video/") or mime_type.startswith("application/"):
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

    def play_next(self, call):
        state = self.hass.states.get('sensor.ais_drives')
        attr = state.attributes
        files = attr.get('files', [])
        l_idx = 0
        i = 0
        for f in files:
            i = i + 1
            if f["path"].replace(G_LOCAL_FILES_ROOT, "") == state.state:
                l_idx = i
        if l_idx == len(files):
            l_idx = min(2, len(files))
        self._browse_path(files[l_idx]["path"], True)

    def play_prev(self, call):
        state = self.hass.states.get('sensor.ais_drives')
        attr = state.attributes
        files = attr.get('files', [])
        l_idx = 0
        i = 0
        for f in files:
            i = i + 1
            if f["path"].replace(G_LOCAL_FILES_ROOT, "") == state.state:
                l_idx = i
        if l_idx == 3:
            l_idx = len(files) - 1
        else:
            l_idx = l_idx - 2
        self._browse_path(files[l_idx]["path"], True)

    def get_item_name(self, path):
        path = path.rstrip(':')
        if path.count('/') > 0:
            name = path.split('/').pop()
        else:
            name = path.split(':').pop()
        name = name.replace(':', '')
        name = name.replace('-', ' ')
        return name

    def remote_next_item(self, say):
        state = self.hass.states.get('sensor.ais_drives')
        attr = state.attributes
        files = attr.get('files', [])
        if len(state.state) == 0:
            if self.selected_item_idx == len(files) - 1:
                self.selected_item_idx = 0
            else:
                self.selected_item_idx = self.selected_item_idx + 1
        else:
            if len(files) == 2:
                self.say("brak pozycji")
                return

            if self.selected_item_idx == len(files) - 1:
                self.selected_item_idx = 2
            else:
                self.selected_item_idx = max(self.selected_item_idx + 1, 2)

        if say:
            name = self.get_item_name(files[self.selected_item_idx]["path"])
            self.say(name)

    def remote_prev_item(self, say):
        state = self.hass.states.get('sensor.ais_drives')
        attr = state.attributes
        files = attr.get('files', [])
        if len(state.state) == 0:
            if self.selected_item_idx < 1:
                self.selected_item_idx = len(files) - 1
            else:
                self.selected_item_idx = self.selected_item_idx - 1
        else:
            if len(files) == 2:
                self.say("brak pozycji")
                return

            if self.selected_item_idx < 3:
                self.selected_item_idx = len(files) - 1
            else:
                self.selected_item_idx = self.selected_item_idx - 1
        if say:
            name = self.get_item_name(files[self.selected_item_idx]["path"])
            self.say(name)

    def remote_select_item(self, say):
        state = self.hass.states.get('sensor.ais_drives')
        attr = state.attributes
        files = attr.get('files', [])
        if state.state is None or self.selected_item_idx is None:
            self.selected_item_idx = 0
        self._browse_path(files[self.selected_item_idx]["path"], say)

    def remote_cancel_item(self, say):
        self._browse_path('..', say)

    @asyncio.coroutine
    def async_load_all(self):
        """Load all the folders and files."""
        def load():
            self.display_root_items(False)
            global G_DRIVE_SECRET, G_DRIVE_CLIENT_ID
            try:
                ws_resp = aisCloud.key("gdrive_client_id")
                json_ws_resp = ws_resp.json()
                G_DRIVE_CLIENT_ID = json_ws_resp["key"]
                ws_resp = aisCloud.key("gdrive_secret")
                json_ws_resp = ws_resp.json()
                G_DRIVE_SECRET = json_ws_resp["key"]
            except Exception as e:
                _LOGGER.error("Error " + str(e))
                ais_global.G_OFFLINE_MODE = True

        yield from self.hass.async_add_job(load)
