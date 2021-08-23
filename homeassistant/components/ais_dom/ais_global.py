"""
Support for functionality to cache some data for AI-Speaker.
"""
import logging
import os
import platform
import socket

import requests

# LV settings
G_EMPTY_OPTION = "-"
G_FAVORITE_OPTION = "Moje Ulubione"
G_DRIVE_SHARED_WITH_ME = "Udostępnione dla mnie"

# TTS settings
GLOBAL_TTS_RATE = 1
GLOBAL_TTS_PITCH = 1
GLOBAL_TTS_VOICE = "pl-pl-x-oda-local"

# audio nature
G_AN_RADIO = "Radio"
G_AN_PODCAST_NAME = "PodcastName"
G_AN_PODCAST = "Podcast"
# Music == YouTube
G_AN_MUSIC = "Music"
G_AN_AUDIOBOOK = "AudioBook"
G_AN_AUDIOBOOK_CHAPTER = "AudioBookChapter"
G_AN_NEWS = "News"
G_AN_LOCAL = "Local"
G_AN_SPOTIFY_SEARCH = "SpotifySearch"
G_AN_SPOTIFY = "Spotify"
G_AN_BOOKMARK = "Bookmark"
G_AN_FAVORITE = "Favorite"
G_AN_GOOGLE_ASSISTANT = "GoogleAssistant"
G_LOCAL_EXO_PLAYER_ENTITY_ID = "media_player.wbudowany_glosnik"
G_CURR_MEDIA_CONTENT = {}

# actions on remote
G_ACTION_DELETE = "delete"
G_ACTION_SET_AUDIO_SPEED = "set_audio_speed"
G_ACTION_SET_AUDIO_SHUFFLE = "set_audio_shuffle"

G_ICON_FOR_AUDIO = {
    G_AN_RADIO: "mdi:radio",
    G_AN_PODCAST: "mdi:podcast",
    G_AN_MUSIC: "mdi:youtube",
    G_AN_AUDIOBOOK: "mdi:audiobook",
    G_AN_SPOTIFY: "mdi:spotify",
    G_AN_LOCAL: "mdi:folder",
    G_AN_FAVORITE: "mdi:heart",
    G_AN_BOOKMARK: "mdi:bookmark",
}

G_NAME_FOR_AUDIO_NATURE = {
    G_AN_RADIO: "Radio",
    G_AN_PODCAST: "Podcast",
    G_AN_MUSIC: "YouTube",
    G_AN_AUDIOBOOK: "Audio książka",
    G_AN_SPOTIFY: "Spotify",
    G_AN_LOCAL: "Dysk",
    G_AN_FAVORITE: "Moje Ulubione",
    G_AN_BOOKMARK: "Zakładki",
}

# tokens
G_OFFLINE_MODE = False

GLOBAL_MY_IP = None
GLOBAL_MY_WIFI_SSID = None
GLOBAL_MY_WIFI_PASS = None
GLOBAL_SCAN_WIFI_ANSWER = {}
_LOGGER = logging.getLogger(__name__)

# devices fully supported by ais dom
G_MODEL_SONOFF_S20 = "s20"
G_MODEL_SONOFF_SLAMPHER = "slampher"
G_MODEL_SONOFF_TOUCH = "sonoff_touch"
G_MODEL_SONOFF_TH = "sonoff_th"
G_MODEL_SONOFF_B1 = "sonoff_b1"
G_MODEL_SONOFF_POW = "sonoff_pow"
G_MODEL_SONOFF_DUAL = "sonoff_dual"
G_MODEL_SONOFF_BASIC = "sonoff_basic"
G_MODEL_SONOFF_IFAN = "sonoff_ifan"
G_MODEL_SONOFF_T11 = "sonoff_t11"
G_MODEL_SONOFF_T12 = "sonoff_t12"
G_MODEL_SONOFF_T13 = "sonoff_t13"
#
G_AIS_SECURE_ANDROID_DOM_FOLDER = "/data/data/pl.sviete.dom/files/home/AIS/.dom"
G_AIS_SECURE_ANDROID_ID_DOM = None
G_AIS_GATE_MODEL = None
G_AIS_SECURE_ANDROID_ID_DOM_FILE = (
    "/data/data/pl.sviete.dom/files/home/AIS/.dom/.ais_secure_android_id_dom"
)
#
G_AIS_GATE_REQ = {}

#
G_AIS_START_IS_DONE = False
G_AIS_NEW_DEVICE_NAME = ""
G_AIS_NEW_DEVICE_START_ADD_TIME = None

