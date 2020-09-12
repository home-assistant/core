"""
Support for AIS local audio

For more details about this component, please refer to the documentation at
https://www.ai-speaker.com
"""
import json
import logging
import mimetypes
import os
import platform
import subprocess
import time

from homeassistant.components.ais_dom import ais_global

from .config_flow import configured_drivers

DOMAIN = "ais_drives_service"
G_LOCAL_FILES_ROOT = "/data/data/pl.sviete.dom/files/home/dom"
G_CLOUD_FILES_ROOT = G_LOCAL_FILES_ROOT + "/dyski-zdalne"

# run the rclone gui
# rclone rcd --rc-web-gui --rc-user=admin --rc-pass=pass --rc-addr :5572 --config dom/rclone.conf
G_RCLONE_OLD_CONF_FILE = "/data/data/pl.sviete.dom/files/home/dom/rclone.conf"
G_RCLONE_CONF_FILE = "/data/data/pl.sviete.dom/files/home/AIS/.dom/rclone.conf"
G_RCLONE_CONF = "--config=" + G_RCLONE_CONF_FILE
G_RCLONE_URL_TO_STREAM = "http://127.0.0.1:8080/"
G_DRIVE_CLIENT_ID = None
G_DRIVE_SECRET = None
G_COVER_FILE = "/data/data/pl.sviete.dom/files/home/AIS/www/cover.jpg"
G_RCLONE_REMOTES_LONG = []
_LOGGER = logging.getLogger(__name__)


TYPE_DRIVE = "drive"
TYPE_MEGA = "mega"
TYPE_FTP = "ftp"
DRIVES_TYPES = {
    TYPE_DRIVE: ("Google Drive", "mdi:google-drive"),
    TYPE_MEGA: ("Mega", "mdi:cloud"),
    TYPE_FTP: ("FTP", "mdi:nas"),
}


def get_pozycji_variety(n):
    if n == 1:
        return str(n) + " pozycja"
    elif n in (2, 3, 4) or (
        n > 20
        and (str(n).endswith("2") or str(n).endswith("3") or str(n).endswith("4"))
    ):
        return str(n) + " pozycje"
    return str(n) + " pozycji"


async def async_setup(hass, config):
    """Register the service."""
    _LOGGER.info("Initialize the folders and files list.")
    data = hass.data[DOMAIN] = LocalData(hass)
    await data.async_load_all(hass)

    # register services
    def browse_path(call):
        _LOGGER.debug("browse_path")
        data.browse_path(call)

    def sync_locations(call):
        _LOGGER.debug("sync_locations")
        data.sync_locations(call)

    def play_next(call):
        _LOGGER.debug("play_next")
        data.play_next(call)

    def play_prev(call):
        _LOGGER.debug("play_prev")
        data.play_prev(call)

    def remote_next_item(call):
        _LOGGER.debug("remote_next_item")
        data.remote_next_item(True)

    def remote_prev_item(call):
        _LOGGER.debug("remote_prev_item")
        data.remote_prev_item(True)

    def remote_select_item(call):
        _LOGGER.debug("remote_select_item")
        data.remote_select_item(True)

    def remote_cancel_item(call):
        _LOGGER.debug("remote_cancel_item")
        data.remote_cancel_item(True)

    def remote_delete_item(call):
        _LOGGER.debug("remote_delete_item")
        data.remote_delete_item(True)

    def rclone_mount_drive(call):
        _LOGGER.debug("rclone_mount_drive")
        if "name" in call.data:
            data.rclone_mount_drive(call.data["name"])

    def rclone_remove_drive(call):
        _LOGGER.debug("rclone_remove_drive")
        if "name" in call.data:
            data.rclone_remove_drive(call.data["name"])

    def rclone_mount_drives(call):
        data.rclone_mount_drives()

    hass.services.async_register(DOMAIN, "rclone_mount_drives", rclone_mount_drives)
    hass.services.async_register(DOMAIN, "rclone_mount_drive", rclone_mount_drive)
    hass.services.async_register(DOMAIN, "rclone_remove_drive", rclone_remove_drive)
    hass.services.async_register(DOMAIN, "browse_path", browse_path)
    hass.services.async_register(DOMAIN, "sync_locations", sync_locations)
    hass.services.async_register(DOMAIN, "play_next", play_next)
    hass.services.async_register(DOMAIN, "play_prev", play_prev)
    hass.services.async_register(DOMAIN, "remote_next_item", remote_next_item)
    hass.services.async_register(DOMAIN, "remote_prev_item", remote_prev_item)
    hass.services.async_register(DOMAIN, "remote_select_item", remote_select_item)
    hass.services.async_register(DOMAIN, "remote_cancel_item", remote_cancel_item)
    hass.services.async_register(DOMAIN, "remote_delete_item", remote_delete_item)

    return True


