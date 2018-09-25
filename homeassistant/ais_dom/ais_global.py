"""
Support for functionality to cache some data for AI-Speaker.
"""
import socket
import logging

# LV settings
G_EMPTY_OPTION = "-"

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


# tokens
G_OFFLINE_MODE = False


GLOBAL_MY_IP = None
GLOBAL_MY_SSID = None
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

G_Y_WEATHER_CODES = {0: 'tornado', 1: 'tropikalna burza', 2: 'huragany', 3: 'silne burze z piorunami',
                     4: 'burze z piorunami', 5: 'mieszane opady deszczu i śniegu',
                     6: 'mieszane opady deszczu i deszczu ze śniegiem', 7: 'mieszany śnieg i deszcz ze śniegiem',
                     8: 'marznąca mżawka', 9: 'mżawka', 10: 'marznący deszcz', 11: 'przelotne opady',
                     12: 'przelotne opady', 13: 'przelotne opady śniegu', 14: 'lekkie przelotne opady śniegu',
                     15: 'śnieg', 16: 'śnieg', 17: 'grad', 18: 'deszcz ze śniegiem', 19: 'kurzu', 20: 'mglisto',
                     21: 'zamglenie', 22: 'zamglenie', 23: 'przenikliwy wiatr', 24: 'wietrznie', 25: 'zimno',
                     26: 'pochmurno', 27: 'pochmurno (noc)', 28: 'pochmurno (dzień)',
                     29: 'częściowo zachmurzenie (noc)', 30: 'pochmurno (dzień)', 31: 'jasna noc',
                     32: 'słonecznie', 33: 'ładna (noc)', 34: 'ładny (dzień)', 35: 'mieszany deszcz i grad',
                     36: 'gorąco', 37: 'przelotne burze', 38: 'rozproszone burze z piorunami',
                     39: 'rozproszone burze z piorunami', 40: 'rozproszonych przelotne opady', 41: 'ciężki śnieg',
                     42: 'przelotne opady śniegu', 43: 'ciężki śnieg', 44: 'pochmurno', 45: 'przelotne opady deszczu',
                     46: 'przelotne opady śniegu', 47: 'odizolowane przelotne opady deszczu', 3200: ''}


def set_my_ssid(ssid):
    global GLOBAL_MY_SSID
    GLOBAL_MY_SSID = ssid

def get_my_global_ip():
    if GLOBAL_MY_IP is None:
        set_global_my_ip()
    return GLOBAL_MY_IP


def set_global_my_ip():
    global GLOBAL_MY_IP
    try:
        GLOBAL_MY_IP = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2]
                  if not ip.startswith('127.')] or [[(s.connect(('8.8.8.8', 53)),
                  s.getsockname()[0], s.close()) for s in
                  [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]])
                  + ['no IP found'])[0]
    except Exception as e:
        _LOGGER.error("Error: " + str(e))
        GLOBAL_MY_IP = '127.0.0.1'


set_global_my_ip()