#
G_AIS_DAY_MEDIA_VOLUME_LEVEL = None
G_HTTP_REST_SERVICE_BASE_URL = "http://{}:8122"

#
G_USB_DEVICES = []
G_USB_INTERNAL_MIC_RESET = False

#
G_AIS_HOME_DIR = "/data/data/pl.sviete.dom/files/home"
G_REMOTE_DRIVES_DOM_PATH = "/data/data/pl.sviete.dom/files/home/dom/dyski-wymienne"
G_LOG_SETTINGS_INFO = None
G_DB_SETTINGS_INFO = None
G_USB_SETTINGS_INFO = {"usbAutoStartServices": True, "usbVoiceNotification": True}

#
G_AIS_DOM_PIN = ""

# files
G_AIS_IMG_PATH = "/data/data/pl.sviete.dom/files/home/AIS/www/img/"
G_LOG_SETTINGS_INFO_FILE = "/.dom/.ais_log_settings_info"
G_DB_SETTINGS_INFO_FILE = "/.dom/.ais_db_settings_info"
G_USB_SETTINGS_INFO_FILE = "/.dom/.ais_usb_settings_info"

# mqtt
G_AIS_MQTT_CONFIG_DIR_PATH = "/data/data/pl.sviete.dom/files/usr/etc/mosquitto"
G_AIS_MQTT_CONFIG_FILE_PATH = G_AIS_MQTT_CONFIG_DIR_PATH + "/mosquitto.conf"
G_AIS_MQTT_CONFIG_INCLUDE_DIR_PATH = G_AIS_MQTT_CONFIG_DIR_PATH + "/mqtt_conf.d"
G_AIS_SUPLA_MQTT_CONFIG_FILE_NAME = "supla.conf"

G_AUTOMATION_CONFIG = None

# DB
G_AIS_INCLUDE_DB_DEFAULT = {
    "domains": [
        "automation",
        "binary_sensor",
        "climate",
        "cover",
        "device_tracker",
        "light",
        "person",
        "sensor",
        "switch",
    ],
    "entity_globs": ["sun.su*"],
    "entities": ["sensor.version_info"],
}

G_AIS_EXCLUDE_DB_DEFAULT_EMPTY = {
    "domains": ["ais_ai_service"],
    "entity_globs": ["sensor.ais_*"],
    "entities": ["sensor.time"],
    "event_types": ["call_service"],
}
G_AIS_EXCLUDE_DB_DEFAULT = {
    "domains": [
            "ais_ai_service",
            "ais_amplifier_service",
            "ais_audiobooks_service",
            "ais_bookmarks",
            "ais_cloud",
            "ais_dom",
            "ais_dom_device",
            "ais_drives_service",
            "ais_exo_player",
            "ais_files",
            "ais_google_home",
            "ais_help",
            "ais_host",
            "ais_ingress",
            "ais_knowledge_service",
            "ais_mdns",
            "ais_shell_command",
            "ais_spotify_service",
            "ais_updater",
            "ais_usb",
            "ais_wifi_service",
            "ais_yt_service",
            "media_player",
            "group"],
    "entity_globs": [
        "automation.ais_*",
        "binary_sensor.ais_*",
        "group.ais_*",
        "group.all_ais_*",
        "input_boolean.ais_*",
        "input_select.ais_*",
        "input_text.ais_*",
        "script.ais_*",
        "sensor.ais*",
        "timer.ais_*",
    ],
    "entities": [
        "sensor.time",
        "input_select.book_autor",
        "group.audiobooks_player",
        "input_select.podcast_type",
        "input_select.radio_type",
        "sensor.daytodisplay",
        "group.day_info",
        "group.local_audio",
        "group.radio_player",
        "group.podcast_player",
        "group.music_player",
        "group.internet_status",
        "group.audio_player",
        "group.dom_system_version",
        "sensor.radiolist",
        "sensor.podcastnamelist",
        "sensor.youtubelist",
        "sensor.spotifysearchlist",
        "sensor.spotifylist",
        "sensor.rssnewslist",
        "input_select.rss_news_category",
        "input_select.rss_news_channel",
        "sensor.selected_entity",
        "sensor.wersja_kordynatora",
        "sensor.status_serwisu_zigbee2mqtt",
        "sensor.gate_pairing_pin",
        "persistent_notification.config_entry_discovery",
        "sensor.audiobookschapterslist",
        "automation.zigbee_tryb_parowania",
        "automation.zigbee_wylaczenie_trybu_parowania",
        "input_number.assistant_rate",
        "input_number.media_player_speed",
        "timer.ais_dom_pin_join",
        "media_player.wbudowany_glosnik",
        "input_number.assistant_tone",
        "timer.zigbee_permit_join",
        "input_select.book_name",
        "sensor.podcastlist",
        "sensor.audiobookslist",
        "sensor.rssnewstext",
        "switch.zigbee_tryb_parowania",
        "input_select.book_chapter",
        "input_select.assistant_voice",
        "input_select.media_player_sound_mode",
        "binary_sensor.updater",
        "weather.dom",
        "binary_sensor.selected_entity",
    ]
}