async def async_setup_entry(hass, config_entry):
    """Set up drive as rclone config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    if ais_global.G_AIS_START_IS_DONE:
        hass.async_create_task(hass.services.async_call(DOMAIN, "rclone_mount_drives"))
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
        open(G_RCLONE_CONF_FILE, "w").close()
    else:
        _LOGGER.info("Reloading entry: " + str(secs))

    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
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


def fix_rclone_config_permissions():
    # fix permissions
    uid = str(os.getuid())
    gid = str(os.getgid())

    if ais_global.has_root():
        fix_rclone_cmd = (
            'su -c "chown ' + uid + ":" + gid + " " + G_RCLONE_CONF_FILE + '"'
        )
        try:
            subprocess.check_output(fix_rclone_cmd, shell=True)  # nosec
        except Exception as e:
            _LOGGER.error(
                "Nie można uzyskać uprwanień do konfiguracji dysków: " + str(e)
            )


def rclone_get_remotes_long():
    global G_RCLONE_REMOTES_LONG
    G_RCLONE_REMOTES_LONG = []

    #
    fix_rclone_config_permissions()
    #
    rclone_cmd = ["rclone", "listremotes", "--long", G_RCLONE_CONF]
    proc = subprocess.run(
        rclone_cmd, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    #  will wait for the process to complete and then we are going to return the output
    if "" != proc.stderr:
        _LOGGER.error(
            "Nie można pobrać informacji o połączeniach do dysków: " + proc.stderr
        )
    else:
        for l in proc.stdout.split("\n"):
            if len(l) > 0:
                ri = l.split(":")
                G_RCLONE_REMOTES_LONG.append(
                    {"name": ri[0].strip(), "type": ri[1].strip()}
                )
    return G_RCLONE_REMOTES_LONG


def rclone_get_auth_url(drive_name, drive_type):
    import pexpect

    #
    fix_rclone_config_permissions()

    rclone_cmd = (
        "rclone config create "
        + drive_name
        + " "
        + drive_type
        + " "
        + G_RCLONE_CONF
        + " --drive-client-id="
        + G_DRIVE_CLIENT_ID
        + " --drive-client-secret="
        + G_DRIVE_SECRET
        + " config_is_local false"
    )
    child = pexpect.spawn(rclone_cmd)
    child.expect("Enter verification code>", timeout=10)
    info = child.before
    child.kill(0)
    info = str(info, "utf-8")
    _LOGGER.info(info)
    s = info.find("https://")
    url = info[s:]
    e = url.find("\r")
    url = url[:e]
    return url


def rclone_set_auth_gdrive(drive_name, code):
    try:
        import pexpect

        #
        fix_rclone_config_permissions()
        #
        rclone_cmd = "rclone config " + G_RCLONE_CONF
        child = pexpect.spawn(rclone_cmd)
        # Current remotes:
        child.expect("/q>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("n")
        # name
        child.expect("name>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(drive_name)
        # Storage
        child.expect("Storage>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("drive")
        # client_id
        child.expect("client_id>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(G_DRIVE_CLIENT_ID)
        # client_secret>
        child.expect("client_secret>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(G_DRIVE_SECRET)
        # scope>
        child.expect("scope>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline()
        # root_folder_id>
        child.expect("root_folder_id>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline()
        # service_account_file>
        child.expect("service_account_file>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline()
        # Edit advanced config? (y/n)
        child.expect("y/n>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("n")
        # Use auto config? n - Because Remote config
        child.expect("y/n>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("n")
        # 'Enter verification code>'
        child.expect("Enter verification code>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(code)
        # Configure this as a team drive?
        child.expect("y/n>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("n")
        # Yes this is OK
        child.expect("y/e/d>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("y")
        # Quit config
        child.expect("e/n/d/r/c/s/q>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("q")
        child.kill(0)
        return "ok"
    except Exception as e:
        return "ERROR: " + str(e)


def rclone_set_auth_mega(drive_name, user, passwd):
    try:
        import pexpect

        #
        fix_rclone_config_permissions()
        #
        rclone_cmd = "rclone config " + G_RCLONE_CONF
        child = pexpect.spawn(rclone_cmd)
        # Current remotes:
        child.expect("/q>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("n")
        # name
        child.expect("name>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(drive_name)
        # storage
        child.expect("Storage>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("mega")
        # user
        child.expect("user>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(user)
        # yes type in my own password
        child.expect("y/g>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("y")
        # password
        child.expect("password:", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(passwd)
        # confirm password
        child.expect("password:", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(passwd)
        # Edit advanced config? (y/n)
        child.expect("y/n>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("n")
        # Yes this is OK
        child.expect("y/e/d>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("y")
        # Quit config
        child.expect("e/n/d/r/c/s/q>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("q")
        #
        child.kill(0)
        return "ok"
    except Exception as e:
        return "ERROR: " + str(e)


def rclone_set_auth_ftp(drive_name, host, port, user_name, password):
    try:
        import pexpect

        #
        fix_rclone_config_permissions()
        #
        if len(password) == 0:
            password = "guest"
        rclone_cmd = "rclone config " + G_RCLONE_CONF
        child = pexpect.spawn(rclone_cmd)
        # Current remotes:
        child.expect("/q>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("n")
        # name
        child.expect("name>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(drive_name)
        # storage
        child.expect("Storage>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("ftp")
        # host
        child.expect("host>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(host)
        # anonymous or username
        child.expect("user>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(user_name)
        # port
        child.expect("port>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(str(port))
        # Yes type in my own password
        child.expect("y/g>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("y")
        # password
        child.expect("password:", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(password)
        # confirm password
        child.expect("password:", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline(password)
        # tls
        child.expect("tls>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("false")
        # Edit advanced config? (y/n)
        child.expect("y/n>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("n")
        # Yes this is OK
        child.expect("y/e/d>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("y")
        # Quit config
        child.expect("e/n/d/r/c/s/q>", timeout=10)
        _LOGGER.info(str(child.before, "utf-8"))
        child.sendline("q")
        #
        child.kill(0)
        return "ok"
    except Exception as e:
        return "ERROR: " + str(e)


def file_tags_extract(path):
    import mutagen.flac
    import mutagen.id3
    import mutagen.mp4

    global G_COVER_FILE
    dir_www = "/data/data/pl.sviete.dom/files/home/AIS/www/"
    dir_name = os.path.basename(os.path.dirname(path)).replace(" ", "")
    ret_path = "/local/" + dir_name + "_cover.jpg"
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
        open(G_COVER_FILE, "wb").write(id3.getall("APIC")[0].data)
    except Exception:
        try:
            flac = mutagen.flac.FLAC(path)
            open(G_COVER_FILE, "wb").write(flac.pictures[0].data)
        except Exception:
            try:
                mp4 = mutagen.mp4.MP4(path)
                open(G_COVER_FILE, "wb").write(mp4["covr"][0])
            except Exception as e:
                _LOGGER.info("Error " + str(e))

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
        self.file_path = None
        self.seek_position = 0

    def beep(self):
        self.hass.services.call(
            "ais_ai_service", "publish_command_to_frame", {"key": "tone", "val": 97}
        )

    def say(self, text):
        self.hass.services.call("ais_ai_service", "say_it", {"text": text})

    def play_file(self, say):
        mime_type = mimetypes.MimeTypes().guess_type(self.current_path)[0]
        if mime_type is None:
            mime_type = ""
        if mime_type.startswith("text/"):
            self.say("Czytam: ")
            with open(self.current_path) as file:
                self.say(file.read())
        elif mime_type.startswith("audio/") or mime_type.startswith("video/"):
            _url = self.current_path
            if _url.startswith("/data/data/pl.sviete.dom/files/home/dom/dyski-zdalne/"):
                self.say("Pobieram i odtwarzam")
            # TODO search the album and title ...
            album_cover_path, file_length = file_tags_extract(self.current_path)
            _audio_info = {
                "NAME": os.path.basename(self.current_path),
                "MEDIA_SOURCE": ais_global.G_AN_LOCAL,
                "ALBUM_NAME": os.path.basename(os.path.dirname(self.current_path)),
                "IMAGE_URL": album_cover_path,
                "DURATION": file_length,
                "media_content_id": _url,
                "lookup_url": self.current_path,
                "media_position_ms": self.seek_position,
            }
            _audio_info = json.dumps(_audio_info)

            if _url is not None:
                # set url stream image and title
                self.hass.services.call(
                    "media_player",
                    "play_media",
                    {
                        "entity_id": "media_player.wbudowany_glosnik",
                        "media_content_type": "ais_content_info",
                        "media_content_id": _audio_info,
                    },
                )
                # seek position
                self.seek_position = 0
        else:
            _LOGGER.info(
                mime_type
                + "Tego typu plików jeszcze nie obsługuję."
                + str(self.current_path)
            )
            self.say("Tego typu plików jeszcze nie obsługuję.")

        self.dispalay_current_path()

    def display_root_items(self, say):
        self.hass.states.async_set(
            "sensor.ais_drives",
            "",
            {
                "files": [
                    {
                        "name": "Dysk wewnętrzny",
                        "icon": "harddisk",
                        "path": G_LOCAL_FILES_ROOT + "/dysk-wewnętrzny",
                    },
                    {
                        "name": "Dyski wymienne",
                        "icon": "usb-flash-drive-outline",
                        "path": G_LOCAL_FILES_ROOT + "/dyski-wymienne",
                    },
                    {
                        "name": "Dyski zdalne",
                        "icon": "server-network",
                        "path": G_LOCAL_FILES_ROOT + "/dyski-zdalne",
                    },
                ]
            },
        )
        if say:
            self.say("Wszystkie Dyski")

    def dispalay_current_path(self):
        state = self.hass.states.get("sensor.ais_drives")
        items_info = state.attributes
        self.hass.states.set(
            "sensor.ais_drives",
            self.current_path.replace(G_LOCAL_FILES_ROOT, ""),
            items_info,
        )

    # browse files on local folder
    def display_current_items(self, say):
        local_items = []
        try:
            local_items = os.scandir(self.current_path)
        except Exception as e:
            _LOGGER.error("list_dir error: " + str(e))
        si = sorted(local_items, key=lambda en: en.name)
        items_info = [
            {"name": ".", "icon": "", "path": G_LOCAL_FILES_ROOT},
            {"name": "..", "icon": "", "path": ".."},
        ]
        for i in si:
            items_info.append(
                {"name": i.name, "icon": self.get_icon(i), "path": i.path}
            )
        self.hass.states.set(
            "sensor.ais_drives",
            self.current_path.replace(G_LOCAL_FILES_ROOT, ""),
            {"files": items_info},
        )
        if say:
            slen = len(si)
            self.say(get_pozycji_variety(slen))

        # call from bookmarks now (since we have files from folder) we need to play the file
        if self.file_path is not None:
            self.hass.services.call(
                "ais_drives_service",
                "browse_path",
                {"path": self.file_path, "seek_position": self.seek_position},
            )

    def get_icon(self, entry):
        if entry.is_dir():
            return "folder"
        elif entry.name.lower().endswith(".txt"):
            return "file-document-outline"
        elif entry.name.lower().endswith((".mp3", ".wav", ".mp4", ".flv")):
            return "music-circle"

    def browse_path(self, call):
        """Load subfolders for the selected folder."""
        if "path" not in call.data:
            _LOGGER.error("No path")
            return
        self.file_path = None
        self.seek_position = 0
        say = True
        if "say" in call.data:
            say = call.data["say"]
        if "file_path" in call.data:
            self.file_path = call.data["file_path"]
            say = False
        if "seek_position" in call.data:
            self.seek_position = call.data["seek_position"]
            say = False
        self._browse_path(call.data["path"], say)

    def _browse_path(self, path, say):
        if len(path.strip()) == 0:
            self.say("Wybierz pozycję do przeglądania")
        if path == "..":
            # up on drive
            if os.path.isfile(self.current_path):
                k = self.current_path.rfind("/" + os.path.basename(self.current_path))
                self.current_path = self.current_path[:k]
            k = self.current_path.rfind("/" + os.path.basename(self.current_path))
            self.current_path = self.current_path[:k]

        else:
            self.current_path = path

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

    # mount drives
    def rclone_mount_drives(self):
        remotes = rclone_get_remotes_long()
        for r in remotes:
            self.hass.services.call(
                "ais_drives_service", "rclone_mount_drive", {"name": r["name"]}
            )
        self.hass.services.call(
            "ais_drives_service",
            "browse_path",
            {"path": G_LOCAL_FILES_ROOT, "say": False},
        )

    def rclone_mount_drive(self, name):
        remotes = rclone_get_remotes_long()
        # get uid and gid
        uid = str(os.getuid())
        gid = str(os.getgid())
        drive_exist = False
        for r in remotes:
            if name == r["name"]:
                drive_exist = True

        if drive_exist:
            if not ais_global.has_root():
                # to suport local test
                rclone_cmd_mount = (
                    "rclone mount "
                    + name
                    + ":/ /data/data/pl.sviete.dom/dom_cloud_drives/"
                    + name
                    + " --uid "
                    + uid
                    + " --gid "
                    + gid
                    + " --allow-non-empty "
                    + " "
                    + G_RCLONE_CONF
                )

            else:
                #
                fix_rclone_config_permissions()
                # prepare mount command
                rclone_cmd_mount = (
                    'su -mm -c "export PATH=$PATH:/data/data/pl.sviete.dom/files/usr/bin/; rclone mount '
                    + name
                    + ":/ /data/data/pl.sviete.dom/dom_cloud_drives/"
                    + name
                    + " --allow-other"
                    + " --uid "
                    + uid
                    + " --gid "
                    + gid
                    + " "
                    + G_RCLONE_CONF
                    + '"'
                )
            os.system("mkdir -p /data/data/pl.sviete.dom/dom_cloud_drives/" + name)
            os.system(rclone_cmd_mount)

        else:
            self.say("Nie masz dodanego dysku zdalnego o nazwie " + name)

    def rclone_remove_drive(self, name):
        remotes = rclone_get_remotes_long()
        drive_exist = False
        for r in remotes:
            if name == r["name"]:
                drive_exist = True
        if drive_exist:
            # Delete an existing remote
            fix_rclone_config_permissions()
            rclone_cmd_remove_drive = (
                "rclone config delete " + name + " " + G_RCLONE_CONF
            )
            os.system(rclone_cmd_remove_drive)
        else:
            _LOGGER.error("rclone_remove_drive: NO drive in Rclone, name: " + name)

        # fusermount
        if not ais_global.has_root():
            os.system("fusermount -u /data/data/pl.sviete.dom/dom_cloud_drives/" + name)
        else:
            os.system(
                'su -mm -c "export PATH=$PATH:/data/data/pl.sviete.dom/files/usr/bin/; '
                + ' fusermount -u /data/data/pl.sviete.dom/dom_cloud_drives/"'
                + name
            )

        # delete drive folder
        os.system("rm -rf /data/data/pl.sviete.dom/dom_cloud_drives/" + name)

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
            self.say(
                "Synchronizuję lokalizację "
                + call.data["source_path"]
                + " z "
                + call.data["dest_path"]
                + " modyfikuję tylko "
                + call.data["source_path"]
            )

        rclone_cmd = [
            "rclone",
            "sync",
            call.data["source_path"],
            call.data["dest_path"],
            "--transfers=1",
            "--stats=0",
            G_RCLONE_CONF,
        ]
        #
        fix_rclone_config_permissions()
        #
        proc = subprocess.run(
            rclone_cmd, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        #  will wait for the process to complete and then we are going to return the output
        if "" != proc.stderr:
            self.say("Błąd podczas synchronizacji: " + proc.stderr)
        else:
            self.say("Synchronizacja zakończona.")

    def play_next(self, call):
        state = self.hass.states.get("sensor.ais_drives")
        attr = state.attributes
        files = attr.get("files", [])
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
        state = self.hass.states.get("sensor.ais_drives")
        attr = state.attributes
        files = attr.get("files", [])
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
        path = path.rstrip("/")
        path = path.rstrip(":")
        if path.count("/") > 0:
            name = path.split("/").pop()
        else:
            name = path.split(":").pop()
        name = name.replace(":", "")
        name = name.replace("-", " ")
        return name

    def remote_next_item(self, say):
        state = self.hass.states.get("sensor.ais_drives")
        attr = state.attributes
        files = attr.get("files", [])
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
        state = self.hass.states.get("sensor.ais_drives")
        attr = state.attributes
        files = attr.get("files", [])
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
        state = self.hass.states.get("sensor.ais_drives")
        attr = state.attributes
        files = attr.get("files", [])
        if state.state is None or self.selected_item_idx is None:
            self.selected_item_idx = 0
        if files[self.selected_item_idx]["path"] == G_LOCAL_FILES_ROOT:
            self.say("Wybierz pozycję")
        else:
            self._browse_path(files[self.selected_item_idx]["path"], say)

    def remote_cancel_item(self, say):
        self._browse_path("..", say)

    def remote_delete_item(self, say):
        state = self.hass.states.get("sensor.ais_drives")
        attr = state.attributes
        files = attr.get("files", [])
        if state.state is None or self.selected_item_idx is None:
            self.say("Brak pozycji do usunięcia")
        if files[self.selected_item_idx]["path"] == G_LOCAL_FILES_ROOT:
            self.say("Tej pozycji nie można usunąć")
        else:
            # delete file or folder
            path = files[self.selected_item_idx]["path"]
            if path.startswith(G_LOCAL_FILES_ROOT) and path != G_LOCAL_FILES_ROOT:
                if os.path.isdir(path):
                    # remove dir
                    import shutil

                    shutil.rmtree(path)
                    self.say("Usuwam folder " + files[self.selected_item_idx]["name"])
                else:
                    # remove file
                    os.remove(path)
                    self.say("Usuwam plik " + files[self.selected_item_idx]["name"])
                # browse this patch again
                from pathlib import Path

                parent_path = str(Path(path).parent)
                self._browse_path(parent_path, False)

            else:
                self.say("Tej pozycji nie można usunąć")

    async def async_load_all(self, hass):
        """Load all the folders and files."""
        from homeassistant.components import ais_cloud

        aisCloud = ais_cloud.AisCloudWS(hass)
        self.display_root_items(False)
        global G_DRIVE_SECRET, G_DRIVE_CLIENT_ID

        # version 0.105 config migration - to allow backup to AIS cloud
        if os.path.isfile(G_RCLONE_OLD_CONF_FILE):
            if not os.path.isfile(G_RCLONE_CONF_FILE):
                subprocess.call(
                    f"mv {G_RCLONE_OLD_CONF_FILE} {G_RCLONE_CONF_FILE}",
                    shell=True,  # nosec
                )

        # set client and secret
        try:
            json_ws_resp = await aisCloud.async_key("gdrive_client_id")
            G_DRIVE_CLIENT_ID = json_ws_resp["key"]
            json_ws_resp = await aisCloud.async_key("gdrive_secret")
            G_DRIVE_SECRET = json_ws_resp["key"]
        except Exception as e:
            _LOGGER.error("Error ais_drives_service async_load_all: " + str(e))
