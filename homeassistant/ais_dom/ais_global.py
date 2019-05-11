"""
Support for functionality to cache some data for AI-Speaker.
"""
import socket
import logging

# LV settings
G_EMPTY_OPTION = "-"
G_FAVORITE_OPTION = "Ulubione"
G_DRIVE_SHARED_WITH_ME = "Udostępnione dla mnie"

# TTS settings
GLOBAL_TTS_RATE = 1
GLOBAL_TTS_PITCH = 1
GLOBAL_TTS_VOICE = 'pl-pl-x-oda-local'

# audio nature
G_AN_RADIO = "Radio"
G_AN_PODCAST_NAME = "PodcastName"
G_AN_PODCAST = "Podcast"
# Music == YouTube
G_AN_MUSIC = "Music"
G_AN_AUDIOBOOK = "AudioBook"
G_AN_NEWS = "News"
G_AN_LOCAL = "Local"
G_AN_SPOTIFY_SEARCH = "SpotifySearch"
G_AN_SPOTIFY = "Spotify"
G_AN_BOOKMARK = "Bookmark"
G_AN_FAVORITE = "Favorite"
G_LOCAL_EXO_PLAYER_ENTITY_ID = "media_player.wbudowany_glosnik"
G_CURR_MEDIA_CONTENT = {}

# actions on remote
G_ACTION_DELETE = 'delete'


G_ICON_FOR_AUDIO = {
    G_AN_RADIO: 'mdi:radio',
    G_AN_PODCAST: 'mdi:podcast',
    G_AN_MUSIC: 'mdi:youtube',
    G_AN_AUDIOBOOK: 'mdi:audiobook',
    G_AN_SPOTIFY: 'mdi:spotify',
    G_AN_LOCAL: 'mdi:folder',
    G_AN_FAVORITE: 'mdi:heart',
    G_AN_BOOKMARK: 'mdi:bookmark'
}

G_NAME_FOR_AUDIO_NATURE = {
    G_AN_RADIO: 'Radio',
    G_AN_PODCAST: 'Podcast',
    G_AN_MUSIC: 'YouTube',
    G_AN_AUDIOBOOK: 'Audio książka',
    G_AN_SPOTIFY: 'Spotify',
    G_AN_LOCAL: 'Plik',
    G_AN_FAVORITE: 'Ulubione',
    G_AN_BOOKMARK: 'Zakładki'
}

# tokens
G_OFFLINE_MODE = False


GLOBAL_MY_IP = None
GLOBAL_MY_WIFI_SSID = None
GLOBAL_MY_WIFI_PASS = None
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
G_AIS_SECURE_ANDROID_ID_DOM = None

#
G_AIS_GATE_REQ = {}


def get_sercure_android_id_dom():
    global G_AIS_SECURE_ANDROID_ID_DOM
    if G_AIS_SECURE_ANDROID_ID_DOM is None:
        import subprocess
        try:
            android_id = subprocess.check_output('su -c "settings get secure android_id"', shell=True, timeout=10)
            android_id = android_id.decode("utf-8").replace('\n', '')
        except Exception:
            _LOGGER.warning("Can't get secure gate id for the device!")
            from uuid import getnode as get_mac
            android_id = get_mac()

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
            GLOBAL_MY_IP = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2]
                      if not ip.startswith('127.')] or [[(s.connect(('8.8.8.8', 53)),
                      s.getsockname()[0], s.close()) for s in
                      [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]])
                      + ['no IP found'])[0]
        except Exception as e:
            _LOGGER.error("Error: " + str(e))
            GLOBAL_MY_IP = '127.0.0.1'
    else:
        GLOBAL_MY_IP = pIP


# to handle async req to gate
def set_ais_gate_req(req_id, req_answer=None):
    global G_AIS_GATE_REQ
    G_AIS_GATE_REQ[req_id] = req_answer


def get_ais_gate_req_answer(req_id):
    global G_AIS_GATE_REQ
    return G_AIS_GATE_REQ.get(req_id, None)


set_global_my_ip(None)