def set_ais_android_id_dom_file_path(path):
    global G_AIS_SECURE_ANDROID_ID_DOM_FILE
    G_AIS_SECURE_ANDROID_ID_DOM_FILE = path


def get_pass_for_ssid(ssid):
    for item in GLOBAL_SCAN_WIFI_ANSWER["ScanResult"]:
        if item["ssid"] == ssid:
            return item["pass"]
    return ""


# say the text without Home Assistant
def say_direct(text):
    j_data = {
        "text": text,
        "pitch": GLOBAL_TTS_PITCH,
        "rate": GLOBAL_TTS_RATE,
        "voice": GLOBAL_TTS_VOICE,
    }
    try:
        requests.post(
            G_HTTP_REST_SERVICE_BASE_URL.format("127.0.0.1") + "/text_to_speech",
            json=j_data,
            timeout=1,
        )
    except Exception as e:
        pass


def get_ais_gate_model():
    global G_AIS_GATE_MODEL
    if G_AIS_GATE_MODEL is not None:
        return G_AIS_GATE_MODEL

    try:
        ws_resp = requests.get(
            G_HTTP_REST_SERVICE_BASE_URL.format("127.0.0.1"), timeout=10
        )
        data = ws_resp.json()
        ais_model = data.get("Model")
        G_AIS_GATE_MODEL = ais_model
    except Exception:
        ais_model = platform.machine()
    return ais_model


def get_sercure_android_id_dom():
    global G_AIS_SECURE_ANDROID_ID_DOM
    if (
        G_AIS_SECURE_ANDROID_ID_DOM is not None
        and G_AIS_SECURE_ANDROID_ID_DOM.startswith("dom-")
    ):
        return G_AIS_SECURE_ANDROID_ID_DOM

    # get dom_id from file
    try:
        # add the dir .dom is not exits
        if not os.path.exists(G_AIS_SECURE_ANDROID_DOM_FOLDER):
            os.makedirs(G_AIS_SECURE_ANDROID_DOM_FOLDER)
        with open(G_AIS_SECURE_ANDROID_ID_DOM_FILE) as fptr:
            dom_id = fptr.read().replace("\n", "")
            if dom_id.startswith("dom-"):
                G_AIS_SECURE_ANDROID_ID_DOM = dom_id
                return G_AIS_SECURE_ANDROID_ID_DOM
    except Exception as e:
        _LOGGER.info("Error get_sercure_android_id_dom " + str(e))

    # get dom_id from secure android settings and save in file
    import subprocess

    android_id = ""
    if not has_root():
        # to support local test
        from uuid import getnode as get_mac

        android_id = get_mac()
    else:
        try:
            android_id = subprocess.check_output(
                'su -c "settings get secure android_id"',
                shell=True,  # nosec
                timeout=10,
            )
            android_id = android_id.decode("utf-8").replace("\n", "")
        except Exception as e:
            _LOGGER.error("Error get_sercure_android_id_dom " + str(e))

    # save in file
    if android_id != "":
        with open(G_AIS_SECURE_ANDROID_ID_DOM_FILE, "w") as fptr:
            fptr.write("dom-" + str(android_id))
            G_AIS_SECURE_ANDROID_ID_DOM = "dom-" + str(android_id)
    return G_AIS_SECURE_ANDROID_ID_DOM


def get_milliseconds_formated(millis):
    try:
        millis = int(millis)
        seconds = (millis / 1000) % 60
        seconds = int(seconds)
        minutes = (millis / (1000 * 60)) % 60
        minutes = int(minutes)
        hours = (millis / (1000 * 60 * 60)) % 24
        return "%d:%d:%d" % (hours, minutes, seconds)
    except Exception:
        return "%d:%d:%d" % (0, 0, 0)


def set_my_ssid(ssid):
    global GLOBAL_MY_WIFI_SSID
    GLOBAL_MY_WIFI_SSID = ssid


