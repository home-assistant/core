"""
Support for functionality to cache some data for AI-Speaker.
"""
import socket
import logging

# LV settings
G_EMPTY_OPTION = "-"
G_DRIVE_SHARED_WITH_ME = "Udostępnione dla mnie"

# TTS settings
GLOBAL_TTS_RATE = 1
GLOBAL_TTS_PITCH = 1
GLOBAL_TTS_VOICE = 'pl-pl-x-oda-local'

# audio nature
G_AN_RADIO = "Radio"
G_AN_PODCAST = "Podcast"
G_AN_MUSIC = "Music"
G_AN_AUDIOBOOK = "AudioBook"
G_AN_NEWS = "News"
G_AN_LOCAL = "Local"
G_AN_SPOTIFY = "Spotify"

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

G_BOOKMARK_MEDIA_POSITION = 0
G_BOOKMARK_MEDIA_CONTENT_ID = ""

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


def set_media_bookmark(media_content_id, position):
    global G_BOOKMARK_MEDIA_POSITION
    global G_BOOKMARK_MEDIA_CONTENT_ID
    G_BOOKMARK_MEDIA_POSITION = position
    G_BOOKMARK_MEDIA_CONTENT_ID = media_content_id


def get_bookmark_position(media_content_id):
    global G_BOOKMARK_MEDIA_POSITION
    global G_BOOKMARK_MEDIA_CONTENT_ID
    if G_BOOKMARK_MEDIA_CONTENT_ID != media_content_id:
        # reset the bookmark
        G_BOOKMARK_MEDIA_CONTENT_ID = ""
        G_BOOKMARK_MEDIA_POSITION = 0
    return G_BOOKMARK_MEDIA_POSITION


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