# we need this to connect the iot device
def set_my_wifi_pass(wifi_pass):
    global GLOBAL_MY_WIFI_PASS
    GLOBAL_MY_WIFI_PASS = wifi_pass


def get_my_global_ip():
    if GLOBAL_MY_IP is None:
        set_global_my_ip(None)
    return GLOBAL_MY_IP


def set_global_my_ip(pIP):
    global GLOBAL_MY_IP
    if pIP is None:
        try:
            GLOBAL_MY_IP = (
                (
                    [
                        ip
                        for ip in socket.gethostbyname_ex(socket.gethostname())[2]
                        if not ip.startswith("127.")
                    ]
                    or [
                        [
                            (s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close())
                            for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]
                        ][0][1]
                    ]
                )
                + ["no IP found"]
            )[0]
        except Exception as e:
            _LOGGER.error("Error: " + str(e))
            GLOBAL_MY_IP = "127.0.0.1"
    else:
        GLOBAL_MY_IP = pIP


# to handle async req to gate
def set_ais_gate_req(req_id, req_answer=None):
    global G_AIS_GATE_REQ
    G_AIS_GATE_REQ[req_id] = req_answer


def get_ais_gate_req_answer(req_id):
    global G_AIS_GATE_REQ
    return G_AIS_GATE_REQ.get(req_id, None)


def get_audio_speed_name(speed):
    l_speed = int(float(speed) * 100)
    if l_speed == 100:
        return "normalna"
    elif l_speed < 100:
        return "wolniej o " + str(100 - l_speed) + "%"
    elif l_speed > 100:
        return "szybciej o " + str(l_speed) + "%"


def has_root():
    if platform.machine() == "x86_64":
        return False

    import subprocess

    try:
        subprocess.check_output("su -c echo", shell=True)  # nosec
    except Exception as e:
        _LOGGER.info("No access to root")
        return False
    return True


def has_front_clock():
    if platform.machine() == "x86_64":
        # return True for test on x86_64
        # return True
        return False

    import subprocess

    try:
        subprocess.check_output(
            "su -c 'ls /data/local/ais_screen_control'", shell=True  # nosec
        )
    except Exception as e:
        _LOGGER.info("No front clock")
        return False
    return True


# save ais mqtt connection settings
def save_ais_mqtt_connection_settings(config_file_name, mqtt_bridge_settings=None):
    with open(G_AIS_MQTT_CONFIG_FILE_PATH, "w") as conf_file:
        # 1. standard ais settings
        conf_file.write("# AIS Config file for mosquitto on gate\n")
        conf_file.write("listener 1883 0.0.0.0\n")
        conf_file.write("allow_anonymous true\n")
        conf_file.write("include_dir " + G_AIS_MQTT_CONFIG_INCLUDE_DIR_PATH + "\n")
        if not os.path.exists(G_AIS_MQTT_CONFIG_INCLUDE_DIR_PATH):
            os.makedirs(G_AIS_MQTT_CONFIG_INCLUDE_DIR_PATH, exist_ok=True)

        if mqtt_bridge_settings is not None:
            # 2. MQTT bridge connection settings
            with open(
                G_AIS_MQTT_CONFIG_INCLUDE_DIR_PATH + "/" + config_file_name, "w"
            ) as conf_bridge_file:
                conf_bridge_file.write("\n")
                conf_bridge_file.write(
                    "# MQTT bridge connection " + config_file_name + "\n"
                )
                conf_bridge_file.write(
                    "connection bridge-" + get_sercure_android_id_dom() + "\n"
                )
                conf_bridge_file.write(
                    "address "
                    + mqtt_bridge_settings["host"]
                    + ":"
                    + str(mqtt_bridge_settings["port"])
                    + "\n"
                )
                conf_bridge_file.write("topic supla/# in\n")
                conf_bridge_file.write("topic homeassistant/# in\n")
                conf_bridge_file.write(
                    "topic supla/+/devices/+/channels/+/execute_action out\n"
                )
                conf_bridge_file.write("topic supla/+/devices/+/channels/+/set/+ out\n")
                conf_bridge_file.write(
                    "remote_username " + mqtt_bridge_settings["username"] + "\n"
                )
                conf_bridge_file.write(
                    "remote_password " + mqtt_bridge_settings["password"] + "\n"
                )
                conf_bridge_file.write(
                    "bridge_cafile /data/data/pl.sviete.dom/files/usr/etc/tls/cert.pem\n"
                )
        else:
            # clear the config by removing file
            os.remove(G_AIS_MQTT_CONFIG_INCLUDE_DIR_PATH + "/" + config_file_name)


set_global_my_ip(None)
