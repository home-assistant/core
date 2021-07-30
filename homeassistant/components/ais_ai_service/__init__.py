"""
Support for functionality to have conversations with AI-Speaker.

"""
import asyncio
import datetime
import json
import logging
import re
import subprocess
import warnings
import platform

from aiohttp.web import json_response
import async_timeout
import psutil
import requests
import voluptuous as vol

from homeassistant import core
from homeassistant.components import ais_cloud, ais_drives_service, conversation
import homeassistant.components.ais_dom.ais_global as ais_global
from homeassistant.components.blueprint import BlueprintInputs
from homeassistant.components.conversation.default_agent import (
    DefaultAgent,
    async_register,
)
import homeassistant.components.mqtt as mqtt
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_DISARMING,
    STATE_ALARM_TRIGGERED,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_HOME,
    STATE_IDLE,
    STATE_LOCKED,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_OK,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_PROBLEM,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
)
from homeassistant.helpers import config_validation as cv, event, intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util

from ..automation import AutomationConfig
from .ais_agent import AisAgent

aisCloudWS = None

ATTR_TEXT = "text"
DOMAIN = "ais_ai_service"

REGEX_TURN_COMMAND = re.compile(r"turn (?P<name>(?: |\w)+) (?P<command>\w+)")

SERVICE_PROCESS_SCHEMA = vol.Schema({vol.Required(ATTR_TEXT): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("intents"): vol.Schema(
                    {cv.string: vol.All(cv.ensure_list, [cv.string])}
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

INTENT_GET_TIME = "AisGetTime"
INTENT_GET_DATE = "AisGetDate"
INTENT_PLAY_RADIO = "AisPlayRadio"
INTENT_PLAY_PODCAST = "AisPlayPodcast"
INTENT_PLAY_YT_MUSIC = "AisPlayYtMusic"
INTENT_PLAY_SPOTIFY = "AisPlaySpotify"
INTENT_ASK_QUESTION = "AisAskQuestion"
INTENT_ASKWIKI_QUESTION = "AisAskWikiQuestion"
INTENT_CHANGE_CONTEXT = "AisChangeContext"
INTENT_GET_WEATHER = "AisGetWeather"
INTENT_GET_WEATHER_48 = "AisGetWeather48"
INTENT_STATUS = "AisStatusInfo"
INTENT_PERSON_STATUS = "AisPersonStatusInfo"
INTENT_TURN_ON = "AisTurnOn"
INTENT_TURN_OFF = "AisTurnOff"
INTENT_TOGGLE = "AisToggle"
INTENT_LAMPS_ON = "AisLampsOn"
INTENT_LAMPS_OFF = "AisLampsOff"
INTENT_SWITCHES_ON = "AisSwitchesOn"
INTENT_SWITCHES_OFF = "AisSwitchesOff"
INTENT_OPEN_COVER = "AisCoverOpen"
INTENT_CLOSE_COVER = "AisCoverClose"
INTENT_STOP = "AisStop"
INTENT_PLAY = "AisPlay"
INTENT_NEXT = "AisNext"
INTENT_PREV = "AisPrev"
INTENT_SCENE = "AisSceneActive"
INTENT_SAY_IT = "AisSayIt"
INTENT_CLIMATE_SET_TEMPERATURE = "AisClimateSetTemperature"
INTENT_CLIMATE_SET_PRESENT_MODE = "AisClimateSetPresentMode"
INTENT_CLIMATE_SET_ALL_ON = "AisClimateSetAllOn"
INTENT_CLIMATE_SET_ALL_OFF = "AisClimateSetAllOff"
INTENT_SPELL_STATUS = "AisSpellStatusInfo"
INTENT_RUN_AUTOMATION = "AisRunAutomation"
INTENT_ASK_GOOGLE = "AisAskGoogle"

REGEX_TYPE = type(re.compile(""))

_LOGGER = logging.getLogger(__name__)
GROUP_VIEWS = ["Pomoc", "Mój Dom", "Audio", "Ustawienia"]
CURR_GROUP_VIEW = None
# group entities in each group view, see main_ais_groups.yaml
GROUP_ENTITIES = []
CURR_GROUP = None
CURR_ENTITIE = None
CURR_ENTITIE_ENTERED = False
CURR_ENTITIE_SELECTED_ACTION = None
CURR_BUTTON_CODE = None
CURR_BUTTON_LONG_PRESS = False
CURR_REMOTE_MODE_IS_IN_AUDIO_MODE = False
CURR_ENTITIE_POSITION = None
PREV_CURR_GROUP = None
PREV_CURR_ENTITIE = None

ALL_SWITCHES = [
    "input_boolean",
    "automation",
    "switch",
    "light",
    "media_player",
    "script",
]

# ais-dom virtual keyboard
# kodowała to Asia Raczkowska w 2019 roku
VIRTUAL_KEYBOARD_MODE = [
    "Litery",
    "Wielkie litery",
    "Cyfry",
    "Znaki specjalne",
    "Usuwanie",
]
CURR_VIRTUAL_KEYBOARD_MODE = None
VIRTUAL_KEYBOARD_LETTERS = [
    "-",
    "A",
    "Ą",
    "B",
    "C",
    "Ć",
    "D",
    "E",
    "Ę",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "Ł",
    "M",
    "N",
    "Ń",
    "O",
    "Ó",
    "P",
    "Q",
    "R",
    "S",
    "Ś",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
    "Ź",
    "Ż",
]
VIRTUAL_KEYBOARD_NUMBERS = ["-", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
VIRTUAL_KEYBOARD_SYMBOLS = [
    "-",
    " ",
    "!",
    '"',
    "#",
    "$",
    "%",
    "&",
    "'",
    "(",
    ")",
    "*",
    "+",
    ",",
    "-",
    "_",
    ".",
    "/",
    ":",
    ";",
    "<",
    "=",
    ">",
    "?",
    "@",
    "[",
    "\\",
    "]",
    "^",
    "{",
    "|",
    "}",
]
VIRTUAL_KEYBOARD_SYMBOLS_NAMES = [
    "-",
    "spacja",
    "wykrzyknik",
    "cudzysłów",
    "hash",
    "dolar",
    "procent",
    "symbol and",
    "pojedynczy cudzysłów",
    "nawias otwierający",
    "nawias zamykający",
    "gwiazdka",
    "plus",
    "przecinek",
    "myślnik",
    "podkreślenie dolne",
    "kropka",
    "ukośnik prawy",
    "dwukropek",
    "średnik",
    "znak mniejszości",
    "znak równości",
    "znak większości",
    "znak zapytania",
    "małpa",
    "kwadratowy nawias otwierający",
    "ukośnik lewy",
    "kwadratowy nawias zamykający",
    "daszek",
    "nawias klamrowy otwierający",
    "kreska pionowa",
    "nawias klamrowy zamykający",
]
VIRTUAL_KEYBOARD_DELETE = ["-", "ostatni znak", "ostatni wyraz", "całe pole"]
CURR_VIRTUAL_KEYBOARD_VALUE = None
CURR_VIRTUAL_KEY = None
# ais-dom virtual keyboard
G_INPUT_CURRENT_HOUR = None
G_INPUT_CURRENT_MINNUTE = None


def is_switch(entity_id):
    global ALL_SWITCHES
    # problem with startswith and tuple of strings
    for s in ALL_SWITCHES:
        if entity_id.startswith(s):
            return True
    return False


@core.callback
@bind_hass
def async_register(hass, intent_type, utterances):
    """Register an intent.
    Registrations don't require conversations to be loaded. They will become
    active once the conversation component is loaded.
    """
    intents = hass.data.get(DOMAIN)

    if intents is None:
        intents = hass.data[DOMAIN] = {}

    conf = intents.get(intent_type)

    if conf is None:
        conf = intents[intent_type] = []

    for utterance in utterances:
        if isinstance(utterance, REGEX_TYPE):
            conf.append(utterance)
        else:
            conf.append(_create_matcher(utterance))


def translate_state(state):
    info_data = ""
    device_class = ""
    try:
        info_data = state.state
        domain = state.domain
        if domain == "binary_sensor":
            device_class = state.attributes.get("device_class", "")
    except Exception as e:
        _LOGGER.error("translate_state: " + str(e))

    if info_data == STATE_ON:
        info_data = "włączone"
        if device_class == "battery":
            info_data = "niski"
        elif device_class == "cold":
            info_data = "zimno"
        elif device_class == "connectivity":
            info_data = "podłączone"
        elif device_class == "door":
            info_data = "otwarte"
        elif device_class == "garage_door":
            info_data = "otwarte"
        elif device_class == "gas":
            info_data = "gaz wykryty"
        elif device_class == "heat":
            info_data = "gorąco"
        elif device_class == "light":
            info_data = "wykryto światło"
        elif device_class == "lock":
            info_data = "otwarte (odblokowane)"
        elif device_class == "moisture":
            info_data = "wilgoć wykrytą (mokra)"
        elif device_class == "motion":
            info_data = "wykrycie ruchu"
        elif device_class == "moving":
            info_data = "wykrycie ruchu"
        elif device_class == "occupancy":
            info_data = "zajęty"
        elif device_class == "opening":
            info_data = "otwarte"
        elif device_class == "plug":
            info_data = "podłączone"
        elif device_class == "power":
            info_data = "wykrycie zasilania"
        elif device_class == "presence":
            info_data = "obecny"
        elif device_class == "problem":
            info_data = "wykryty problem"
        elif device_class == "safety":
            info_data = "niebezpiecznie"
        elif device_class == "smoke":
            info_data = "dym wykrywany"
        elif device_class == "sound":
            info_data = "dźwięk wykryty"
        elif device_class == "vibration":
            info_data = "wykrycie wibracji"
        elif device_class == "window":
            info_data = "otwarte"
    elif info_data == STATE_OFF:
        info_data = "wyłączone"
        if device_class == "battery":
            info_data = "normalny"
        elif device_class == "cold":
            info_data = "normalnie"
        elif device_class == "connectivity":
            info_data = "odłączone"
        elif device_class == "door":
            info_data = "zamknięte"
        elif device_class == "garage_door":
            info_data = "zamknięte"
        elif device_class == "gas":
            info_data = "brak gazu (czysto)"
        elif device_class == "heat":
            info_data = "normalnie"
        elif device_class == "light":
            info_data = "brak światła"
        elif device_class == "lock":
            info_data = "zamknięte (zablokowane)"
        elif device_class == "moisture":
            info_data = " brak wilgoci (sucha)"
        elif device_class == "motion":
            info_data = "brak ruchu"
        elif device_class == "moving":
            info_data = "brak ruchu"
        elif device_class == "occupancy":
            info_data = "wolne"
        elif device_class == "opening":
            info_data = "zamknięte"
        elif device_class == "plug":
            info_data = "odłączone"
        elif device_class == "power":
            info_data = "brak zasilania"
        elif device_class == "presence":
            info_data = "nieobecny"
        elif device_class == "problem":
            info_data = "brak problemu (OK)"
        elif device_class == "safety":
            info_data = "bezpiecznie"
        elif device_class == "smoke":
            info_data = "brak dymu"
        elif device_class == "sound":
            info_data = "brak dźwięku"
        elif device_class == "vibration":
            info_data = "brak wibracji"
        elif device_class == "window":
            info_data = "zamknięte"
    elif info_data == STATE_HOME:
        info_data = "w domu"
    elif info_data == STATE_NOT_HOME:
        info_data = "poza domem"
    elif info_data == STATE_UNKNOWN:
        info_data = "status nieznany"
    elif info_data == STATE_OPEN:
        info_data = "otwarty"
    elif info_data == STATE_OPENING:
        info_data = "otwieranie"
    elif info_data == STATE_CLOSED:
        info_data = "zamknięty"
    elif info_data == STATE_CLOSING:
        info_data = "zamykanie"
    elif info_data == STATE_PAUSED:
        info_data = "pauza"
    elif info_data == STATE_PLAYING:
        info_data = "odtwarzanie"
    elif info_data == STATE_IDLE:
        info_data = "status bezczynny"
    elif info_data == STATE_STANDBY:
        info_data = "status bezczynny"
    elif info_data == STATE_ALARM_DISARMED:
        info_data = "status rozbrojony"
    elif info_data == STATE_ALARM_ARMED_HOME:
        info_data = "status uzbrojony w domu"
    elif info_data == STATE_ALARM_ARMED_AWAY:
        info_data = "status uzbrojony poza domem"
    elif info_data == STATE_ALARM_ARMED_NIGHT:
        info_data = "status uzbrojony noc"
    elif info_data == STATE_ALARM_ARMED_CUSTOM_BYPASS:
        info_data = "status uzbrojony własny"
    elif info_data == STATE_ALARM_ARMING:
        info_data = "alarm uzbrajanie"
    elif info_data == STATE_ALARM_DISARMING:
        info_data = "alarm rozbrajanie"
    elif info_data == STATE_ALARM_TRIGGERED:
        info_data = "alarm powiadomiony"
    elif info_data == STATE_LOCKED:
        info_data = "zamknięty"
    elif info_data == STATE_UNLOCKED:
        info_data = "otwarty"
    elif info_data == STATE_UNAVAILABLE:
        info_data = "niedostępny"
    elif info_data == STATE_OK:
        info_data = "ok"
    elif info_data == STATE_PROBLEM:
        info_data = "problem"
    elif info_data == "above_horizon":
        info_data = "powyżej horyzontu"
    elif info_data == "below_horizon":
        info_data = "poniżej horyzontu"
    elif info_data == "heat":
        info_data = "grzanie"
    elif info_data == "cleaning":
        info_data = "sprzątanie"
    elif info_data == "docked":
        info_data = "w stacji dokującej"
    elif info_data == "returning":
        info_data = "powrót do stacji dokującej"

    return info_data


def get_next(arra, curr):
    _first = None
    _curr = None
    _next = None
    for a in arra:
        # ignore empy option
        if a != ais_global.G_EMPTY_OPTION:
            if _curr is not None and _next is None:
                _next = a
            if _first is None:
                _first = a
            if curr == a:
                _curr = a
    if _next is not None:
        return _next
    else:
        return _first


def get_prev(arra, curr):
    _last = None
    _curr = None
    _prev = None
    for a in arra:
        # ignore empy option
        if a != ais_global.G_EMPTY_OPTION:
            _last = a
            if curr == a:
                _curr = a
            if _curr is None:
                _prev = a
    if _prev is not None:
        return _prev
    else:
        return _last


# Group views: Dom -> Audio -> Ustawienia -> Pomoc
def get_curr_group_view():
    if CURR_GROUP_VIEW is None:
        return GROUP_VIEWS[0]
    return CURR_GROUP_VIEW


def say_curr_group_view(hass):
    _say_it(hass, get_curr_group_view())


def set_curr_group_view():
    # set focus on current menu group view
    global CURR_GROUP_VIEW
    global CURR_GROUP
    global CURR_ENTITIE
    global CURR_ENTITIE_ENTERED
    global CURR_ENTITIE_POSITION
    CURR_GROUP = None
    CURR_ENTITIE = None
    CURR_ENTITIE_ENTERED = False
    CURR_ENTITIE_POSITION = None
    CURR_GROUP_VIEW = get_curr_group_view()


def set_next_group_view():
    # set focus on next menu group view
    global CURR_GROUP_VIEW
    CURR_GROUP_VIEW = get_next(GROUP_VIEWS, get_curr_group_view())
    # to reset
    set_curr_group_view()


def set_prev_group_view():
    # set focus on prev menu group view
    global CURR_GROUP_VIEW
    CURR_GROUP_VIEW = get_prev(GROUP_VIEWS, get_curr_group_view())
    # to reset
    set_curr_group_view()


# virtual keybord
# Group views: Litery -> Wielkie litery -> Cyfry -> Znaki specjalne -> Usuwanie
def get_curr_virtual_keyboard_mode():
    if CURR_VIRTUAL_KEYBOARD_MODE is None:
        return VIRTUAL_KEYBOARD_MODE[0]
    return CURR_VIRTUAL_KEYBOARD_MODE


def set_next_virtual_keyboard_mode():
    global CURR_VIRTUAL_KEYBOARD_MODE
    global CURR_VIRTUAL_KEY
    CURR_VIRTUAL_KEY = None
    CURR_VIRTUAL_KEYBOARD_MODE = get_next(
        VIRTUAL_KEYBOARD_MODE, get_curr_virtual_keyboard_mode()
    )


def set_prev_virtual_keyboard_mode():
    global CURR_VIRTUAL_KEYBOARD_MODE
    global CURR_VIRTUAL_KEY
    CURR_VIRTUAL_KEY = None
    CURR_VIRTUAL_KEYBOARD_MODE = get_prev(
        VIRTUAL_KEYBOARD_MODE, get_curr_virtual_keyboard_mode()
    )


def say_curr_virtual_keyboard_mode(hass):
    _say_it(hass, get_curr_virtual_keyboard_mode())


def get_curr_virtual_key():
    if CURR_VIRTUAL_KEY is not None:
        return str(CURR_VIRTUAL_KEY)
    km = get_curr_virtual_keyboard_mode()
    if km == "Litery":
        return VIRTUAL_KEYBOARD_LETTERS[0]
    elif km == "Wielkie litery":
        return VIRTUAL_KEYBOARD_LETTERS[0]
    elif km == "Cyfry":
        return VIRTUAL_KEYBOARD_NUMBERS[0]
    elif km == "Znaki specjalne":
        return VIRTUAL_KEYBOARD_SYMBOLS[0]
    elif km == "Usuwanie":
        return VIRTUAL_KEYBOARD_DELETE[0]


def set_next_virtual_key():
    global CURR_VIRTUAL_KEY
    km = get_curr_virtual_keyboard_mode()
    if km == "Litery":
        CURR_VIRTUAL_KEY = get_next(VIRTUAL_KEYBOARD_LETTERS, get_curr_virtual_key())
    elif km == "Wielkie litery":
        CURR_VIRTUAL_KEY = get_next(VIRTUAL_KEYBOARD_LETTERS, get_curr_virtual_key())
    elif km == "Cyfry":
        CURR_VIRTUAL_KEY = get_next(VIRTUAL_KEYBOARD_NUMBERS, get_curr_virtual_key())
    elif km == "Znaki specjalne":
        CURR_VIRTUAL_KEY = get_next(VIRTUAL_KEYBOARD_SYMBOLS, get_curr_virtual_key())
    elif km == "Usuwanie":
        CURR_VIRTUAL_KEY = get_next(VIRTUAL_KEYBOARD_DELETE, get_curr_virtual_key())


def set_prev_virtual_key():
    global CURR_VIRTUAL_KEY
    km = get_curr_virtual_keyboard_mode()
    if km == "Litery":
        CURR_VIRTUAL_KEY = get_prev(VIRTUAL_KEYBOARD_LETTERS, get_curr_virtual_key())
    elif km == "Wielkie litery":
        CURR_VIRTUAL_KEY = get_prev(VIRTUAL_KEYBOARD_LETTERS, get_curr_virtual_key())
    elif km == "Cyfry":
        CURR_VIRTUAL_KEY = get_prev(VIRTUAL_KEYBOARD_NUMBERS, get_curr_virtual_key())
    elif km == "Znaki specjalne":
        CURR_VIRTUAL_KEY = get_prev(VIRTUAL_KEYBOARD_SYMBOLS, get_curr_virtual_key())
    elif km == "Usuwanie":
        CURR_VIRTUAL_KEY = get_prev(VIRTUAL_KEYBOARD_DELETE, get_curr_virtual_key())


def say_curr_virtual_key(hass):
    key = get_curr_virtual_key()
    km = get_curr_virtual_keyboard_mode()
    text = ""
    if km == "Litery":
        text = "" + key.lower()
    elif km == "Wielkie litery":
        text = "" + key
    elif km == "Cyfry":
        text = "" + key
    elif km == "Znaki specjalne":
        idx = VIRTUAL_KEYBOARD_SYMBOLS.index(key)
        text = "" + VIRTUAL_KEYBOARD_SYMBOLS_NAMES[idx]
    elif km == "Usuwanie":
        text = "" + key

    _say_it(hass, text)


def reset_virtual_keyboard(hass):
    global CURR_VIRTUAL_KEYBOARD_MODE
    global CURR_VIRTUAL_KEY
    global CURR_VIRTUAL_KEYBOARD_VALUE
    CURR_VIRTUAL_KEYBOARD_MODE = None
    CURR_VIRTUAL_KEY = None
    CURR_VIRTUAL_KEYBOARD_VALUE = None
    # reset field value
    hass.services.call(
        "input_text", "set_value", {"entity_id": CURR_ENTITIE, "value": ""}
    )


def get_hour_to_say(h, m):
    from datetime import time

    import babel.dates

    t = time(h, m)
    message = "godzina: " + babel.dates.format_time(t, format="short", locale="pl")
    return message


def set_time_hour_up(hass, entity_id):
    global G_INPUT_CURRENT_HOUR
    global G_INPUT_CURRENT_MINNUTE
    if G_INPUT_CURRENT_HOUR is None:
        time_attr = hass.states.get(entity_id).attributes
        G_INPUT_CURRENT_HOUR = time_attr.get("hour", 0)
        G_INPUT_CURRENT_MINNUTE = time_attr.get("minute", 0)
    if G_INPUT_CURRENT_HOUR == 23:
        G_INPUT_CURRENT_HOUR = 0
    else:
        G_INPUT_CURRENT_HOUR = G_INPUT_CURRENT_HOUR + 1
    _say_it(hass, get_hour_to_say(G_INPUT_CURRENT_HOUR, G_INPUT_CURRENT_MINNUTE))


def set_time_hour_down(hass, entity_id):
    global G_INPUT_CURRENT_HOUR
    global G_INPUT_CURRENT_MINNUTE
    if G_INPUT_CURRENT_HOUR is None:
        time_attr = hass.states.get(entity_id).attributes
        G_INPUT_CURRENT_HOUR = time_attr.get("hour", 0)
        G_INPUT_CURRENT_MINNUTE = time_attr.get("minute", 0)
    if G_INPUT_CURRENT_HOUR == 0:
        G_INPUT_CURRENT_HOUR = 23
    else:
        G_INPUT_CURRENT_HOUR = G_INPUT_CURRENT_HOUR - 1
    _say_it(hass, get_hour_to_say(G_INPUT_CURRENT_HOUR, G_INPUT_CURRENT_MINNUTE))


def set_time_minute_up(hass, entity_id):
    global G_INPUT_CURRENT_HOUR
    global G_INPUT_CURRENT_MINNUTE
    if G_INPUT_CURRENT_HOUR is None:
        time_attr = hass.states.get(entity_id).attributes
        G_INPUT_CURRENT_HOUR = time_attr.get("hour", 0)
        G_INPUT_CURRENT_MINNUTE = time_attr.get("minute", 0)
    if G_INPUT_CURRENT_MINNUTE == 59:
        G_INPUT_CURRENT_MINNUTE = 0
    else:
        G_INPUT_CURRENT_MINNUTE = G_INPUT_CURRENT_MINNUTE + 1
    _say_it(hass, get_hour_to_say(G_INPUT_CURRENT_HOUR, G_INPUT_CURRENT_MINNUTE))


def set_time_minute_down(hass, entity_id):
    global G_INPUT_CURRENT_HOUR
    global G_INPUT_CURRENT_MINNUTE
    if G_INPUT_CURRENT_HOUR is None:
        time_attr = hass.states.get(entity_id).attributes
        G_INPUT_CURRENT_HOUR = time_attr.get("hour", 0)
        G_INPUT_CURRENT_MINNUTE = time_attr.get("minute", 0)
    if G_INPUT_CURRENT_MINNUTE == 0:
        G_INPUT_CURRENT_MINNUTE = 59
    else:
        G_INPUT_CURRENT_MINNUTE = G_INPUT_CURRENT_MINNUTE - 1
    _say_it(hass, get_hour_to_say(G_INPUT_CURRENT_HOUR, G_INPUT_CURRENT_MINNUTE))


def remove_selected_action(key_code):
    global CURR_ENTITIE_SELECTED_ACTION
    if key_code not in (19, 20, 21, 22, 23):
        CURR_ENTITIE_SELECTED_ACTION = None
        return

    if (
            CURR_ENTITIE_SELECTED_ACTION == ais_global.G_ACTION_SET_AUDIO_SHUFFLE
            and key_code not in (19, 20, 23)
    ):
        CURR_ENTITIE_SELECTED_ACTION = None
        return


# Groups in Groups views
def get_curr_group():
    global CURR_GROUP
    if CURR_GROUP is None:
        # take the first one from Group view
        for group in GROUP_ENTITIES:
            if group["remote_group_view"] == get_curr_group_view():
                CURR_GROUP = group
                break
    return CURR_GROUP


def get_group_from_group(entity_id):
    global CURR_GROUP
    for group in GROUP_ENTITIES:
        if group["entity_id"] == entity_id:
            CURR_GROUP = group
            break
    return CURR_GROUP


def get_curr_group_idx():
    idx = 0
    for group in GROUP_ENTITIES:
        if group["entity_id"] == get_curr_group()["entity_id"]:
            return idx
        idx += 1
    return idx


def say_curr_group(hass):
    _say_it(hass, get_curr_group()["friendly_name"])


def set_bookmarks_curr_group(hass):
    for idx, g in enumerate(GROUP_ENTITIES, start=0):
        if g["entity_id"] == "group.ais_bookmarks":
            set_curr_group(hass, g)
            return


def set_favorites_curr_group(hass):
    for idx, g in enumerate(GROUP_ENTITIES, start=0):
        if g["entity_id"] == "group.ais_favorites":
            set_curr_group(hass, g)
            return


def set_curr_group(hass, group):
    # set focus on current menu group view
    global CURR_GROUP_VIEW
    global CURR_GROUP
    global CURR_ENTITIE
    global CURR_ENTITIE_ENTERED
    global CURR_ENTITIE_POSITION
    # the entitie can be selected or focused
    CURR_ENTITIE = None
    CURR_ENTITIE_ENTERED = False
    CURR_ENTITIE_POSITION = None
    if group is None:
        CURR_GROUP = get_curr_group()
        hass.states.async_set("binary_sensor.selected_entity", CURR_GROUP["entity_id"])
    else:
        CURR_GROUP_VIEW = group["remote_group_view"]
        CURR_GROUP = group
    # set display context for mega audio player
    if CURR_GROUP["entity_id"] in (
            "group.radio_player",
            "group.podcast_player",
            "group.music_player",
            "group.ais_bookmarks",
            "group.ais_rss_news_remote",
            "group.local_audio",
            "sensor.ais_drives",
            "group.ais_favorites",
            "group.audiobooks_player",
    ):
        hass.states.async_set(
            "sensor.ais_player_mode", CURR_GROUP["entity_id"].replace("group.", "")
        )


def set_next_group(hass):
    # set focus on next group in focused view
    global CURR_GROUP
    first_group_in_view = None
    curr_group_in_view = None
    next_group_in_view = None
    for group in GROUP_ENTITIES:
        if group["remote_group_view"] == get_curr_group_view():
            # select the first group
            if curr_group_in_view is not None and next_group_in_view is None:
                next_group_in_view = group
            if first_group_in_view is None:
                first_group_in_view = group
            if CURR_GROUP["entity_id"] == group["entity_id"]:
                curr_group_in_view = group

    if next_group_in_view is not None:
        CURR_GROUP = next_group_in_view
    else:
        CURR_GROUP = first_group_in_view
    # to reset
    set_curr_group(hass, CURR_GROUP)


def set_prev_group(hass):
    # set focus on prev group in focused view
    global CURR_GROUP
    last_group_in_view = None
    curr_group_in_view = None
    prev_group_in_view = None
    for group in GROUP_ENTITIES:
        if group["remote_group_view"] == get_curr_group_view():
            # select the last group
            last_group_in_view = group
            if CURR_GROUP["entity_id"] == group["entity_id"]:
                curr_group_in_view = group
            if curr_group_in_view is None:
                prev_group_in_view = group
    if prev_group_in_view is not None:
        CURR_GROUP = prev_group_in_view
    else:
        CURR_GROUP = last_group_in_view
    # to reset
    set_curr_group(hass, CURR_GROUP)


# entity in group
def get_curr_entity():
    global CURR_ENTITIE
    if CURR_ENTITIE is None:
        if len(GROUP_ENTITIES[get_curr_group_idx()]["entities"]) > 0:
            CURR_ENTITIE = GROUP_ENTITIES[get_curr_group_idx()]["entities"][0]
    return CURR_ENTITIE


def get_curr_entity_idx():
    idx = 0
    for item in GROUP_ENTITIES[get_curr_group_idx()]["entities"]:
        if item == get_curr_entity():
            return idx
        idx += 1


def set_curr_entity(hass, entity):
    # set focus on current entity
    global CURR_ENTITIE
    global CURR_ENTITIE_POSITION
    if entity is None:
        CURR_ENTITIE = get_curr_entity()
    else:
        CURR_ENTITIE = entity
    CURR_ENTITIE_POSITION = None
    hass.states.async_set("binary_sensor.selected_entity", CURR_ENTITIE)


def set_next_entity(hass):
    # set next entity
    global CURR_ENTITIE
    # special case for music
    if CURR_ENTITIE == "input_select.ais_music_service":
        state = hass.states.get("input_select.ais_music_service")
        if state.state == "Spotify":
            CURR_ENTITIE = "input_text.ais_spotify_query"
        else:
            CURR_ENTITIE = "input_text.ais_music_query"
    elif CURR_ENTITIE == "input_text.ais_music_query":
        CURR_ENTITIE = "sensor.youtubelist"
    elif CURR_ENTITIE == "input_text.ais_spotify_query":
        CURR_ENTITIE = "sensor.spotifysearchlist"
    elif CURR_ENTITIE == "sensor.youtubelist":
        CURR_ENTITIE = "input_select.ais_music_service"
    elif CURR_ENTITIE == "sensor.spotifysearchlist":
        CURR_ENTITIE = "sensor.spotifylist"
    elif CURR_ENTITIE == "sensor.spotifylist":
        CURR_ENTITIE = "input_select.ais_music_service"
    else:
        entity_idx = get_curr_entity_idx()
        group_idx = get_curr_group_idx()
        l_group_len = len(GROUP_ENTITIES[group_idx]["entities"])
        if entity_idx + 1 == l_group_len:
            entity_idx = 0
        else:
            entity_idx = entity_idx + 1
        CURR_ENTITIE = GROUP_ENTITIES[group_idx]["entities"][entity_idx]
    # to reset variables
    set_curr_entity(hass, None)
    say_curr_entity(hass)


def set_prev_entity(hass):
    # set prev entity
    global CURR_ENTITIE
    # special case for music
    if CURR_ENTITIE == "input_select.ais_music_service":
        state = hass.states.get("input_select.ais_music_service")
        if state.state == "Spotify":
            CURR_ENTITIE = "sensor.spotifylist"
        else:
            CURR_ENTITIE = "sensor.youtubelist"
    elif CURR_ENTITIE == "sensor.youtubelist":
        CURR_ENTITIE = "input_text.ais_music_query"
    elif CURR_ENTITIE == "input_text.ais_music_query":
        CURR_ENTITIE = "input_select.ais_music_service"
    elif CURR_ENTITIE == "sensor.spotifylist":
        CURR_ENTITIE = "sensor.spotifysearchlist"
    elif CURR_ENTITIE == "sensor.spotifysearchlist":
        CURR_ENTITIE = "input_text.ais_spotify_query"
    elif CURR_ENTITIE == "input_text.ais_spotify_query":
        CURR_ENTITIE = "input_select.ais_music_service"

    # end special case for music
    else:
        idx = get_curr_entity_idx()
        l_group_len = len(GROUP_ENTITIES[get_curr_group_idx()]["entities"])
        if idx == 0:
            idx = l_group_len - 1
        else:
            idx = idx - 1
        CURR_ENTITIE = GROUP_ENTITIES[get_curr_group_idx()]["entities"][idx]
    # to reset variables
    set_curr_entity(hass, None)
    say_curr_entity(hass)


def say_curr_entity(hass):
    # check if we have selected item
    entity_id = get_curr_entity()
    if entity_id is None:
        if CURR_GROUP["entity_id"] == "group.all_ais_persons":
            _say_it(
                hass,
                "Brak informacji o osobach. W konfiguracji możesz dodać osoby, "
                "oraz urządzenia raportujące lokalizację osób.",
            )
        elif CURR_GROUP["entity_id"] == "group.all_automations":
            _say_it(
                hass,
                "Brak zdefiniowanych automatyzacji. Dodaj automatyzację w konfiguracji.",
            )
        else:
            _say_it(hass, "Brak pozycji")
        return
    state = hass.states.get(entity_id)
    if state is None:
        _say_it(hass, "Brak pozycji")
        return
    text = state.attributes.get("text")
    info_name = state.attributes.get("friendly_name")
    info_data = state.state
    info_unit = state.attributes.get("unit_of_measurement")
    if not text:
        text = ""
    # handle special cases...
    if entity_id == "sensor.aisknowledgeanswer":
        _say_it(hass, "Odpowiedź: " + text)
        return
    elif entity_id == "sensor.ais_drives":
        state = hass.states.get("sensor.ais_drives")
        if state.state is None or state.state == "":
            _say_it(hass, "dysk wewnętrzny")
        else:
            attr = state.attributes
            files = attr.get("files", [])
            info = ais_drives_service.get_pozycji_variety(len(files))
            _say_it(hass, info)
        return
    elif entity_id == "sensor.ais_secure_android_id_dom":
        _say_it(
            hass, info_name + " " + info_data + ". Aby przeliterować naciśnij 'OK'."
        )
        return
    elif entity_id == "sensor.ais_connect_iot_device_info":
        info = (
            "Instrukcja. Podłącz urządzenie do prądu. Upewnij się, że urządzenie znajduje się w zasięgu routera "
            "WiFi oraz bramki AIS dom. "
            "Uruchom tryb parowania, naciskając 4 razy szybko przycisk na urządzeniu, "
            "następnie poczekaj aż dioda na urządzeniu, zacznie pulsować. Gdy urządzenie jest w trybie parowania, "
            "to naciśnij OK na pilocie, aby rozpocząć wyszukiwanie urządzenia."
        )
        _say_it(hass, info)
        return
    elif entity_id == "input_boolean.ais_quiet_mode":
        state = hass.states.get("input_boolean.ais_quiet_mode").state
        info_value = " wyłączony. Naciśnij OK by włączyć. "
        if state == "on":
            info_value = " włączony. Naciśnij OK by wyłączyć. "
        _say_it(
            hass,
            info_name
            + info_value
            + " Gdy tryb nocny jest włączony to asystent w wybranych godzinach "
              "automatycznie zredukuje głośność odtwarzania audio.",
        )
        return
    elif entity_id == "input_boolean.ais_auto_update":
        state = hass.states.get("input_boolean.ais_auto_update").state
        info_value = (
            "Automatyczne aktualizacje wyłączone. Aktualizujesz system samodzielnie w "
            "dogodnym dla Ciebie czasie. Naciśnij OK by włączyć aktualizacje automatyczne."
        )
        if state == "on":
            info_value = (
                "Automatyczne aktualizacje włączone. Codziennie sprawdzimy i automatycznie "
                "zainstalujemy dostępne aktualizacje składowych systemu. "
                "Naciśnij OK by wyłączyć aktualizacje automatyczne. "
            )
        _say_it(hass, info_value)
        return
    elif entity_id == "input_select.ais_bookmark_last_played":
        _say_it(hass, info_name + " " + info_data.replace("Local;", ""))
        return
    elif entity_id == "sensor.ais_wifi_service_current_network_info":
        state = hass.states.get("sensor.ais_wifi_service_current_network_info")
        attr = state.attributes
        info = attr.get("description", "brak informacji o połączeniu")
        _say_it(hass, "Prędkość połączenia " + info)
        return
    elif entity_id.startswith("script."):
        _say_it(hass, info_name + " Naciśnij OK by uruchomić.")
        return
    elif entity_id.startswith("automation."):
        _say_it(hass, info_name + " Naciśnij OK by uruchomić.")
        return
    elif entity_id.startswith("input_datetime."):
        state = hass.states.get(entity_id)
        attr = state.attributes
        info_name = info_name + "; "
        info_time = get_hour_to_say(attr.get("hour", "00"), attr.get("minute", 0))
        _say_it(hass, info_name + info_time + ". Naciśnij OK by zmienić godzinę.")
        return
    elif entity_id.startswith("input_text."):
        if CURR_BUTTON_CODE == 4:
            if CURR_VIRTUAL_KEYBOARD_VALUE is None:
                _say_it(hass, "Nic nie wpisałeś")
            else:
                _say_it(hass, "Wpisałeś " + CURR_VIRTUAL_KEYBOARD_VALUE)
        else:
            _say_it(
                hass,
                info_name
                + " "
                + info_data
                + ". Naciśnij OK aby wpisać lub dyktować tekst",
            )
        return
    elif entity_id.startswith("input_select."):
        if CURR_BUTTON_CODE == 4:
            if info_data == ais_global.G_EMPTY_OPTION:
                _say_it(hass, "Brak wyboru")
            else:
                _say_it(hass, "Wybrałeś " + info_data)
        else:
            if info_data != ais_global.G_EMPTY_OPTION:
                _say_it(hass, info_name + " " + info_data + ". Naciśnij OK by zmienić.")
            else:
                _say_it(hass, info_name + " " + info_data + ". Naciśnij OK by wybrać.")
        return
    elif entity_id.startswith("sensor.") and entity_id.endswith("list"):
        info_name = ""
        if int(info_data) != -1:
            try:
                info_name = hass.states.get(entity_id).attributes.get(int(info_data))[
                    "title"
                ]
            except Exception:
                info_name = ""
        if CURR_BUTTON_CODE == 4:
            if int(info_data) == -1:
                _say_it(hass, "Brak wybranej pozycji ")
            else:
                _say_it(hass, "Lista na pozycji " + info_name)
        else:
            if entity_id == "sensor.radiolist":
                info = "Lista stacji radiowych "
            elif entity_id == "sensor.podcastlist":
                info = "Lista odcinków "
            elif entity_id == "sensor.spotifylist":
                info = "Lista utworów ze Spotify "
            elif entity_id == "sensor.youtubelist":
                info = "Lista utworów z YouTube "
            elif entity_id == "sensor.rssnewslist":
                info = "Lista artykułów "
            elif entity_id == "sensor.aisbookmarkslist":
                info = "Lista zakładek "
            elif entity_id == "sensor.aisfavoriteslist":
                info = "Lista ulubionych "
            elif entity_id == "sensor.podcastnamelist":
                info = "Lista audycji  "
            elif entity_id == "sensor.aisfavoriteslist":
                info = "Lista ulubionych pozycji  "
            elif entity_id == "sensor.aisbookmarkslist":
                info = "Lista zakładek  "
            elif entity_id == "sensor.audiobookslist":
                info = "Lista książek  "
            elif entity_id == "sensor.audiobookschapterslist":
                info = "Lista rozdziałów  "
            else:
                info = "Pozycja "

            if CURR_ENTITIE_ENTERED:
                additional_info = ". Wybierz pozycję."
            elif int(info_data) != -1:
                additional_info = ". Naciśnij OK by zmienić."
            else:
                additional_info = ". Naciśnij OK by wybrać."

            _say_it(hass, info + info_name + additional_info)

        return
    # normal case
    # decode None
    if not info_name:
        info_name = ""
    info_data = translate_state(state)
    if not info_unit:
        info_unit = ""
    info = f"{info_name} {info_data} {info_unit}"
    _say_it(hass, info)


def get_curent_position(hass):
    # return the entity focused position
    global CURR_ENTITIE_POSITION
    if CURR_ENTITIE_POSITION is None:
        CURR_ENTITIE_POSITION = hass.states.get(CURR_ENTITIE).state
    return CURR_ENTITIE_POSITION


def commit_current_position(hass):
    global CURR_ENTITIE_ENTERED
    if CURR_ENTITIE.startswith("input_select."):
        # force the change - to trigger the state change for automation
        position = get_curent_position(hass)
        state = hass.states.get(CURR_ENTITIE).state
        if position == state:
            if CURR_ENTITIE == "input_select.radio_type":
                hass.services.call(
                    "ais_cloud", "get_radio_names", {"radio_type": state}
                )
                return
            elif CURR_ENTITIE == "input_select.rss_news_category":
                hass.services.call(
                    "ais_cloud", "get_rss_news_channels", {"rss_news_category": state}
                )
                return
            elif CURR_ENTITIE == "input_select.rss_news_channel":
                hass.services.call(
                    "ais_cloud", "get_rss_news_items", {"rss_news_channel": state}
                )
                return
            elif CURR_ENTITIE == "input_select.podcast_type":
                hass.services.call(
                    "ais_cloud", "get_podcast_names", {"podcast_type": state}
                )
                return
        hass.services.call(
            "input_select",
            "select_option",
            {"entity_id": CURR_ENTITIE, "option": position},
        )
    elif CURR_ENTITIE.startswith("input_number."):
        hass.services.call(
            "input_number",
            "set_value",
            {"entity_id": CURR_ENTITIE, "value": get_curent_position(hass)},
        )
    elif CURR_ENTITIE.startswith("input_datetime."):
        hass.services.call(
            "input_datetime",
            "set_datetime",
            {
                "entity_id": CURR_ENTITIE,
                "time": str(G_INPUT_CURRENT_HOUR) + ":" + str(G_INPUT_CURRENT_MINNUTE),
            },
        )
        text = get_hour_to_say(G_INPUT_CURRENT_HOUR, G_INPUT_CURRENT_MINNUTE)
        _say_it(hass, "wpisana " + text)
        CURR_ENTITIE_ENTERED = False
    elif CURR_ENTITIE.startswith("sensor.") and CURR_ENTITIE.endswith("list"):
        # play/read selected source
        idx = hass.states.get(CURR_ENTITIE).state
        if CURR_ENTITIE == "sensor.radiolist":
            hass.services.call(
                "ais_cloud",
                "play_audio",
                {"id": idx, "media_source": ais_global.G_AN_RADIO},
            )
        elif CURR_ENTITIE == "sensor.":
            hass.services.call(
                "ais_cloud",
                "play_audio",
                {"id": idx, "media_source": ais_global.G_AN_PODCAST},
            )
        elif CURR_ENTITIE == "sensor.spotifysearchlist":
            hass.services.call(
                "ais_cloud",
                "play_audio",
                {"id": idx, "media_source": ais_global.G_AN_SPOTIFY_SEARCH},
            )
        elif CURR_ENTITIE == "sensor.spotifylist":
            hass.services.call(
                "ais_cloud",
                "play_audio",
                {"id": idx, "media_source": ais_global.G_AN_SPOTIFY},
            )
        elif CURR_ENTITIE == "sensor.youtubelist":
            hass.services.call(
                "ais_cloud",
                "play_audio",
                {"id": idx, "media_source": ais_global.G_AN_MUSIC},
            )
        elif CURR_ENTITIE == "sensor.rssnewslist":
            hass.services.call(
                "ais_cloud",
                "play_audio",
                {"id": idx, "media_source": ais_global.G_AN_NEWS},
            )
        elif CURR_ENTITIE == "sensor.audiobookslist":
            hass.services.call(
                "ais_cloud",
                "play_audio",
                {"id": idx, "media_source": ais_global.G_AN_AUDIOBOOK},
            )
        elif CURR_ENTITIE == "sensor.audiobookschapterslist":
            hass.services.call(
                "ais_cloud",
                "play_audio",
                {"id": idx, "media_source": ais_global.G_AN_AUDIOBOOK_CHAPTER},
            )
        elif CURR_ENTITIE == "sensor.aisbookmarkslist":
            hass.services.call(
                "ais_cloud",
                "play_audio",
                {"id": idx, "media_source": ais_global.G_AN_BOOKMARK},
            )
        elif CURR_ENTITIE == "sensor.aisfavoriteslist":
            hass.services.call(
                "ais_cloud",
                "play_audio",
                {"id": idx, "media_source": ais_global.G_AN_FAVORITE},
            )
        elif CURR_ENTITIE == "sensor.podcastnamelist":
            hass.services.call(
                "ais_cloud",
                "play_audio",
                {"id": idx, "media_source": ais_global.G_AN_PODCAST_NAME},
            )

    if CURR_ENTITIE == "input_select.ais_android_wifi_network":
        _say_it(hass, "wybrano wifi: " + get_curent_position(hass).split(";")[0])

    elif CURR_ENTITIE == "input_select.ais_music_service":
        _say_it(
            hass,
            "Wybrano " + position + ", napisz lub powiedz jakiej muzyki mam wyszukać",
        )
        state = hass.states.get(CURR_ENTITIE)
        if state.state == "YouTube":
            input = "input_text.ais_music_query"
        elif state.state == "Spotify":
            input = "input_text.ais_spotify_query"
        hass.services.call("input_text", "set_value", {"entity_id": input, "value": ""})
        reset_virtual_keyboard(hass)
        set_curr_entity(hass, input)
    else:
        _beep_it(hass, 33)
    # TODO - run the script for the item,
    # the automation on state should be executed only from app not from remote


def set_next_position(hass):
    global CURR_ENTITIE_POSITION
    CURR_ENTITIE_POSITION = get_curent_position(hass)
    state = hass.states.get(CURR_ENTITIE)
    attr = state.attributes
    if CURR_ENTITIE.startswith("input_select."):
        # the "-" option is always first
        options = attr.get("options")
        if len(options) < 2:
            _say_it(hass, "brak pozycji")
        else:
            CURR_ENTITIE_POSITION = get_next(options, CURR_ENTITIE_POSITION)
            _say_it(hass, CURR_ENTITIE_POSITION)
    elif CURR_ENTITIE.startswith("sensor.") and CURR_ENTITIE.endswith("list"):
        if len(attr) == 0:
            _say_it(hass, "brak pozycji")
        else:
            curr_id = int(state.state)
            next_id = int(curr_id) + 1
            if next_id == len(attr):
                next_id = 0
            track = attr.get(int(next_id))
            _say_it(hass, track["name"])
            # update list
            hass.states.async_set(CURR_ENTITIE, next_id, attr)
    elif CURR_ENTITIE.startswith("input_number."):
        _max = float(state.attributes.get("max"))
        _step = float(state.attributes.get("step"))
        _curr = float(CURR_ENTITIE_POSITION)
        CURR_ENTITIE_POSITION = str(round(min(_curr + _step, _max), 2))
        _say_it(hass, str(CURR_ENTITIE_POSITION))


def set_prev_position(hass):
    global CURR_ENTITIE_POSITION
    CURR_ENTITIE_POSITION = get_curent_position(hass)
    state = hass.states.get(CURR_ENTITIE)
    attr = state.attributes
    if CURR_ENTITIE.startswith("input_select."):
        options = attr.get("options")
        if len(options) < 2:
            _say_it(hass, "brak pozycji")
        else:
            CURR_ENTITIE_POSITION = get_prev(options, CURR_ENTITIE_POSITION)
            _say_it(hass, CURR_ENTITIE_POSITION)
    elif CURR_ENTITIE.startswith("sensor.") and CURR_ENTITIE.endswith("list"):
        if len(attr) == 0:
            _say_it(hass, "brak pozycji")
        else:
            curr_id = int(state.state)
            prev_id = curr_id - 1
            if prev_id < 0:
                prev_id = len(attr) - 1
            track = attr.get(int(prev_id))
            _say_it(hass, track["name"])
            # update list
            hass.states.async_set(CURR_ENTITIE, prev_id, attr)
    elif CURR_ENTITIE.startswith("input_number."):
        _min = float(state.attributes.get("min"))
        _step = float(state.attributes.get("step"))
        _curr = float(CURR_ENTITIE_POSITION)
        CURR_ENTITIE_POSITION = str(round(max(_curr - _step, _min), 2))
        _say_it(hass, str(CURR_ENTITIE_POSITION))


def select_entity(hass, long_press):
    global CURR_ENTITIE_SELECTED_ACTION
    global G_INPUT_CURRENT_MINNUTE
    global G_INPUT_CURRENT_HOUR
    # on remote OK, select group view, group or entity
    global CURR_ENTITIE_ENTERED
    # OK on remote
    if CURR_GROUP_VIEW is None:
        # no group view was selected
        get_groups(hass)
        set_curr_group_view()
        say_curr_group_view(hass)
        return
    if CURR_GROUP is None:
        # no group is selected - we need to select the first one
        # from the group view
        set_curr_group(hass, None)
        say_curr_group(hass)
        return
    # group in group
    if CURR_GROUP["entity_id"] == "group.all_ais_devices":
        get_groups(hass)
        gg = CURR_GROUP["entities"]
        set_curr_group(hass, get_group_from_group(gg[0]))
        say_curr_group(hass)
        return
    if CURR_ENTITIE is None:
        # no entity is selected - we need to focus the first one
        set_curr_entity(hass, None)
        say_curr_entity(hass)
        CURR_ENTITIE_ENTERED = False
        return

    if CURR_ENTITIE == "sensor.ais_drives":
        if CURR_ENTITIE_SELECTED_ACTION == ais_global.G_ACTION_DELETE:
            hass.async_run_job(
                hass.services.call("ais_drives_service", "remote_delete_item")
            )
            CURR_ENTITIE_SELECTED_ACTION = None
            return
        else:
            hass.services.call("ais_drives_service", "remote_select_item")
            return
    elif CURR_ENTITIE.startswith("media_player."):
        if CURR_ENTITIE_SELECTED_ACTION == ais_global.G_ACTION_SET_AUDIO_SHUFFLE:
            state = hass.states.get("media_player.wbudowany_glosnik")
            shuffle = state.attributes.get("shuffle", False)
            if shuffle:
                _say_it(hass, "Włączono odtwarzanie w kolejności.")
                hass.services.call(
                    "media_player",
                    "shuffle_set",
                    {"entity_id": CURR_ENTITIE, "shuffle": False},
                )
            else:
                _say_it(hass, "Włączono odtwarzanie losowe.")
                hass.services.call(
                    "media_player",
                    "shuffle_set",
                    {"entity_id": CURR_ENTITIE, "shuffle": True},
                )
            return

    if CURR_ENTITIE_ENTERED is False:
        # check if the entity option can be selected
        if can_entity_be_changed(hass, CURR_ENTITIE):
            if can_entity_be_entered(hass, CURR_ENTITIE):
                CURR_ENTITIE_ENTERED = True
                if CURR_ENTITIE.startswith("input_text."):
                    _say_it(hass, "Wpisywanie/dyktowanie tekstu włączone")
                    reset_virtual_keyboard(hass)
                elif CURR_ENTITIE.startswith("input_datetime."):
                    G_INPUT_CURRENT_MINNUTE = None
                    G_INPUT_CURRENT_HOUR = None
                    _say_it(
                        hass,
                        "OK, dostosuj godzinę strzałkami góra lub dół a minuty strzałkami lewo lub prawo."
                        " By zatwierdzić naciśnij 'OK'.",
                    )
                else:
                    set_next_position(hass)
                return
            else:
                # we will change this item directly
                if CURR_ENTITIE.startswith("media_player."):
                    # enter to media player
                    CURR_ENTITIE_ENTERED = True
                    # play / pause on selected player
                    curr_state = hass.states.get(CURR_ENTITIE).state
                    if curr_state == "playing":
                        if long_press is True:
                            _say_it(hass, "stop")
                            hass.services.call(
                                "media_player",
                                "media_stop",
                                {"entity_id": CURR_ENTITIE},
                            )
                        else:
                            _say_it(hass, "pauza")
                            hass.services.call(
                                "media_player",
                                "media_pause",
                                {"entity_id": CURR_ENTITIE},
                            )
                    else:
                        _say_it(hass, "graj")
                        hass.services.call(
                            "media_player", "media_play", {"entity_id": CURR_ENTITIE}
                        )
                elif CURR_ENTITIE.startswith("input_boolean."):
                    curr_state = hass.states.get(CURR_ENTITIE).state
                    if curr_state == "on":
                        _say_it(hass, "ok, wyłączam")
                    if curr_state == "off":
                        _say_it(hass, "ok, włączam")
                    hass.services.call(
                        "input_boolean", "toggle", {"entity_id": CURR_ENTITIE}
                    )
                elif CURR_ENTITIE.startswith("switch."):
                    curr_state = hass.states.get(CURR_ENTITIE).state
                    if curr_state == "on":
                        _say_it(hass, "ok, wyłączam")
                    if curr_state == "off":
                        _say_it(hass, "ok, włączam")
                    if curr_state == "unavailable":
                        _say_it(hass, "przełącznik jest niedostępny")
                    hass.services.call("switch", "toggle", {"entity_id": CURR_ENTITIE})
                elif CURR_ENTITIE.startswith("light."):
                    curr_state = hass.states.get(CURR_ENTITIE).state
                    if curr_state == "on":
                        _say_it(hass, "ok, wyłączam")
                    elif curr_state == "off":
                        _say_it(hass, "ok, włączam")
                    elif curr_state == "unavailable":
                        _say_it(hass, "oświetlnie jest niedostępne")
                    hass.services.call("light", "toggle", {"entity_id": CURR_ENTITIE})
                elif CURR_ENTITIE.startswith("script."):
                    hass.services.call("script", CURR_ENTITIE.split(".")[1])
                elif CURR_ENTITIE.startswith("automation."):
                    _say_it(hass, "ok, uruchamiam")
                    hass.services.call(
                        "automation", "trigger", {"entity_id": CURR_ENTITIE}
                    )
        else:
            # do some special staff for some entries
            if CURR_ENTITIE == "sensor.version_info":
                # get the info about upgrade
                state = hass.states.get(CURR_ENTITIE)
                reinstall_dom_app = state.attributes.get("reinstall_dom_app", False)
                reinstall_android_app = state.attributes.get(
                    "reinstall_android_app", False
                )
                reinstall_linux_apt = state.attributes.get("reinstall_linux_apt", False)
                if (
                        reinstall_dom_app is False
                        and reinstall_android_app is False
                        and reinstall_linux_apt is False
                ):
                    _say_it(hass, "Twoja wersja jest aktualna")
                else:
                    _say_it(
                        hass,
                        "Poczekaj na zakończenie aktualizacji i restart. Do usłyszenia.",
                    )
                    hass.services.call("ais_updater", "execute_upgrade")

            elif CURR_ENTITIE == "sensor.ais_secure_android_id_dom":
                # spelling
                state = hass.states.get("sensor.ais_secure_android_id_dom")
                dom_id = state.state.replace("dom-", "")
                dom_id = "; ".join(dom_id)
                _say_it(hass, dom_id)
                return
            elif CURR_ENTITIE == "sensor.ais_connect_iot_device_info":
                # start searching for the device
                hass.services.call("script", "ais_scan_iot_devices_in_network")
                return
            else:
                _say_it(hass, "Tej pozycji nie można zmieniać")

    if CURR_ENTITIE_ENTERED is True:
        # check if we can change this item
        if can_entity_be_changed(hass, CURR_ENTITIE):
            # these items can be controlled from remote
            # if we are here it means that the enter on the same item was
            # pressed twice, we should do something - to mange the item status
            if CURR_ENTITIE.startswith(("input_select.", "input_number.")):
                commit_current_position(hass)
            elif CURR_ENTITIE.startswith("sensor.") and CURR_ENTITIE.endswith("list"):
                if CURR_ENTITIE_SELECTED_ACTION == ais_global.G_ACTION_DELETE:
                    # delete
                    if CURR_ENTITIE == "sensor.aisfavoriteslist":
                        item_idx = hass.states.get("sensor.aisfavoriteslist").state
                        _say_it(hass, "OK usuwam tą pozycję z ulubionych.")
                        hass.async_run_job(
                            hass.services.call(
                                "ais_bookmarks", "delete_favorite", {"id": item_idx}
                            )
                        )
                    elif CURR_ENTITIE == "sensor.aisbookmarkslist":
                        item_idx = hass.states.get("sensor.aisbookmarkslist").state
                        hass.async_run_job(
                            hass.services.call(
                                "ais_bookmarks", "delete_bookmark", {"id": item_idx}
                            )
                        )
                        _say_it(hass, "OK. Usuwam tą zakładkę.")
                    # reset action
                    CURR_ENTITIE_SELECTED_ACTION = None
                    return
                #
                commit_current_position(hass)
            elif CURR_ENTITIE.startswith("media_player."):
                # play / pause on selected player
                curr_state = hass.states.get(CURR_ENTITIE).state
                if curr_state == "playing":
                    if long_press is True:
                        _say_it(hass, "stop")
                        hass.services.call(
                            "media_player", "media_stop", {"entity_id": CURR_ENTITIE}
                        )
                    else:
                        _say_it(hass, "pauza")
                        hass.services.call(
                            "media_player", "media_pause", {"entity_id": CURR_ENTITIE}
                        )
                else:
                    _say_it(hass, "graj")
                    hass.services.call(
                        "media_player", "media_play", {"entity_id": CURR_ENTITIE}
                    )
            elif CURR_ENTITIE.startswith("input_text."):
                type_to_input_text_from_virtual_keyboard(hass)
            elif CURR_ENTITIE.startswith("input_datetime."):
                commit_current_position(hass)
        else:
            # eneter on unchanged item
            _say_it(hass, "Tej pozycji nie można zmieniać")


def can_entity_be_changed(hass, entity):
    # check if entity can be changed
    if CURR_ENTITIE.startswith(
            (
                    "media_player.",
                    "input_boolean.",
                    "switch.",
                    "script.",
                    "light.",
                    "input_text.",
                    "input_select.",
                    "input_number.",
                    "automation.",
                    "input_datetime.",
            )
    ):
        return True
    elif CURR_ENTITIE.startswith("sensor.") and CURR_ENTITIE.endswith("list"):
        return True
    else:
        return False


def can_entity_be_entered(hass, entity):
    # check if entity can be entered
    if CURR_ENTITIE.startswith(
            (
                    "media_player.",
                    "input_boolean.",
                    "switch.",
                    "script.",
                    "light.",
                    "automation.",
                    "group.",
            )
    ):
        return False
    else:
        return True


def set_on_dpad_down(hass, long_press):
    global CURR_ENTITIE_SELECTED_ACTION
    if CURR_ENTITIE is not None:
        if CURR_ENTITIE.startswith("media_player."):
            if (
                    CURR_ENTITIE_SELECTED_ACTION is None
                    or CURR_ENTITIE_SELECTED_ACTION == ais_global.G_ACTION_SET_AUDIO_SHUFFLE
            ):
                CURR_ENTITIE_SELECTED_ACTION = ais_global.G_ACTION_SET_AUDIO_SPEED
                state = hass.states.get("input_number.media_player_speed")
                l_speed_pl = ais_global.get_audio_speed_name(state.state)
                _say_it(
                    hass,
                    "Prędkość odtwarzania audio "
                    + l_speed_pl
                    + ". Przyśpiesz strzałką w prawo, zwolnij strzałką w lewo.",
                )
            elif CURR_ENTITIE_SELECTED_ACTION == ais_global.G_ACTION_SET_AUDIO_SPEED:
                CURR_ENTITIE_SELECTED_ACTION = ais_global.G_ACTION_SET_AUDIO_SHUFFLE
                state = hass.states.get("media_player.wbudowany_glosnik")
                shuffle = state.attributes.get("shuffle", False)
                if shuffle:
                    _say_it(
                        hass, "Odtwarzanie losowe włączone. Naciśnij OK by wyłączyć."
                    )
                else:
                    _say_it(
                        hass, "Odtwarzanie losowe wyłączone. Naciśnij OK by włączyć."
                    )
            return
        elif CURR_ENTITIE.startswith("input_text.") and CURR_ENTITIE_ENTERED:
            set_prev_virtual_keyboard_mode()
            say_curr_virtual_keyboard_mode(hass)
            return
        elif CURR_ENTITIE.startswith("input_datetime.") and CURR_ENTITIE_ENTERED:
            set_time_hour_down(hass, CURR_ENTITIE)
            return
        elif CURR_ENTITIE_ENTERED and CURR_ENTITIE == "sensor.aisfavoriteslist":
            _say_it(hass, "Usuwanie. Naciśnij OK aby usunąć pozycję z ulubionych.")
            CURR_ENTITIE_SELECTED_ACTION = ais_global.G_ACTION_DELETE
            return
        elif CURR_ENTITIE_ENTERED and CURR_ENTITIE == "sensor.aisbookmarkslist":
            _say_it(hass, "Usuwanie. Naciśnij OK aby usunąć tą zakładkę.")
            CURR_ENTITIE_SELECTED_ACTION = ais_global.G_ACTION_DELETE
            return
        elif CURR_ENTITIE == "sensor.ais_drives":
            path = hass.states.get(CURR_ENTITIE).state
            if path.startswith("/dysk-wewnętrzny"):
                _say_it(hass, "Usuwanie. Naciśnij OK aby usunąć tą pozycję.")
                CURR_ENTITIE_SELECTED_ACTION = ais_global.G_ACTION_DELETE
            else:
                _say_it(hass, "Wybrana pozycja nie ma dodatkowych opcji.")
            return
        else:
            _say_it(hass, "Wybrana pozycja nie ma dodatkowych opcji.")


def set_on_dpad_up(hass, long_press):
    global CURR_ENTITIE_SELECTED_ACTION
    if CURR_ENTITIE is not None:
        if CURR_ENTITIE_SELECTED_ACTION == ais_global.G_ACTION_SET_AUDIO_SHUFFLE:
            CURR_ENTITIE_SELECTED_ACTION = ais_global.G_ACTION_SET_AUDIO_SPEED
            state = hass.states.get("input_number.media_player_speed")
            l_speed_pl = ais_global.get_audio_speed_name(state.state)
            _say_it(
                hass,
                "Prędkość odtwarzania audio "
                + l_speed_pl
                + ". Przyśpiesz strzałką w prawo zwolnij strzałką w lewo.",
            )
            return
        elif CURR_ENTITIE_SELECTED_ACTION == ais_global.G_ACTION_SET_AUDIO_SPEED:
            CURR_ENTITIE_SELECTED_ACTION = None
            _say_it(hass, "Sterowanie odtwarzaczem")
        elif CURR_ENTITIE.startswith("media_player."):
            # info about audio
            state = hass.states.get("media_player.wbudowany_glosnik")
            text = "Odtwarzam " + state.attributes.get("media_title", "")
            audio_type_pl = ais_global.G_NAME_FOR_AUDIO_NATURE.get(
                state.attributes.get("source", ""), state.attributes.get("source", "")
            )
            text += " z " + audio_type_pl
            _say_it(hass, text)
            return
        elif CURR_ENTITIE.startswith("input_text.") and CURR_ENTITIE_ENTERED:
            set_next_virtual_keyboard_mode()
            say_curr_virtual_keyboard_mode(hass)
            return
        elif CURR_ENTITIE.startswith("input_datetime.") and CURR_ENTITIE_ENTERED:
            set_time_hour_up(hass, CURR_ENTITIE)
            return
        else:
            _say_it(hass, "Wybrana pozycja nie ma dodatkowych informacji.")


def set_focus_on_prev_entity(hass, long_press):
    # prev on joystick
    if CURR_ENTITIE is not None:
        if CURR_ENTITIE.startswith("media_player."):
            if long_press:
                # seek back on remote
                hass.services.call(
                    "media_player",
                    "media_seek",
                    {"entity_id": CURR_ENTITIE, "seek_position": 0},
                )
                return
            else:
                if CURR_ENTITIE_SELECTED_ACTION == ais_global.G_ACTION_SET_AUDIO_SPEED:
                    # speed down on remote
                    state = hass.states.get("input_number.media_player_speed")
                    _min = float(state.attributes.get("min"))
                    _step = float(state.attributes.get("step"))
                    _curr = round(max(float(state.state) - _step, _min), 2)
                    hass.services.call(
                        "ais_ai_service",
                        "publish_command_to_frame",
                        {"key": "setPlaybackSpeed", "val": _curr},
                    )
                    hass.services.call(
                        "input_number",
                        "set_value",
                        {
                            "entity_id": "input_number.media_player_speed",
                            "value": _curr,
                        },
                    )
                    _say_it(hass, ais_global.get_audio_speed_name(_curr))
                    return

    # no group is selected go to prev in the groups view menu
    if CURR_GROUP is None:
        set_prev_group_view()
        say_curr_group_view(hass)
        return
    # group is selected
    # check if the entity in the group is selected
    if CURR_ENTITIE is None:
        set_prev_group(hass)
        say_curr_group(hass)
        return
    # entity in the group is selected
    # check if the entity option can be selected
    if can_entity_be_changed(hass, CURR_ENTITIE) and CURR_ENTITIE_ENTERED is True:
        if CURR_ENTITIE.startswith("media_player."):
            hass.services.call(
                "media_player", "media_previous_track", {"entity_id": CURR_ENTITIE}
            )
            return
        elif CURR_ENTITIE.startswith("input_text.") and CURR_ENTITIE_ENTERED:
            set_prev_virtual_key()
            say_curr_virtual_key(hass)
            return
        elif CURR_ENTITIE.startswith("input_datetime.") and CURR_ENTITIE_ENTERED:
            set_time_minute_down(hass, CURR_ENTITIE)
            return
        else:
            set_prev_position(hass)
    else:
        if CURR_ENTITIE.startswith("media_player.") and CURR_ENTITIE_ENTERED:
            hass.services.call(
                "media_player", "media_previous_track", {"entity_id": CURR_ENTITIE}
            )
            return
        elif CURR_ENTITIE == "sensor.ais_drives":
            hass.services.call("ais_drives_service", "remote_prev_item")
            return
        else:
            # entity not selected or no way to change the entity, go to next one
            set_prev_entity(hass)


def set_focus_on_next_entity(hass, long_press):
    # next on joystick
    if CURR_ENTITIE is not None:
        if CURR_ENTITIE.startswith("media_player."):
            if long_press:
                # seek next on remote
                hass.services.call(
                    "media_player",
                    "media_seek",
                    {"entity_id": CURR_ENTITIE, "seek_position": 1},
                )
                return
            else:
                if CURR_ENTITIE_SELECTED_ACTION == ais_global.G_ACTION_SET_AUDIO_SPEED:
                    # speed up on remote
                    state = hass.states.get("input_number.media_player_speed")
                    _max = float(state.attributes.get("max"))
                    _step = float(state.attributes.get("step"))
                    _curr = round(min(float(state.state) + _step, _max), 2)
                    hass.services.call(
                        "input_number",
                        "set_value",
                        {
                            "entity_id": "input_number.media_player_speed",
                            "value": _curr,
                        },
                    )
                    hass.services.call(
                        "ais_ai_service",
                        "publish_command_to_frame",
                        {"key": "setPlaybackSpeed", "val": _curr},
                    )
                    _say_it(hass, ais_global.get_audio_speed_name(_curr))
                    return
    # no group is selected go to next in the groups view menu
    if CURR_GROUP is None:
        set_next_group_view()
        say_curr_group_view(hass)
        return
    # group is selected
    # check if the entity in the group is selected
    if CURR_ENTITIE is None:
        set_next_group(hass)
        say_curr_group(hass)
        return
    # entity in the group is selected
    # check if the entity option can be selected
    if can_entity_be_changed(hass, CURR_ENTITIE) and CURR_ENTITIE_ENTERED is True:
        if CURR_ENTITIE.startswith("media_player."):
            hass.services.call(
                "media_player", "media_next_track", {"entity_id": CURR_ENTITIE}
            )
        elif CURR_ENTITIE.startswith("input_text.") and CURR_ENTITIE_ENTERED:
            set_next_virtual_key()
            say_curr_virtual_key(hass)
        elif CURR_ENTITIE.startswith("input_datetime.") and CURR_ENTITIE_ENTERED:
            set_time_minute_up(hass, CURR_ENTITIE)
            return
        else:
            set_next_position(hass)
    else:
        if CURR_ENTITIE.startswith("media_player.") and CURR_ENTITIE_ENTERED is True:
            hass.services.call(
                "media_player", "media_next_track", {"entity_id": CURR_ENTITIE}
            )
        elif CURR_ENTITIE == "sensor.ais_drives":
            hass.services.call("ais_drives_service", "remote_next_item")
        else:
            # entity not selected or no way to change the entity, go to next one
            set_next_entity(hass)


def go_up_in_menu(hass):
    # on back on remote
    global CURR_ENTITIE_ENTERED, CURR_ENTITIE
    # check if the entity in the group is selected
    if CURR_ENTITIE is not None:
        # check if we are browsing files
        if CURR_ENTITIE == "sensor.ais_drives":
            # check if we can go up
            state = hass.states.get("sensor.ais_drives")
            if state.state is not None and state.state != "":
                hass.services.call("ais_drives_service", "remote_cancel_item")
                return
            else:
                # go up in the group menu
                set_curr_group(hass, None)
                say_curr_group(hass)
        elif CURR_ENTITIE == "media_player.wbudowany_glosnik":
            if PREV_CURR_GROUP is not None:
                # go back to prev context
                set_curr_group(hass, PREV_CURR_GROUP)
                # set_curr_entity(hass, None)
                CURR_ENTITIE = None
                CURR_ENTITIE_ENTERED = False
                PREV_CURR_GROUP["friendly_name"]
                _say_it(hass, PREV_CURR_GROUP["friendly_name"])
            else:
                # go home
                go_home(hass)
        elif not CURR_ENTITIE_ENTERED:
            # go up in the group menu
            # check if we have group in group
            if CURR_GROUP is not None:
                if CURR_GROUP["remote_group_view"].startswith("group."):
                    set_curr_group(hass, CURR_GROUP)
                    say_curr_group(hass)
                    return
                set_curr_group(hass, None)
                say_curr_group(hass)
        else:
            CURR_ENTITIE_ENTERED = False
            if CURR_ENTITIE.startswith("input_text."):
                if CURR_VIRTUAL_KEYBOARD_VALUE is None:
                    hass.services.call(
                        "input_text",
                        "set_value",
                        {"entity_id": CURR_ENTITIE, "value": ""},
                    )
                else:
                    hass.services.call(
                        "input_text",
                        "set_value",
                        {
                            "entity_id": CURR_ENTITIE,
                            "value": CURR_VIRTUAL_KEYBOARD_VALUE,
                        },
                    )
            say_curr_entity(hass)
        return
    # no entity is selected, check if the group is selected
    elif CURR_GROUP is not None:
        # go up in the group view menu
        # check if group in group
        if CURR_GROUP["remote_group_view"].startswith("group."):
            gg = get_group_from_group(CURR_GROUP["remote_group_view"])
            set_curr_group(hass, gg)
            say_curr_group(hass)
            return
        else:
            set_curr_group_view()
            say_curr_group_view(hass)
            return
    # can't go up, beep
    _beep_it(hass, 33)


def type_to_input_text(hass, key):
    if CURR_ENTITIE.startswith("input_text.") and CURR_ENTITIE_ENTERED:
        # add the letter to the virtual input
        global CURR_VIRTUAL_KEYBOARD_VALUE
        if CURR_VIRTUAL_KEYBOARD_VALUE is None:
            CURR_VIRTUAL_KEYBOARD_VALUE = chr(key)
        else:
            CURR_VIRTUAL_KEYBOARD_VALUE = CURR_VIRTUAL_KEYBOARD_VALUE + chr(key)

        _say_it(hass, "wpisano: " + chr(key))


def type_to_input_text_from_virtual_keyboard(hass):
    # add the letter to the virtual input
    global CURR_VIRTUAL_KEYBOARD_VALUE
    if CURR_VIRTUAL_KEYBOARD_VALUE is None:
        CURR_VIRTUAL_KEYBOARD_VALUE = ""
    if CURR_VIRTUAL_KEY is None:
        if get_curr_virtual_keyboard_mode() == "Usuwanie":
            _say_it(hass, "wybierz tryb usuwania")
        else:
            _say_it(hass, "wybierz znak do wpisania")
        return

    key = get_curr_virtual_key()
    km = get_curr_virtual_keyboard_mode()
    if km == "Litery":
        key = key.lower()
    if km == "Usuwanie":
        if key == "ostatni znak":
            text = CURR_VIRTUAL_KEYBOARD_VALUE[:-1]
        elif key == "ostatni wyraz":
            text = CURR_VIRTUAL_KEYBOARD_VALUE.rsplit(" ", 1)[0]
        else:
            text = ""
    else:
        text = CURR_VIRTUAL_KEYBOARD_VALUE + key

    CURR_VIRTUAL_KEYBOARD_VALUE = text

    text = ""
    if km == "Litery":
        text = "wpisuję literę: " + key.lower()
    elif km == "Wielkie litery":
        text = "wpisuję wielką literę: " + key
    elif km == "Cyfry":
        text = "wpisuję cyfrę: " + key
    elif km == "Znaki specjalne":
        idx = VIRTUAL_KEYBOARD_SYMBOLS.index(key)
        text = "" + VIRTUAL_KEYBOARD_SYMBOLS_NAMES[idx]
        text = "wpisuję znak: " + text
    elif km == "Usuwanie":
        text = "OK, usuwam " + key

    _say_it(hass, text)


def go_to_player(hass, say):
    global CURR_REMOTE_MODE_IS_IN_AUDIO_MODE
    CURR_REMOTE_MODE_IS_IN_AUDIO_MODE = True
    # remember the previous context
    global PREV_CURR_GROUP, PREV_CURR_ENTITIE
    # selecting the player to control via remote
    global CURR_ENTITIE_ENTERED
    if len(GROUP_ENTITIES) == 0:
        get_groups(hass)

    if CURR_ENTITIE != "media_player.wbudowany_glosnik":
        # remember prev group and entity
        PREV_CURR_GROUP = CURR_GROUP
        PREV_CURR_ENTITIE = CURR_ENTITIE

    for group in GROUP_ENTITIES:
        if group["entity_id"] == "group.audio_player":
            set_curr_group(hass, group)
            set_curr_entity(hass, "media_player.wbudowany_glosnik")
            CURR_ENTITIE_ENTERED = True
            if say:
                _say_it(hass, "Sterowanie odtwarzaczem")
            break


def go_home(hass):
    global CURR_REMOTE_MODE_IS_IN_AUDIO_MODE
    CURR_REMOTE_MODE_IS_IN_AUDIO_MODE = False
    if len(GROUP_ENTITIES) == 0:
        get_groups(hass)
    global CURR_GROUP_VIEW
    CURR_GROUP_VIEW = "Mój Dom"
    # to reset
    set_curr_group_view()
    say_curr_group_view(hass)


def get_groups(hass):
    global GROUP_ENTITIES
    all_ais_sensors = []
    all_ais_persons = []
    all_ais_automations = []
    all_ais_scenes = []
    all_ais_switches = []
    all_ais_lights = []
    all_ais_climates = []
    all_ais_covers = []
    all_ais_locks = []
    all_ais_vacuums = []
    all_ais_cameras = []
    all_ais_fans = []
    entities = hass.states.async_all()
    GROUP_ENTITIES = []

    def add_menu_item(l_entity):
        l_group = {
            "friendly_name": l_entity.attributes.get("friendly_name"),
            "order": l_entity.attributes.get("order"),
            "entity_id": l_entity.entity_id,
            "entities": l_entity.attributes.get("entity_id"),
            "context_key_words": l_entity.attributes.get("context_key_words"),
            "context_answer": l_entity.attributes.get("context_answer"),
            "context_suffix": l_entity.attributes.get("context_suffix"),
            "remote_group_view": l_entity.attributes.get("remote_group_view"),
            "player_mode": l_entity.attributes.get("player_mode", ""),
        }
        GROUP_ENTITIES.append(l_group)

    def get_key(item):
        return item["order"]

    for entity in entities:
        if entity.entity_id.startswith("group."):
            remote = entity.attributes.get("remote_group_view")
            if remote is not None:
                add_menu_item(entity)
        elif entity.entity_id.startswith("sensor."):
            device_class = entity.attributes.get("device_class", None)
            if device_class is not None:
                all_ais_sensors.append(entity.entity_id)
        elif entity.entity_id.startswith("person."):
            all_ais_persons.append(entity.entity_id)
        elif entity.entity_id.startswith(
                "automation."
        ) and not entity.entity_id.startswith("automation.ais_"):
            all_ais_automations.append(entity.entity_id)
        elif entity.entity_id.startswith("scene."):
            all_ais_scenes.append(entity.entity_id)
        elif (
                entity.entity_id.startswith("switch.")
                and entity.entity_id != "switch.zigbee_tryb_parowania"
        ):
            all_ais_switches.append(entity.entity_id)
        elif entity.entity_id.startswith("light."):
            all_ais_lights.append(entity.entity_id)
        elif entity.entity_id.startswith("climate."):
            all_ais_climates.append(entity.entity_id)
        elif entity.entity_id.startswith("cover."):
            all_ais_covers.append(entity.entity_id)
        elif entity.entity_id.startswith("lock."):
            all_ais_locks.append(entity.entity_id)
        elif entity.entity_id.startswith("vacuum."):
            all_ais_vacuums.append(entity.entity_id)
        elif entity.entity_id.startswith("camera."):
            all_ais_cameras.append(entity.entity_id)
        elif entity.entity_id.startswith("fan."):
            all_ais_fans.append(entity.entity_id)

    # update group on remote
    all_unique_sensors = list(set(all_ais_sensors))
    all_unique_sensors.sort()
    all_unique_persons = list(set(all_ais_persons))
    all_unique_persons.sort()
    all_unique_automations = list(set(all_ais_automations))
    all_unique_automations.sort()
    all_unique_scenes = list(set(all_ais_scenes))
    all_unique_scenes.sort()
    all_unique_switches = list(set(all_ais_switches))
    all_unique_switches.sort()
    all_unique_lights = list(set(all_ais_lights))
    all_unique_lights.sort()
    all_unique_climates = list(set(all_ais_climates))
    all_unique_climates.sort()
    all_unique_covers = list(set(all_ais_covers))
    all_unique_covers.sort()
    all_unique_locks = list(set(all_ais_locks))
    all_unique_locks.sort()
    all_unique_vacuums = list(set(all_ais_vacuums))
    all_unique_vacuums.sort()
    all_unique_cameras = list(set(all_ais_cameras))
    all_unique_cameras.sort()
    all_unique_fans = list(set(all_ais_fans))
    all_unique_fans.sort()

    GROUP_ENTITIES = sorted(GROUP_ENTITIES, key=get_key)

    for group in GROUP_ENTITIES:
        if group["entity_id"] == "group.all_ais_automations":
            group["entities"] = all_unique_automations
        elif group["entity_id"] == "group.all_ais_scenes":
            group["entities"] = all_unique_scenes
        elif group["entity_id"] == "group.all_ais_persons":
            group["entities"] = all_unique_persons
        elif group["entity_id"] == "group.all_ais_sensors":
            group["entities"] = all_unique_sensors
        elif group["entity_id"] == "group.all_ais_switches":
            group["entities"] = all_unique_switches
        elif group["entity_id"] == "group.all_ais_lights":
            group["entities"] = all_unique_lights
        elif group["entity_id"] == "group.all_ais_climates":
            group["entities"] = all_unique_climates
        elif group["entity_id"] == "group.all_ais_covers":
            group["entities"] = all_unique_covers
        elif group["entity_id"] == "group.all_ais_locks":
            group["entities"] = all_unique_locks
        elif group["entity_id"] == "group.all_ais_vacuums":
            group["entities"] = all_unique_vacuums
        elif group["entity_id"] == "group.all_ais_cameras":
            group["entities"] = all_unique_cameras
        elif group["entity_id"] == "group.all_ais_fans":
            group["entities"] = all_unique_fans


# new way to communicate with frame
async def async_process_json_from_frame(hass, json_req):
    res = {"ais": "ok"}
    topic = json_req["topic"]
    payload = json_req["payload"]
    ais_gate_client_id = json_req["ais_gate_client_id"]
    if "hot_word_on" in json_req:
        hot_word_on = json_req["hot_word_on"]
    else:
        hot_word_on = False
    if topic == "ais/player_auto_discovery":
        # AppDiscoveryMode on mobile is ON
        # TODO discovery AI Speaker
        pass
    if topic == "ais/speech_command":
        try:
            # TODO add info if the intent is media player type - to publish
            intent_resp = await _async_process(
                hass, payload, ais_gate_client_id, hot_word_on
            )
            resp_text = intent_resp.speech["plain"]["speech"]
            res = {"ais": "ok", "say_it": resp_text}
        except Exception as e:
            _LOGGER.error("intent_resp " + str(e))

    elif topic == "ais/media_player":
        hass.async_run_job(
            hass.services.async_call(
                "media_player",
                payload,
                {ATTR_ENTITY_ID: "media_player.wbudowany_glosnik"},
            )
        )
    elif topic == "ais/register_wear_os":
        # 1. check pin
        pin = payload["ais_dom_pin"]
        if pin != ais_global.G_AIS_DOM_PIN:
            return json_response({"ais": "nok"})

        # 2. register device and return webhook
        import secrets

        from homeassistant.const import CONF_WEBHOOK_ID

        webhook_id = secrets.token_hex()
        payload[CONF_WEBHOOK_ID] = webhook_id
        payload["user_id"] = ""

        await hass.async_create_task(
            hass.config_entries.flow.async_init(
                "mobile_app", data=payload, context={"source": "registration"}
            )
        )

        res = {CONF_WEBHOOK_ID: payload[CONF_WEBHOOK_ID]}

    elif topic == "ais/event":
        # tag_scanned event
        hass.bus.async_fire(payload["event_type"], payload["event_data"])

    # add player staus for some topics
    if topic in ("ais/player_status", "ais/player_auto_discovery", "ais/media_player"):
        attributes = hass.states.get("media_player.wbudowany_glosnik").attributes
        j_media_info = {
            "media_title": attributes.get("media_title", ""),
            "media_source": attributes.get("source", ""),
            "media_stream_image": attributes.get("media_stream_image", ""),
            "media_album_name": attributes.get("media_album_name", ""),
        }
        res["player_status"] = j_media_info
    res["gate_id"] = ais_global.get_sercure_android_id_dom()
    return json_response(res)


async def async_setup(hass, config):
    """Register the process service."""
    global aisCloudWS
    aisCloudWS = ais_cloud.AisCloudWS(hass)
    warnings.filterwarnings("ignore", module="fuzzywuzzy")
    config = config.get(DOMAIN, {})
    intents = hass.data.get(DOMAIN)
    if intents is None:
        intents = hass.data[DOMAIN] = {}

    for intent_type, utterances in config.get("intents", {}).items():
        conf = intents.get(intent_type)
        if conf is None:
            conf = intents[intent_type] = []
        conf.extend(_create_matcher(utterance) for utterance in utterances)

    async def process(service):
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        await _async_process(hass, text)

    def process_code(service):
        """Parse remote code into action."""
        text = json.loads(service.data.get(ATTR_TEXT))
        _process_code(hass, text)

    def say_it(service):
        """Info to the user."""
        text = ""
        pitch = None
        rate = None
        language = None
        voice = None
        path = None
        if ATTR_TEXT in service.data:
            text = service.data[ATTR_TEXT]
        # TODO else:
        #     # check message template
        #     if "template_text" in service.data:
        #         tpl = template.Template(service.data["template_text"], hass)
        #         message = tpl.async_render()
        #     else:
        #         return
        if "img" in service.data:
            img = service.data["img"]
            if img is not None:
                if len(img) < 3:
                    img = None
        else:
            img = None

        if "pitch" in service.data:
            pitch = service.data["pitch"]
        if "rate" in service.data:
            rate = service.data["rate"]
        if "language" in service.data:
            language = service.data["language"]
        if "voice" in service.data:
            voice = service.data["voice"]
        if "path" in service.data:
            path = service.data["path"]

        _say_it(
            hass=hass,
            message=text,
            img=img,
            pitch=pitch,
            rate=rate,
            language=language,
            voice=voice,
            path=path,
        )

    def say_in_browser(service):
        """Info to the via browser - this is handled by ais-tts in card"""
        pass

    def welcome_home(service):
        """Welcome message."""

        # display favorites from Spotify only if Spotify is available
        if hass.services.has_service("ais_spotify_service", "get_favorites"):
            hass.services.call(
                "ais_spotify_service", "get_favorites", {"type": "featured-playlists"}
            )

        text = "Witaj w Domu. Powiedz proszę w czym mogę Ci pomóc?"
        if ais_global.G_OFFLINE_MODE:
            text = (
                "Uwaga, uruchomienie bez dostępu do sieci, część usług może nie działać poprawnie."
                "Sprawdź połączenie z Internetem."
            )
        _say_it(hass, text)

        # immersive full mode for all apps
        if ais_global.has_root():
            hass.services.call(
                "ais_shell_command",
                "execute_command",
                {
                    "command": "su -c 'settings put global policy_control "
                               "immersive.full=*'"
                },
            )
        if hass.services.has_service("ais_tts", "play_item"):
            # ais_tts - remove all panels
            if "lovelace-dom" in hass.data.get(
                    hass.components.frontend.DATA_PANELS, {}
            ):
                hass.components.frontend.async_remove_panel("lovelace-dom")
            if "aisaudio" in hass.data.get(hass.components.frontend.DATA_PANELS, {}):
                hass.components.frontend.async_remove_panel("aisaudio")
            if "map" in hass.data.get(hass.components.frontend.DATA_PANELS, {}):
                hass.components.frontend.async_remove_panel("map")
            if "history" in hass.data.get(hass.components.frontend.DATA_PANELS, {}):
                hass.components.frontend.async_remove_panel("history")
            if "logbook" in hass.data.get(hass.components.frontend.DATA_PANELS, {}):
                hass.components.frontend.async_remove_panel("logbook")

        # set the flag to info that the AIS start part is done - this is needed to don't say some info before this flag
        ais_global.G_AIS_START_IS_DONE = True

    async def async_set_context(service):
        """Set the context in app."""
        context = service.data[ATTR_TEXT]
        # get audio types again if the was a network problem on start
        if ais_global.G_AIS_START_IS_DONE:
            if context == "radio":
                types = hass.states.get("input_select.radio_type").attributes.get(
                    "options", []
                )
                if len(types) < 2:
                    await hass.services.async_call("ais_cloud", "get_radio_types")
                # TODO for the rest of audio

        if context == "ais_tv":
            hass.states.async_set("sensor.ais_player_mode", "ais_tv")
        elif context == "ais_tv_on":
            hass.states.async_set("sensor.ais_tv_mode", "tv_on")
            hass.states.async_set("sensor.ais_tv_activity", "")
            _say_it(hass, "Sterowanie na monitorze")
            await _publish_command_to_frame(hass, "goToActivity", "ActivityMenu")
        elif context == "ais_tv_off":
            hass.states.async_set("sensor.ais_tv_mode", "tv_off")
            hass.states.async_set("sensor.ais_tv_activity", "")
            _say_it(hass, "Sterowanie bez monitora")
            await _publish_command_to_frame(
                hass, "goToActivity", "SplashScreenActivity"
            )
        elif context == "ais_tv_youtube":
            hass.states.async_set("sensor.ais_tv_activity", "youtube")
            _say_it(hass, "Odtwarzacz wideo")
            await _publish_command_to_frame(hass, "goToActivity", "ExoPlayerActivity")
        elif context == "ais_tv_spotify":
            hass.states.async_set("sensor.ais_tv_activity", "spotify")
            _say_it(hass, "Odtwarzacz Spotify")
            await _publish_command_to_frame(hass, "goToActivity", "SpotifyActivity")
        elif context == "ais_tv_cameras":
            hass.states.async_set("sensor.ais_tv_activity", "camera")
            _say_it(hass, "Podgląd z kamery")
        elif context == "ais_tv_show_camera":
            hass.states.async_set("sensor.ais_tv_activity", "camera")
            cam_id = service.data["entity_id"]
            cam_attr = hass.states.get(cam_id).attributes
            cam_name = cam_attr.get("friendly_name", "")
            _say_it(hass, "Podgląd z kamery " + cam_name)
            await _publish_command_to_frame(hass, "showCamera", cam_id)
        elif context == "ais_tv_settings":
            hass.states.async_set("sensor.ais_tv_activity", "settings")
            _say_it(hass, "Ustawienia aplikacji")
            await _publish_command_to_frame(hass, "goToActivity", "SettingsActivity")
        elif context == "radio_public":
            hass.states.async_set("sensor.ais_player_mode", "radio_player")
            hass.states.async_set("sensor.ais_radio_origin", "public")
            hass.states.async_set("sensor.radiolist", -1, {})
            atrr = hass.states.get("input_select.radio_type").attributes
            hass.states.async_set("input_select.radio_type", "-", atrr)
        elif context == "radio_private":
            hass.states.async_set("sensor.ais_player_mode", "radio_player")
            hass.states.async_set("sensor.ais_radio_origin", "private")
            hass.states.async_set("sensor.radiolist", -1, {})
            atrr = hass.states.get("input_select.radio_type").attributes
            hass.states.async_set("input_select.radio_type", "-", atrr)
        elif context == "radio_shared":
            hass.states.async_set("sensor.ais_player_mode", "radio_player")
            hass.states.async_set("sensor.ais_radio_origin", "shared")
            hass.states.async_set("sensor.radiolist", -1, {})
            atrr = hass.states.get("input_select.radio_type").attributes
            hass.states.async_set("input_select.radio_type", "-", atrr)
        elif context == "podcast_public":
            hass.states.async_set("sensor.ais_player_mode", "podcast_player")
            hass.states.async_set("sensor.ais_podcast_origin", "public")
            hass.states.async_set("sensor.podcastlist", -1, {})
            atrr = hass.states.get("input_select.podcast_type").attributes
            hass.states.async_set("input_select.podcast_type", "-", atrr)
        elif context == "podcast_private":
            hass.states.async_set("sensor.ais_player_mode", "podcast_player")
            hass.states.async_set("sensor.ais_podcast_origin", "private")
            hass.states.async_set("sensor.podcastlist", -1, {})
            atrr = hass.states.get("input_select.podcast_type").attributes
            hass.states.async_set("input_select.podcast_type", "-", atrr)
        elif context == "podcast_shared":
            hass.states.async_set("sensor.ais_player_mode", "podcast_player")
            hass.states.async_set("sensor.ais_podcast_origin", "shared")
            hass.states.async_set("sensor.podcastlist", -1, {})
            atrr = hass.states.get("input_select.podcast_type").attributes
            hass.states.async_set("input_select.podcast_type", "-", atrr)
        elif context == "YouTube":
            hass.states.async_set("sensor.ais_player_mode", "music_player")
            await hass.services.async_call(
                "input_select",
                "select_option",
                {"entity_id": "input_select.ais_music_service", "option": "YouTube"},
            )
        elif context == "Spotify":
            hass.states.async_set("sensor.ais_player_mode", "music_player")
            await hass.services.async_call(
                "input_select",
                "select_option",
                {"entity_id": "input_select.ais_music_service", "option": "Spotify"},
            )
        elif context == "Radio":
            hass.states.async_set("sensor.ais_player_mode", "radio_player")
        elif context == "Podcast":
            hass.states.async_set("sensor.ais_player_mode", "podcast_player")
        else:
            for idx, menu in enumerate(GROUP_ENTITIES, start=0):
                context_key_words = menu["context_key_words"]
                if context_key_words is not None:
                    context_key_words = context_key_words.split(",")
                    if context in context_key_words:
                        set_curr_group(hass, menu)
                        set_curr_entity(hass, None)
                        if context == "spotify":
                            await hass.services.async_call(
                                "input_select",
                                "select_option",
                                {
                                    "entity_id": "input_select.ais_music_service",
                                    "option": "Spotify",
                                },
                            )
                        elif context == "youtube":
                            await hass.services.async_call(
                                "input_select",
                                "select_option",
                                {
                                    "entity_id": "input_select.ais_music_service",
                                    "option": "YouTube",
                                },
                            )
                        break

    async def check_local_ip(service):
        """Set the local ip in app."""
        ip = ais_global.get_my_global_ip()
        hass.states.async_set(
            "sensor.internal_ip_address",
            ip,
            {"friendly_name": "Lokalny adres IP", "icon": "mdi:access-point-network"},
        )

    async def publish_command_to_frame(service):
        key = service.data["key"]
        val = service.data["val"]
        ip = "localhost"
        if "ip" in service.data:
            if service.data["ip"] is not None:
                ip = service.data["ip"]
        await _publish_command_to_frame(hass, key, val, ip)

    # old
    def process_command_from_frame(service):
        _process_command_from_frame(hass, service)

    # fix for the problem on box with remote
    def prepare_remote_menu(service):
        get_groups(hass)
        # register context intent
        for menu in GROUP_ENTITIES:
            context_key_words = menu["context_key_words"]
            if context_key_words is not None:
                context_key_words = context_key_words.split(",")
                async_register(hass, INTENT_CHANGE_CONTEXT, context_key_words)

    def on_new_iot_device_selection(service):
        iot = service.data["iot"].lower()
        # the name according to the selected model
        if "dom_" + ais_global.G_MODEL_SONOFF_S20 in iot:
            info = "Inteligentne gniazdo"
        elif "dom_" + ais_global.G_MODEL_SONOFF_B1 in iot:
            info = "Żarówka"
        elif "dom_" + ais_global.G_MODEL_SONOFF_TH in iot:
            info = "Przełącznik z czujnikami"
        elif "dom_" + ais_global.G_MODEL_SONOFF_SLAMPHER in iot:
            info = "Oprawka"
        elif "dom_" + ais_global.G_MODEL_SONOFF_TOUCH in iot:
            info = "Przełącznik dotykowy"
        elif "dom_" + ais_global.G_MODEL_SONOFF_POW in iot:
            info = "Przełącznik z pomiarem mocy"
        elif "dom_" + ais_global.G_MODEL_SONOFF_DUAL in iot:
            info = "Przełącznik podwójny"
        elif "dom_" + ais_global.G_MODEL_SONOFF_BASIC in iot:
            info = "Przełącznik"
        elif "dom_" + ais_global.G_MODEL_SONOFF_IFAN in iot:
            info = "Wentylator sufitowy"
        elif "dom_" + ais_global.G_MODEL_SONOFF_T11 in iot:
            info = "Przełącznik dotykowy pojedynczy"
        elif "dom_" + ais_global.G_MODEL_SONOFF_T12 in iot:
            info = "Przełącznik dotykowy podwójny"
        elif "dom_" + ais_global.G_MODEL_SONOFF_T13 in iot:
            info = "Przełącznik dotykowy potrójny"
        else:
            info = "Nowe urządzenie"
        hass.services.call(
            "input_text",
            "set_value",
            {"entity_id": "input_text.ais_iot_device_name", "value": info},
        )
        # set the WIFI as an current WIFI (only if empty)
        wifis = hass.states.get("input_select.ais_android_wifi_network")
        if (
                wifis.state == ais_global.G_EMPTY_OPTION
                and ais_global.GLOBAL_MY_WIFI_SSID is not None
        ):
            options = wifis.attributes.get("options")
            for o in options:
                if ais_global.GLOBAL_MY_WIFI_SSID in o:
                    hass.services.call(
                        "input_select",
                        "select_option",
                        {
                            "entity_id": "input_select.ais_android_wifi_network",
                            "option": o,
                        },
                    )

    async def async_mob_request(service):
        from homeassistant.components.mobile_app.const import (
            ATTR_APP_DATA,
            ATTR_APP_ID,
            ATTR_APP_VERSION,
            ATTR_OS_VERSION,
            ATTR_PUSH_TOKEN,
            ATTR_PUSH_URL,
        )

        if "request" not in service.data:
            _LOGGER.error("No request in service.data")
            return
        if "device_id" not in service.data:
            _LOGGER.error("No device_id in service.data")
            return

        session = async_get_clientsession(hass)

        device_id = service.data["device_id"]
        entry_data = None
        data = {"request": service.data["request"]}
        if "data" in service.data:
            data["data"] = service.data["data"]
        else:
            data["data"] = {}

        for entry in hass.config_entries.async_entries("mobile_app"):
            if entry.data["device_name"] == device_id:
                entry_data = entry.data

        if entry_data is None:
            _LOGGER.error("No mob id from " + device_id)
            return

        app_data = entry_data[ATTR_APP_DATA]
        push_token = app_data[ATTR_PUSH_TOKEN]
        push_url = app_data[ATTR_PUSH_URL]

        data[ATTR_PUSH_TOKEN] = push_token

        reg_info = {
            ATTR_APP_ID: entry_data[ATTR_APP_ID],
            ATTR_APP_VERSION: entry_data[ATTR_APP_VERSION],
        }
        if ATTR_OS_VERSION in entry_data:
            reg_info[ATTR_OS_VERSION] = entry_data[ATTR_OS_VERSION]

        data["registration_info"] = reg_info

        try:
            with async_timeout.timeout(10):
                response = await session.post(push_url, json=data)
                result = await response.json()

            if response.status in [200, 201, 202]:
                return

            fallback_error = result.get("errorMessage", "Unknown error")
            fallback_message = (
                f"Internal server error, please try again later: {fallback_error}"
            )
            message = result.get("message", fallback_message)
            _LOGGER.error(message)

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout sending notification to %s", push_url)

    async def async_mob_notify(service):
        from homeassistant.components.mobile_app.const import (
            ATTR_APP_DATA,
            ATTR_APP_ID,
            ATTR_APP_VERSION,
            ATTR_OS_VERSION,
            ATTR_PUSH_TOKEN,
            ATTR_PUSH_URL,
        )

        session = async_get_clientsession(hass)

        device_id = service.data["device_id"]
        # to allow notation with _
        device_id = device_id.replace("mobile_ais_dom_", "mobile_ais_dom-")

        entry_data = None
        data = {"message": service.data["message"]}
        if "title" in service.data:
            data["title"] = service.data["title"]
        else:
            data["title"] = "Powiadomienie z AI-Speaker"
        if "image" in service.data:
            data["image"] = service.data["image"]
        if "say" in service.data:
            data["say"] = service.data["say"]
        else:
            data["say"] = False
        if "priority" in service.data:
            data["priority"] = service.data["priority"]
        else:
            data["priority"] = "normal"
        if "notification_id" in service.data:
            data["notification_id"] = service.data["notification_id"]
        else:
            data["notification_id"] = 0
        if "data" in service.data:
            data["data"] = service.data["data"]
        else:
            data["data"] = {}
        if "click_action" in service.data:
            data["click_action"] = service.data["click_action"]
        else:
            data["click_action"] = ""

        for entry in hass.config_entries.async_entries("mobile_app"):
            if entry.data["device_name"] == device_id:
                entry_data = entry.data

        if entry_data is None:
            # new way - via device id
            dev_registry = await hass.helpers.device_registry.async_get_registry()
            device = dev_registry.async_get(device_id)
            if device is not None:
                for entry in hass.config_entries.async_entries("mobile_app"):
                    if entry.data["device_name"] == device.name:
                        entry_data = entry.data

        if entry_data is None:
            _LOGGER.error("No mob id from " + device_id)
            return

        app_data = entry_data[ATTR_APP_DATA]
        push_token = app_data[ATTR_PUSH_TOKEN]
        push_url = app_data[ATTR_PUSH_URL]

        data[ATTR_PUSH_TOKEN] = push_token

        reg_info = {
            ATTR_APP_ID: entry_data[ATTR_APP_ID],
            ATTR_APP_VERSION: entry_data[ATTR_APP_VERSION],
        }
        if ATTR_OS_VERSION in entry_data:
            reg_info[ATTR_OS_VERSION] = entry_data[ATTR_OS_VERSION]

        data["registration_info"] = reg_info

        try:
            with async_timeout.timeout(10):
                response = await session.post(push_url, json=data)
                result = await response.json()

            if response.status in [200, 201, 202]:
                return

            fallback_error = result.get("errorMessage", "Unknown error")
            fallback_message = (
                f"Internal server error, please try again later: {fallback_error}"
            )
            message = result.get("message", fallback_message)
            _LOGGER.error(message)

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout sending notification to %s", push_url)

        # await hass.services.async_call(
        #     "notify", device_id, {"message": message, "title": title, "data": data}
        # )

    async def check_night_mode(service):
        # check the night / quiet mode
        timer = False
        if "timer" in service.data:
            timer = service.data["timer"]
        # TODO - check this fix for 'NoneType' object has no attribute 'state'
        quiet_mode = ""
        if hass is not None:
            if hass.states.get("input_boolean.ais_quiet_mode") is not None:
                quiet_mode = hass.states.get("input_boolean.ais_quiet_mode").state
        if quiet_mode == "":
            hass.async_add_job(
                hass.services.async_call("frontend", "set_theme", {"name": "ais"})
            )
            return

        def apply_night_mode():
            _LOGGER.info("Start Night ")
            ais_global.G_AIS_DAY_MEDIA_VOLUME_LEVEL = hass.states.get(
                "media_player.wbudowany_glosnik"
            ).attributes["volume_level"]
            # set volume as min from (0.2, curr_volume_level)
            vl = min(0.2, ais_global.G_AIS_DAY_MEDIA_VOLUME_LEVEL)
            hass.async_add_job(
                hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {"entity_id": "media_player.wbudowany_glosnik", "volume_level": vl},
                )
            )
            hass.async_add_job(
                hass.services.async_call("frontend", "set_theme", {"name": "night"})
            )

        def apply_day_mode():
            _LOGGER.info("Stop Night ")
            curr_volume_level = hass.states.get(
                "media_player.wbudowany_glosnik"
            ).attributes["volume_level"]
            # get volume level
            if ais_global.G_AIS_DAY_MEDIA_VOLUME_LEVEL is not None:
                vl = max(
                    0.1, ais_global.G_AIS_DAY_MEDIA_VOLUME_LEVEL, curr_volume_level
                )
                hass.async_add_job(
                    hass.services.async_call(
                        "media_player",
                        "volume_set",
                        {
                            "entity_id": "media_player.wbudowany_glosnik",
                            "volume_level": vl,
                        },
                    )
                )
            hass.async_add_job(
                hass.services.async_call("frontend", "set_theme", {"name": "ais"})
            )

        if not timer:
            # call after change or on start
            quiet_mode_start_attr = hass.states.get(
                "input_datetime.ais_quiet_mode_start"
            ).attributes
            quiet_mode_stop_attr = hass.states.get(
                "input_datetime.ais_quiet_mode_stop"
            ).attributes
            th = datetime.datetime.now().hour * 60 * 60
            tm = datetime.datetime.now().minute * 60
            ts = th + tm
            qm_st = quiet_mode_start_attr["timestamp"]
            qm_et = quiet_mode_stop_attr["timestamp"]
            # if the times are equal and 0 we can set them as default
            if (qm_st == qm_et == 0) and quiet_mode == "on":
                hass.async_add_job(
                    hass.services.async_call(
                        "input_datetime",
                        "set_datetime",
                        {
                            "entity_id": "input_datetime.ais_quiet_mode_start",
                            "time": "22:00",
                        },
                    )
                )
                hass.async_add_job(
                    hass.services.async_call(
                        "input_datetime",
                        "set_datetime",
                        {
                            "entity_id": "input_datetime.ais_quiet_mode_stop",
                            "time": "06:00",
                        },
                    )
                )
            # if times are smaller than current time, this means that this time (hour and minute)
            # will be again tomorrow - add one day
            if int(qm_st) < int(ts):
                qm_st = int(qm_st) + 86400
            if int(qm_et) < int(ts):
                qm_et = int(qm_et) + 86400
            # if we are more close to night - apply day mode
            if (int(qm_st) > int(qm_et)) and quiet_mode == "on":
                apply_night_mode()
            else:
                apply_day_mode()
        if timer and quiet_mode == "on":
            # call from timer
            quiet_mode_start_attr = hass.states.get(
                "input_datetime.ais_quiet_mode_start"
            ).attributes
            quiet_mode_stop_attr = hass.states.get(
                "input_datetime.ais_quiet_mode_stop"
            ).attributes
            if quiet_mode_start_attr["timestamp"] != quiet_mode_stop_attr["timestamp"]:

                h = datetime.datetime.now().hour
                m = datetime.datetime.now().minute
                if (
                        quiet_mode_start_attr["hour"] == h
                        and quiet_mode_start_attr["minute"] == m
                ):
                    apply_night_mode()
                if (
                        quiet_mode_stop_attr["hour"] == h
                        and quiet_mode_stop_attr["minute"] == m
                ):
                    apply_day_mode()

    # register services
    hass.services.async_register(DOMAIN, "process", process)
    hass.services.async_register(DOMAIN, "process_code", process_code)
    hass.services.async_register(DOMAIN, "say_it", say_it)
    hass.services.async_register(DOMAIN, "say_in_browser", say_in_browser)
    hass.services.async_register(DOMAIN, "welcome_home", welcome_home)
    hass.services.async_register(
        DOMAIN, "publish_command_to_frame", publish_command_to_frame
    )
    hass.services.async_register(
        DOMAIN, "process_command_from_frame", process_command_from_frame
    )
    hass.services.async_register(DOMAIN, "prepare_remote_menu", prepare_remote_menu)
    hass.services.async_register(
        DOMAIN, "on_new_iot_device_selection", on_new_iot_device_selection
    )
    hass.services.async_register(DOMAIN, "set_context", async_set_context)
    hass.services.async_register(DOMAIN, "check_local_ip", check_local_ip)
    hass.services.async_register(DOMAIN, "check_night_mode", check_night_mode)
    hass.services.async_register(DOMAIN, "mob_notify", async_mob_notify)
    hass.services.async_register(DOMAIN, "mob_request", async_mob_request)

    # register intents
    hass.helpers.intent.async_register(GetTimeIntent())
    hass.helpers.intent.async_register(GetDateIntent())
    hass.helpers.intent.async_register(AisClimateSetTemperature())
    hass.helpers.intent.async_register(AisClimateSetPresentMode())
    hass.helpers.intent.async_register(AisClimateSetAllOn())
    hass.helpers.intent.async_register(AisClimateSetAllOff())
    hass.helpers.intent.async_register(TurnOnIntent())
    hass.helpers.intent.async_register(TurnOffIntent())
    hass.helpers.intent.async_register(ToggleIntent())
    hass.helpers.intent.async_register(StatusIntent())
    hass.helpers.intent.async_register(PersonStatusIntent())
    hass.helpers.intent.async_register(PlayRadioIntent())
    hass.helpers.intent.async_register(AisPlayPodcastIntent())
    hass.helpers.intent.async_register(AisPlayYtMusicIntent())
    hass.helpers.intent.async_register(AisPlaySpotifyIntent())
    hass.helpers.intent.async_register(AskQuestionIntent())
    hass.helpers.intent.async_register(AskWikiQuestionIntent())
    hass.helpers.intent.async_register(ChangeContextIntent())
    hass.helpers.intent.async_register(AisGetWeather())
    hass.helpers.intent.async_register(AisGetWeather48())
    hass.helpers.intent.async_register(AisLampsOn())
    hass.helpers.intent.async_register(AisLampsOff())
    hass.helpers.intent.async_register(AisSwitchesOn())
    hass.helpers.intent.async_register(AisSwitchesOff())
    hass.helpers.intent.async_register(AisOpenCover())
    hass.helpers.intent.async_register(AisCloseCover())
    hass.helpers.intent.async_register(AisStop())
    hass.helpers.intent.async_register(AisPlay())
    hass.helpers.intent.async_register(AisNext())
    hass.helpers.intent.async_register(AisPrev())
    hass.helpers.intent.async_register(AisSceneActive())
    hass.helpers.intent.async_register(AisRunAutomation())
    hass.helpers.intent.async_register(AisAskGoogle())
    hass.helpers.intent.async_register(AisSayIt())
    hass.helpers.intent.async_register(SpellStatusIntent())

    async_register(hass, INTENT_GET_WEATHER, ["[aktualna] pogoda", "jaka jest pogoda"])
    async_register(
        hass,
        INTENT_GET_WEATHER_48,
        ["prognoza pogody", "pogoda prognoza", "jaka będzie pogoda"],
    )
    async_register(
        hass,
        INTENT_CLIMATE_SET_TEMPERATURE,
        [
            "Ogrzewanie [w] {item} {temp} stopni[e]",
            "Ogrzewanie [w] {item} temperatura {temp} stopni[e]",
        ],
    )
    async_register(hass, INTENT_CLIMATE_SET_PRESENT_MODE, ["Ogrzewanie tryb {item}"])
    async_register(hass, INTENT_CLIMATE_SET_ALL_OFF, ["Wyłącz całe ogrzewanie"])
    async_register(hass, INTENT_CLIMATE_SET_ALL_ON, ["Włącz całe ogrzewanie"])
    async_register(
        hass,
        INTENT_LAMPS_ON,
        [
            "włącz światła",
            "zapal światła",
            "włącz wszystkie światła",
            "zapal wszystkie światła",
        ],
    )
    async_register(
        hass,
        INTENT_LAMPS_OFF,
        [
            "zgaś światła",
            "wyłącz światła",
            "wyłącz wszystkie światła",
            "zgaś wszystkie światła",
        ],
    )
    async_register(
        hass, INTENT_SWITCHES_ON, ["włącz przełączniki", "włącz wszystkie przełączniki"]
    )
    async_register(
        hass,
        INTENT_SWITCHES_OFF,
        ["wyłącz przełączniki", "wyłącz wszystkie przełączniki"],
    )
    async_register(
        hass,
        INTENT_GET_TIME,
        [
            "która",
            "która [jest] [teraz] godzina",
            "którą mamy godzinę",
            "jaki [jest] czas",
            "[jaka] [jest] godzina",
        ],
    )
    async_register(
        hass,
        INTENT_GET_DATE,
        [
            "[jaka] [jest] data",
            "jaki [mamy] [jest] [dzisiaj] dzień",
            "co dzisiaj jest",
            "co [mamy] [jest] dzisiaj",
        ],
    )
    async_register(
        hass,
        INTENT_PLAY_RADIO,
        [
            "Włącz radio",
            "Radio {item}",
            "Włącz radio {item}",
            "Graj radio {item}",
            "Graj {item} radio",
            "Posłuchał bym radio {item}",
            "Włącz stację radiową {item}",
        ],
    )
    async_register(
        hass,
        INTENT_PLAY_PODCAST,
        [
            "Podcast {item}",
            "Włącz podcast {item}",
            "Graj podcast {item}",
            "Graj {item} podcast",
            "Posłuchał bym podcast {item}",
        ],
    )
    async_register(
        hass,
        INTENT_PLAY_YT_MUSIC,
        [
            "Muzyka {item}",
            "Włącz muzykę {item}",
            "Graj muzykę {item}",
            "Graj {item} muzykę",
            "Posłuchał bym muzykę {item}",
            "Włącz [z] [na] YouTube {item}",
            "YouTube {item}",
        ],
    )
    async_register(hass, INTENT_PLAY_SPOTIFY, ["Spotify {item}"])
    async_register(hass, INTENT_TURN_ON, ["Włącz {item}", "Zapal światło w {item}"])
    async_register(hass, INTENT_TURN_OFF, ["Wyłącz {item}", "Zgaś Światło w {item}"])
    async_register(hass, INTENT_TOGGLE, ["Przełącz {item}"])
    async_register(
        hass,
        INTENT_STATUS,
        [
            "Jaka jest {item}",
            "Jaki jest {item}",
            "Jak jest {item}",
            "Jakie jest {item}",
            "[jaki] [ma] status {item}",
        ],
    )
    async_register(
        hass,
        INTENT_ASK_QUESTION,
        [
            "Co to jest {item}",
            "Kto to jest {item}",
            "Znajdź informację o {item}",
            "Znajdź informacje o {item}",
            "Wyszukaj informację o {item}",
            "Wyszukaj informacje o {item}",
            "Wyszukaj {item}",
            "Kim jest {item}",
            "Informacje o {item}",
            "Czym jest {item}",
            "Opowiedz mi o {intem}",
            "Informację na temat {item}",
            "Co wiesz o {item}",
            "Co wiesz na temat {item}",
            "Opowiedz o {item}",
            "Kim są {item}",
            "Kto to {item}",
        ],
    )
    async_register(hass, INTENT_SPELL_STATUS, ["Przeliteruj {item}", "Literuj {item}"])
    async_register(
        hass,
        INTENT_ASKWIKI_QUESTION,
        ["Wikipedia {item}", "wiki {item}", "encyklopedia {item}"],
    )
    async_register(hass, INTENT_OPEN_COVER, ["Otwórz {item}", "Odsłoń {item}"])
    async_register(hass, INTENT_CLOSE_COVER, ["Zamknij {item}", "Zasłoń {item}"])
    async_register(
        hass, INTENT_STOP, ["Stop", "Zatrzymaj", "Koniec", "Pauza", "Zaniechaj", "Stój"]
    )
    async_register(hass, INTENT_PLAY, ["Start", "Graj", "Odtwarzaj"])
    async_register(hass, INTENT_SCENE, ["Scena {item}", "Aktywuj [scenę] {item}"])
    async_register(
        hass, INTENT_RUN_AUTOMATION, ["Uruchom {item}", "Automatyzacja {item}"]
    )
    async_register(hass, INTENT_ASK_GOOGLE, ["Google {item}"])
    async_register(
        hass, INTENT_PERSON_STATUS, ["Gdzie jest {item}", "Lokalizacja {item}"]
    )
    async_register(
        hass,
        INTENT_NEXT,
        ["[włącz] następny", "[włącz] kolejny", "[graj] następny", "[graj] kolejny"],
    )
    async_register(
        hass,
        INTENT_PREV,
        [
            "[włącz] poprzedni",
            "[włącz] wcześniejszy",
            "[graj] poprzedni",
            "[graj] wcześniejszy",
        ],
    )
    async_register(
        hass,
        INTENT_SAY_IT,
        ["Powiedz", "Mów", "Powiedz {item}", "Mów {item}", "Echo {item}"],
    )

    # initial status of the player
    hass.states.async_set("sensor.ais_player_mode", "ais_favorites")

    # sensors
    hass.states.async_set("sensor.aisknowledgeanswer", "", {"text": ""})
    hass.states.async_set(
        "sensor.ais_wifi_service_current_network_info",
        0,
        {
            "friendly_name": "Prędkość połączenia",
            "unit_of_measurement": "MB",
            "icon": "mdi:speedometer",
        },
    )

    async def ais_run_each_minute(now):
        await hass.services.async_call(
            "ais_ai_service", "check_night_mode", {"timer": True}
        )

    async def ais_run_each_minute2(now):
        await hass.services.async_call(
            "ais_ai_service", "check_night_mode", {"timer": True}
        )
        time_now = datetime.datetime.now()
        current_time = time_now.strftime("%H%M")
        await hass.services.async_call(
            "ais_shell_command", "set_clock_display_text", {"text": current_time + "0"}
        )

    # run each minute at first second
    _dt = dt_util.utcnow()
    if ais_global.has_front_clock():
        event.async_track_utc_time_change(hass, ais_run_each_minute2, second=1)
    else:
        event.async_track_utc_time_change(hass, ais_run_each_minute, second=1)

    # AIS agent
    agent = AisAgent(hass)
    conversation.async_set_agent(hass, agent)
    return True


async def _publish_command_to_frame(hass, key, val, ip=None):
    # sent the command to the android frame via http
    if ip is None:
        ip = "localhost"
    url = ais_global.G_HTTP_REST_SERVICE_BASE_URL.format(ip)

    if key == "WifiConnectToSid":
        ssid = val.split(";")[0]
        if ssid is None or ssid == "-" or ssid == "":
            _say_it(hass, "Wybierz sieć WiFi z listy")
            return

        # TODO get password from file
        password = hass.states.get("input_text.ais_android_wifi_password").state
        if len(password.strip()) == 0:
            _say_it(hass, "ok, przełączam na sieć: " + ssid)
        else:
            _say_it(hass, "ok, łączę z siecią: " + ssid)

        wifi_type = val.split(";")[-3]
        bssid = val.split(";")[-1].replace("MAC:", "").strip()
        requests_json = {
            key: ssid,
            "ip": ip,
            "WifiNetworkPass": password,
            "WifiNetworkType": wifi_type,
            "bssid": bssid,
        }

    elif key == "WifiConnectTheDevice":
        iot = val.split(";")[0]
        if iot == ais_global.G_EMPTY_OPTION:
            _say_it(hass, "wybierz urządzenie które mam dołączyć")
            return
        # check if wifi is selected
        ssid = hass.states.get("input_select.ais_android_wifi_network").state.split(
            ";"
        )[0]
        if ssid == ais_global.G_EMPTY_OPTION:
            _say_it(hass, "wybierz wifi do której mam dołączyć urządzenie")
            return

        # take bssid
        bssid = val.split(";")[-1].replace("MAC:", "").strip()

        # check the frequency
        wifi_frequency_mhz = val.split(";")[-2]
        if not wifi_frequency_mhz.startswith("2.4"):
            _say_it(
                hass,
                "Urządzenia mogą pracować tylko w sieci 2.4 GHz, wybierz inną sieć.",
            )

        # check if name is selected, if not then add the device name
        name = hass.states.get("input_text.ais_iot_device_name").state
        # friendly name (32 chars max)
        if name == "":
            name = iot
        if len(name) > 32:
            _say_it(hass, "nazwa urządzenie może mieć maksymalnie 32 znaki")
            return
        _say_it(hass, "OK, dodajemy: " + name)
        password = hass.states.get("input_text.ais_iot_device_wifi_password").state

        # save the time when this was executed
        # to inform the user about new device
        import time

        ais_global.G_AIS_NEW_DEVICE_NAME = name
        ais_global.G_AIS_NEW_DEVICE_START_ADD_TIME = time.time()
        requests_json = {
            key: iot,
            "ip": ip,
            "WifiNetworkPass": password,
            "WifiNetworkSsid": ssid,
            "IotName": name,
            "bsssid": bssid,
        }
    elif key == "showCamera":
        component = hass.data.get("camera")
        camera = component.get_entity(val)
        stream_source = await camera.stream_source()
        requests_json = {"showCamera": {"streamUrl": stream_source, "haCamId": val}}
    elif key == "WifiConnectionInfo":
        requests_json = {key: val, "ip": ip}
        # tunnel guard
        access = hass.states.get("input_boolean.ais_remote_access").state
        gate_id = ais_global.get_sercure_android_id_dom()
        if access == "on":
            try:
                # r = requests.get('http://httpbin.org/status/404', timeout=10)
                r = requests.get("http://" + gate_id + ".paczka.pro", timeout=10)
                if r.status_code == 404:
                    command = "pm2 restart tunnel || pm2 start /data/data/pl.sviete.dom/files/usr/bin/cloudflared" \
                              " --name tunnel --output /dev/null --error /dev/null" \
                              " --restart-delay=150000 -- --hostname http://{}.paczka.pro" \
                              " --url http://localhost:8180".format(gate_id)
                    subprocess.Popen(
                        command,
                        shell=True,  # nosec
                        stdout=None,
                        stderr=None,
                    )
            except Exception:
                pass

    else:
        requests_json = {key: val, "ip": ip}
    try:
        requests.post(url + "/command", json=requests_json, timeout=2)
    except Exception:
        pass


def _wifi_rssi_to_info(rssi):
    info = "moc nieznana"
    if rssi > -31:
        return "moc doskonała (" + str(rssi) + ")"
    if rssi > -68:
        return "moc bardzo dobra (" + str(rssi) + ")"
    if rssi > -71:
        return "moc dobra (" + str(rssi) + ")"
    if rssi > -81:
        return "moc słaba (" + str(rssi) + ")"
    if rssi > -91:
        return "moc bardzo słaba (" + str(rssi) + ")"
    return info


def _wifi_frequency_info(mhz):
    if str(mhz).startswith("2"):
        return "2.4 GHz"
    elif str(mhz).startswith("5"):
        return "5 GHz"
    return str(mhz)


def _publish_wifi_status(hass, service):
    wifis = json.loads(service.data["payload"])
    ais_global.GLOBAL_SCAN_WIFI_ANSWER = wifis
    wifis_names = [ais_global.G_EMPTY_OPTION]
    for item in wifis["ScanResult"]:
        if len(item["ssid"]) > 0:
            wifis_names.append(
                item["ssid"]
                + "; "
                + _wifi_rssi_to_info(item["rssi"])
                + "; "
                + item["capabilities"]
                + "; "
                + _wifi_frequency_info(item["frequency_mhz"])
                + "; MAC: "
                + item["bssid"]
            )
    hass.async_run_job(
        hass.services.call(
            "input_select",
            "set_options",
            {
                "entity_id": "input_select.ais_android_wifi_network",
                "options": wifis_names,
            },
        )
    )
    return len(wifis_names) - 1


def _process_command_from_frame(hass, service):
    # process the message from frame
    if "topic" not in service.data:
        return

    if service.data["topic"] == "ais/speech_command":
        hass.async_run_job(
            hass.services.async_call(
                "conversation", "process", {"text": service.data["payload"]}
            )
        )
        return
    elif service.data["topic"] == "ais/key_command":
        _process_code(hass, json.loads(service.data["payload"]))
        return
    elif service.data["topic"] == "ais/speech_text":
        _say_it(hass, service.data["payload"])
        return
    elif service.data["topic"] == "ais/speech_status":
        # AIS service.data["payload"] can be: START -> DONE/ERROR
        event_data = {"status": str(service.data["payload"])}
        hass.bus.fire("ais_speech_status", event_data)
        hass.states.async_set(
            "sensor.ais_speech_status", str(service.data["payload"]), {}
        )
        _LOGGER.debug("speech_status: " + str(service.data["payload"]))
        return
    elif service.data["topic"] == "ais/add_bookmark":
        try:
            bookmark = json.loads(service.data["payload"])
            hass.async_run_job(
                hass.services.call(
                    "ais_bookmarks",
                    "add_bookmark",
                    {
                        "attr": {
                            "media_title": bookmark["media_title"],
                            "source": bookmark["media_source"],
                            "media_position": bookmark["media_position"],
                            "media_content_id": bookmark["media_content_id"],
                            "media_stream_image": bookmark["media_stream_image"],
                        }
                    },
                )
            )
        except Exception as e:
            _LOGGER.info("problem to add_bookmark: " + str(e))
        return
    elif service.data["topic"] == "ais/player_speed":
        # speed = json.loads(service.data["payload"])
        # _say_it(hass, "prędkość odtwarzania: " + str(speed["currentSpeed"]))
        # hass.services.call(
        #     'input_number',
        #     'set_value', {
        #         "entity_id": "input_number.media_player_speed",
        #         "value": round(speed["currentSpeed"], 2)})
        return
    elif service.data["topic"] == "ais/wifi_scan_info":
        len_wifis = _publish_wifi_status(hass, service)
        info = "Mamy dostępne " + str(len_wifis) + " wifi."
        _say_it(hass, info)
        return
    elif service.data["topic"] == "ais/iot_scan_info":
        iot = json.loads(service.data["payload"])
        iot_names = [ais_global.G_EMPTY_OPTION]
        for item in iot["ScanResult"]:
            if len(item["ssid"]) > 0:
                iot_names.append(
                    item["ssid"]
                    + "; "
                    + _wifi_rssi_to_info(item["rssi"])
                    + "; "
                    + item["capabilities"]
                )

        hass.async_run_job(
            hass.services.async_call(
                "input_select",
                "set_options",
                {
                    "entity_id": "input_select.ais_iot_devices_in_network",
                    "options": iot_names,
                },
            )
        )
        if len(iot_names) == 1:
            info = "Nie znaleziono żadnego nowego urządzenia"
        elif len(iot_names) == 2:
            if item["model"] == ais_global.G_MODEL_SONOFF_S20:
                info = "Znaleziono nowe inteligentne gniazdo"
            elif item["model"] == ais_global.G_MODEL_SONOFF_SLAMPHER:
                info = "Znaleziono nową oprawkę"
            elif item["model"] == ais_global.G_MODEL_SONOFF_TOUCH:
                info = "Znaleziono nowy przełącznik dotykowy"
            elif item["model"] == ais_global.G_MODEL_SONOFF_TH:
                info = "Znaleziono nowy przełącznik z czujnikami"
            elif item["model"] == ais_global.G_MODEL_SONOFF_B1:
                info = "Znaleziono nową żarówkę"
            elif item["model"] == ais_global.G_MODEL_SONOFF_POW:
                info = "Znaleziono nowy przełącznik z pomiarem mocy"
            elif item["model"] == ais_global.G_MODEL_SONOFF_DUAL:
                info = "Znaleziono nowy podwójny przełącznik"
            elif item["model"] == ais_global.G_MODEL_SONOFF_BASIC:
                info = "Znaleziono nowy przełącznik"
            elif item["model"] == ais_global.G_MODEL_SONOFF_IFAN:
                info = "Znaleziono nowy wentylator sufitowy"
            elif item["model"] == ais_global.G_MODEL_SONOFF_T11:
                info = "Znaleziono nowy przełącznik dotykowy pojedynczy"
            elif item["model"] == ais_global.G_MODEL_SONOFF_T12:
                info = "Znaleziono nowy przełącznik dotykowy podwójny"
            elif item["model"] == ais_global.G_MODEL_SONOFF_T13:
                info = "Znaleziono nowy przełącznik dotykowy potrójny"
            else:
                info = "Znaleziono nowe inteligentne urządzenie"
        else:
            info = "Znaleziono " + str(len(iot_names) - 1) + " nowe urządzenia"

        # check if we are doing this from remote
        if (
                len(iot_names) > 1
                and CURR_ENTITIE
                in (
                "sensor.ais_connect_iot_device_info",
                "script.ais_scan_iot_devices_in_network",
        )
                and CURR_BUTTON_CODE == 23
        ):
            info = (
                    info
                    + ". Sprawdź wszystkie parametry, naciśnij strzałkę w prawo, by przejść dalej. "
                      "Na koniec uruchom: Dołącz nowe urządzenie."
            )
            # prepare form data
            set_curr_entity(hass, "script.ais_scan_iot_devices_in_network")
            hass.async_run_job(
                hass.services.async_call(
                    "input_select",
                    "select_next",
                    {"entity_id": "input_select.ais_iot_devices_in_network"},
                )
            )
        _say_it(hass, info)
        return
    elif service.data["topic"] == "ais/wifi_status_info":
        _publish_wifi_status(hass, service)
        return
    elif service.data["topic"] == "ais/ais_gate_req_answer":
        cci = json.loads(service.data["payload"])
        ais_global.set_ais_gate_req(cci["req_id"], cci["req_answer"])
        return
    elif service.data["topic"] == "ais/wifi_connection_info":
        # current connection info
        cci = json.loads(service.data["payload"])
        attr = {
            "friendly_name": "Prędkość połączenia",
            "unit_of_measurement": "MB",
            "icon": "mdi:speedometer",
        }
        desc = ""
        speed = 0
        if "ais_gate_id" in cci:
            pass
            # ais_global.G_AIS_SECURE_ANDROID_ID_DOM = cci["ais_gate_id"]
        if "pass" in cci:
            ais_global.set_my_wifi_pass(cci["pass"])
        if "ssid" in cci:
            ais_global.set_my_ssid(cci["ssid"])
            attr["ssid"] = cci["ssid"]
            if cci["ssid"] == "<unknown ssid>":
                desc += "brak informacji o połączeniu"
            else:
                desc += cci["ssid"]
                if "link_speed_mbps" in cci:
                    desc += (
                            "; prędkość: "
                            + str(cci["link_speed_mbps"])
                            + " megabitów na sekundę"
                    )
                    attr["link_speed_mbps"] = cci["link_speed_mbps"]
                    speed = cci["link_speed_mbps"]
                if "rssi" in cci:
                    desc += "; " + _wifi_rssi_to_info(cci["rssi"])
                    attr["rssi"] = cci["rssi"]
                if "frequency_mhz" in cci:
                    desc += "; " + _wifi_frequency_info(cci["frequency_mhz"])
                    attr["frequency_mhz"] = cci["frequency_mhz"]
        attr["description"] = desc
        hass.states.async_set(
            "sensor.ais_wifi_service_current_network_info", speed, attr
        )
        return
    elif service.data["topic"] == "ais/wifi_state_change_info":
        # current connection info
        cci = json.loads(service.data["payload"])
        ais_global.set_my_ssid(cci["ssid"])
        # check if we are now online
        if ais_global.GLOBAL_MY_IP == "127.0.0.1":
            ais_global.set_global_my_ip(None)
            if ais_global.GLOBAL_MY_IP != "127.0.0.1":
                pass
                # if yes then try to reload the cloud and other components
                # TODO reload invalid components
                # hass.async_run_job(async_load_platform(hass, 'sun', 'sun', {}, {}))
                # hass.async_run_job(async_load_platform(hass, 'ais_cloud', 'ais_cloud', {}, {}))
                # hass.async_run_job(async_load_platform(hass, 'ais_yt_service', 'ais_yt_service', {}, {}))
                # hass.async_run_job(async_load_platform(hass, 'ais_knowledge_service', 'ais_knowledge_service'...
        return
    elif service.data["topic"] == "ais/go_to_player":
        go_to_player(hass, False)
    elif service.data["topic"] == "ais/ip_state_change_info":
        pl = json.loads(service.data["payload"])
        ais_global.set_global_my_ip(pl["ip"])
        icon = "mdi:access-point-network"
        friendly_name = "Lokalny adres IP"
        if "type" in pl:
            # see android ConnectivityManager
            if type == "-1":
                # TYPE_NONE
                icon = "mdi:lan-disconnect"
                friendly_name = "Lokalny adres IP - "
            elif type == "9":
                # TYPE_ETHERNET
                icon = "mdi:ethernet"
                friendly_name = "Lokalny adres IP (ethernet)"
            elif type == "1":
                # TYPE_WIFI
                icon = "mdi:wifi-strength-4-lock"
                friendly_name = "Lokalny adres IP (wifi)"

        hass.states.async_set(
            "sensor.internal_ip_address",
            pl["ip"],
            {"friendly_name": friendly_name, "icon": icon},
        )
    elif service.data["topic"] == "ais/player_status":
        # try to get current volume
        try:
            message = json.loads(service.data["payload"])
            ais_global.G_AIS_DAY_MEDIA_VOLUME_LEVEL = (
                    message.get("currentVolume", 0) / 100
            )
        except Exception:
            _LOGGER.info(
                "ais_global.G_AIS_DAY_MEDIA_VOLUME_LEVEL: "
                + str(ais_global.G_AIS_DAY_MEDIA_VOLUME_LEVEL)
            )
        if "ais_gate_client_id" in service.data:
            json_string = json.dumps(service.data["payload"])
        else:
            json_string = service.data["payload"]

        hass.async_run_job(
            hass.services.async_call(
                "media_player",
                "play_media",
                {
                    "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                    "media_content_type": "exo_info",
                    "media_content_id": json_string,
                },
            )
        )
    elif service.data["topic"] == "ais/execute_script":
        hass.services.call(
            "ais_shell_command", "execute_script", {"script": service.data["payload"]}
        )

    elif service.data["topic"] == "ais/tts_voice":
        # this is done only once on start to set the voice on hass from android
        voice = service.data["payload"]
        set_voice = "Jola lokalnie"
        if voice == "pl-pl-x-oda-network":
            set_voice = "Jola online"
        elif voice == "pl-pl-x-oda#female_1-local":
            set_voice = "Celina"
        elif voice == "pl-pl-x-oda#female_2-local":
            set_voice = "Anżela"
        elif voice == "pl-pl-x-oda#female_3-local":
            set_voice = "Asia"
        elif voice == "pl-pl-x-oda#male_1-local":
            set_voice = "Sebastian"
        elif voice == "pl-pl-x-oda#male_2-local":
            set_voice = "Bartek"
        elif voice == "pl-pl-x-oda#male_3-local":
            set_voice = "Andrzej"

        current_voice = hass.states.get("input_select.assistant_voice").state
        if current_voice != set_voice:
            # we will inform the frame about change in EVENT_STATE_CHANGED listener
            hass.async_run_job(
                hass.services.async_call(
                    "input_select",
                    "select_option",
                    {"entity_id": "input_select.assistant_voice", "option": set_voice},
                )
            )
        else:
            # EVENT_STATE_CHANGED listener will not notice this change - publish info to frame about voice
            hass.services.call(
                "ais_ai_service",
                "publish_command_to_frame",
                {"key": "setTtsVoice", "val": voice},
            )

    elif service.data["topic"] == "ais/trim_memory":
        _LOGGER.warning("trim_memory " + str(service.data["payload"]))
        try:
            import os

            if str(service.data["payload"]) == "15":
                # TRIM_MEMORY_RUNNING_CRITICAL
                tot_m, used_m, free_m = map(
                    int, os.popen("free -t -m").readlines()[-1].split()[1:]
                )
                _LOGGER.warning(
                    "TRIM_MEMORY_RUNNING_CRITICAL, used memory: " + str(used_m)
                )
                # check if we can clear database
                if "dbUrl" in ais_global.G_DB_SETTINGS_INFO:
                    if ais_global.G_DB_SETTINGS_INFO["dbUrl"].startswith(
                            "sqlite:///:memory:"
                    ):
                        _LOGGER.warning("recorder -> purge keep_days: 0")
                        hass.services.call(
                            "recorder", "purge", {"keep_days": 0, "repack": True}
                        )
                else:
                    # try to kill some heavy process
                    # Get List of all running process sorted by Highest Memory Usage
                    list_of_proc_objects = []
                    # Iterate over the list
                    for proc in psutil.process_iter():
                        try:
                            # Fetch process details as dict
                            pinfo = proc.as_dict(attrs=["pid", "name", "username"])
                            pinfo["vms"] = proc.memory_info().vms / (1024 * 1024)
                            # Append dict to list
                            list_of_proc_objects.append(pinfo)
                        except (
                                psutil.NoSuchProcess,
                                psutil.AccessDenied,
                                psutil.ZombieProcess,
                        ):
                            pass
                    # Sort list of dict by key vms i.e. memory usage
                    list_of_proc_objects = sorted(
                        list_of_proc_objects,
                        key=lambda proc_obj: proc_obj["vms"],
                        reverse=True,
                    )
                    # print top 5 process by memory usage
                    for elem in list_of_proc_objects[:5]:
                        _LOGGER.error("We should kill: " + str(elem))

        except Exception as e:
            pass

    elif service.data["topic"] == "ais/trim_storage":
        _LOGGER.warning("trim_storage " + str(service.data["payload"]))
        _LOGGER.warning("ACTION_DEVICE_STORAGE_LOW report form Android")
        # check if we can clear database
        if hass.services.has_service("recorder", "purge"):
            _LOGGER.warning("recorder -> purge keep_days: 0")
            hass.services.call("recorder", "purge", {"keep_days": 0, "repack": True})
            _LOGGER.warning("ais -> flush_logs")
            hass.services.call("ais_shell_command", "flush_logs")
    elif service.data["topic"] == "ais/sip_event":
        event_data = {"event": str(service.data["payload"])}
        hass.bus.fire("ais_sip_event", event_data)
        _LOGGER.info("sip_event " + str(event_data))
    else:
        # TODO process this without mqtt
        # player_status and speech_status
        mqtt.async_publish(hass, service.data["topic"], service.data["payload"], 2)
        # TODO
    return


def _post_message(
        message,
        hass,
        exclude_say_it=None,
        pitch=None,
        rate=None,
        language=None,
        voice=None,
        path=None,
):
    """Post the message to TTS service."""
    j_data = {
        "text": message,
        "pitch": pitch if pitch is not None else ais_global.GLOBAL_TTS_PITCH,
        "rate": rate if rate is not None else ais_global.GLOBAL_TTS_RATE,
        "language": language if language is not None else "pl_PL",
        "voice": voice if voice is not None else ais_global.GLOBAL_TTS_VOICE,
        "path": path if path is not None else "",
    }

    tts_browser_text = message
    if len(tts_browser_text) > 250:
        space_position = tts_browser_text.find(" ", 250)
        if space_position > 250:
            tts_browser_text = tts_browser_text[0:space_position]
        else:
            tts_browser_text = tts_browser_text[0:250]

    hass.async_add_job(
        hass.services.async_call(
            "ais_ai_service", "say_in_browser", {"text": tts_browser_text}
        )
    )
    try:
        requests.post(
            ais_global.G_HTTP_REST_SERVICE_BASE_URL.format("127.0.0.1")
            + "/text_to_speech",
            json=j_data,
            timeout=1,
        )
    except Exception as e:
        pass


def _beep_it(hass, tone):
    """Post the beep to Android frame."""
    # https://android.googlesource.com/platform/frameworks/base/+/b267554/media/java/android/media/ToneGenerator.java
    hass.services.call(
        "ais_ai_service", "publish_command_to_frame", {"key": "tone", "val": tone}
    )


def _say_it(
        hass,
        message,
        img=None,
        exclude_say_it=None,
        pitch=None,
        rate=None,
        language=None,
        voice=None,
        path=None,
):
    # sent the tts message to the panel via http api
    message = message.replace("°C", "stopni Celsjusza")
    _post_message(
        message=message,
        hass=hass,
        exclude_say_it=exclude_say_it,
        pitch=pitch,
        rate=rate,
        language=language,
        voice=voice,
        path=path,
    )

    if len(message) > 1999:
        tts_text = message[0:1999] + "..."
    else:
        tts_text = message + " "
    if img is not None:
        tts_text = tts_text + " \n\n" + "![Zdjęcie](" + img + ")"
    if len(message) > 100:
        hass.states.async_set(
            "sensor.aisknowledgeanswer", message[0:100] + "...", {"text": tts_text}
        )
    else:
        hass.states.async_set("sensor.aisknowledgeanswer", message, {"text": tts_text})


def _create_matcher(utterance):
    """Create a regex that matches the utterance."""
    # Split utterance into parts that are type: NORMAL, GROUP or OPTIONAL
    # Pattern matches (GROUP|OPTIONAL): Change light to [the color] {item}
    parts = re.split(r"({\w+}|\[[\w\s]+\] *)", utterance)
    # Pattern to extract name from GROUP part. Matches {item}
    group_matcher = re.compile(r"{(\w+)}")
    # Pattern to extract text from OPTIONAL part. Matches [the color]
    optional_matcher = re.compile(r"\[([\w ]+)\] *")

    pattern = ["^"]
    for part in parts:
        group_match = group_matcher.match(part)
        optional_match = optional_matcher.match(part)

        # Normal part
        if group_match is None and optional_match is None:
            pattern.append(part)
            continue

        # Group part
        if group_match is not None:
            pattern.append(fr"(?P<{group_match.groups()[0]}>[\w ]+?)\s*")

        # Optional part
        elif optional_match is not None:
            pattern.append(fr"(?:{optional_match.groups()[0]} *)?")

    pattern.append("$")
    return re.compile("".join(pattern), re.I)


def _process_code(hass, data):
    """Process a code from remote."""
    global CURR_BUTTON_CODE
    global CURR_BUTTON_LONG_PRESS
    global CURR_ENTITIE_ENTERED
    global CURR_REMOTE_MODE_IS_IN_AUDIO_MODE
    if "Action" not in data or "KeyCode" not in data:
        return
    action = data["Action"]
    code = data["KeyCode"]

    if "onDisplay" in data:
        # set the code in global variable
        CURR_BUTTON_CODE = code
        # show the code in web app
        hass.states.set("binary_sensor.ais_remote_button", code)
        event_data = {"action": action, "code": code, "long": CURR_BUTTON_LONG_PRESS}
        hass.bus.fire("ais_key_event", event_data)
        return

    # fix - when the mouse mode on remote is on, the remote is sending only the code 23 (OK) as key down (action 0)
    # to handle this we are ignoring the key up (action 1), and key down (action 0) is changing to key up (action 1)
    if code == 23:
        if action == 1:
            return
        else:
            action = 1

    # ACTION_DOWN = 0; ACTION_UP = 1;
    if action == 0:
        CURR_BUTTON_LONG_PRESS = False
        if "RepeatCount" in data:
            if data["RepeatCount"] > 0:
                CURR_BUTTON_LONG_PRESS = True
        if CURR_BUTTON_LONG_PRESS is False:
            return

    elif action == 2:
        # ACTION_MULTIPLE = 2;
        _LOGGER.debug("long press on " + str(data))
        return

    elif action == 1:
        # ACTION_UP
        # to prevent up action after long press
        if CURR_BUTTON_LONG_PRESS is True:
            CURR_BUTTON_LONG_PRESS = False

    # set the code in global variable
    CURR_BUTTON_CODE = code
    # show the code in web app
    hass.states.set("binary_sensor.ais_remote_button", code)
    event_data = {"action": action, "code": code, "long": CURR_BUTTON_LONG_PRESS}
    hass.bus.fire("ais_key_event", event_data)

    # remove selected action
    remove_selected_action(code)

    # decode Key Events
    # codes according to android.view.KeyEvent
    if code == 93:
        # PG- -> KEYCODE_PAGE_DOWN
        set_bookmarks_curr_group(hass)
        set_curr_entity(hass, "sensor.aisbookmarkslist")
        CURR_ENTITIE_ENTERED = True
        say_curr_entity(hass)
    elif code == 92:
        # PG+ -> KEYCODE_PAGE_UP
        set_favorites_curr_group(hass)
        CURR_ENTITIE_ENTERED = True
        # go to bookmarks
        set_curr_entity(hass, "sensor.aisfavoriteslist")

        say_curr_entity(hass)
    elif code == 4:
        # Back arrow, go up in menu/groups -> KEYCODE_BACK
        # or go up in local folder structure
        go_up_in_menu(hass)
    elif code == 82:
        # Menu -> KEYCODE_MENU
        set_next_group_view()
        say_curr_group_view(hass)
    elif code == 164:
        # Mute -> KEYCODE_VOLUME_MUTE
        pass
    elif code == 71:
        # MIC DOWN -> KEYCODE_LEFT_BRACKET
        pass
    elif code == 72:
        # MIC UP -> KEYCODE_RIGHT_BRACKET
        pass
    elif code == 19:
        # Dpad up -> KEYCODE_DPAD_UP
        set_on_dpad_up(hass, CURR_BUTTON_LONG_PRESS)
        pass
    elif code == 20:
        # Dpad down -> KEYCODE_DPAD_DOWN
        set_on_dpad_down(hass, CURR_BUTTON_LONG_PRESS)
        pass
    elif code == 21:
        # Dpad left -> KEYCODE_DPAD_LEFT
        set_focus_on_prev_entity(hass, CURR_BUTTON_LONG_PRESS)
    elif code == 22:
        # Dpad right -> KEYCODE_DPAD_RIGHT
        set_focus_on_next_entity(hass, CURR_BUTTON_LONG_PRESS)
    elif code == 23:
        # Dpad center -> KEYCODE_DPAD_CENTER
        select_entity(hass, CURR_BUTTON_LONG_PRESS)
    elif code == 25:
        # Volume down -> KEYCODE_VOLUME_DOWN
        pass
    elif code == 24:
        # Volume up -> KEYCODE_VOLUME_UP
        pass
    # button to switch from dom to audio, 190 - legacy button_3, new 170 - tv
    elif code == 190 or code == 170:
        # go home -> KEYCODE_HOME
        if CURR_BUTTON_LONG_PRESS:
            go_to_player(hass, True)
        else:
            # toggle mode
            if CURR_REMOTE_MODE_IS_IN_AUDIO_MODE:
                go_home(hass)
            else:
                go_to_player(hass, True)

    # other code on text field
    else:
        type_to_input_text(hass, code)


def get_context_suffix(hass):
    context_suffix = GROUP_ENTITIES[get_curr_group_idx()]["context_suffix"]
    if context_suffix == "Muzyka":
        context_suffix = hass.states.get("input_select.ais_music_service").state
    return context_suffix


async def _async_process(hass, text, calling_client_id=None, hot_word_on=False):
    """Process a line of text."""
    global CURR_VIRTUAL_KEYBOARD_VALUE
    # clear text
    text = text.replace("&", "and")
    text = text.replace("-", " ").lower()
    # check if the text input is selected
    #  binary_sensor.selected_entity / binary_sensor.ais_remote_button
    if CURR_ENTITIE_ENTERED and CURR_ENTITIE is not None:
        if CURR_ENTITIE.startswith("input_text."):
            await hass.services.async_call(
                "input_text", "set_value", {"entity_id": CURR_ENTITIE, "value": text}
            )
            # return response to the hass conversation
            ir = intent.IntentResponse()
            ir.async_set_speech("wpisano w pole tekst: " + text)
            CURR_VIRTUAL_KEYBOARD_VALUE = text
            ir.hass = hass
            return ir

    global CURR_BUTTON_CODE
    s = False
    m = None
    m_org = None
    found_intent = None

    # async_initialize ha agent
    ha_agent = hass.data.get("ha_conversation_agent")
    if ha_agent is None:
        ha_agent = hass.data["ha_conversation_agent"] = DefaultAgent(hass)
        await ha_agent.async_initialize(hass.data.get("conversation_config"))

    # 1. first check the conversation intents
    conv_intents = hass.data.get("conversation", {})
    for intent_type, matchers in conv_intents.items():
        for matcher in matchers:
            match = matcher.match(text)
            if not match:
                continue
            response = await hass.helpers.intent.async_handle(
                "conversation",
                intent_type,
                {key: {"value": value} for key, value in match.groupdict().items()},
                text,
            )
            return response

    # 2. check the user automatons intents
    if ais_global.G_AUTOMATION_CONFIG is not None:
        automations = {
            state.entity_id: state.name
            for state in hass.states.async_all()
            if state.entity_id.startswith("automation")
               and not state.entity_id.startswith("automation.ais_")
        }

    for key, value in automations.items():
        if value.lower().startswith("jolka"):
            # get aliases
            all_commands = []
            for auto_config in ais_global.G_AUTOMATION_CONFIG:
                if isinstance(auto_config, AutomationConfig):
                    auto_name = auto_config.get("alias", "").lower().strip()
                    if (
                            "description" in auto_config
                            and auto_name == value.lower().strip()
                    ):
                        all_commands = auto_config.get("description", "").split(";")
                if isinstance(auto_config, BlueprintInputs):
                    blueprint_inputs = auto_config
                    raw_blueprint_inputs = blueprint_inputs.config_with_inputs
                    auto_name = raw_blueprint_inputs.get("alias", "").lower().strip()
                    if (
                            "description" in raw_blueprint_inputs
                            and auto_name == value.lower().strip()
                    ):
                        all_commands = raw_blueprint_inputs.get(
                            "description", ""
                        ).split(";")

                all_commands = [
                    each_string.strip().lower() for each_string in all_commands
                ]

            all_commands.append(
                value.lower().replace("jolka", "", 1).replace(":", "").strip()
            )
            text_command = text.lower().replace("jolka", "", 1).replace(":", "").strip()
            if text_command in all_commands:
                await hass.services.async_call(
                    "automation", "trigger", {ATTR_ENTITY_ID: key}
                )
                s = True
                found_intent = "AUTO"
                m = "DO_NOT_SAY OK"
                break

    # 3. check the AIS dom intents
    if s is False:
        intents = hass.data.get(DOMAIN, {})
        try:
            for intent_type, matchers in intents.items():
                if found_intent is not None:
                    break
                for matcher in matchers:
                    match = matcher.match(text)
                    if match:
                        # we have a match
                        found_intent = intent_type
                        m, s = await hass.helpers.intent.async_handle(
                            DOMAIN,
                            intent_type,
                            {
                                key: {"value": value}
                                for key, value in match.groupdict().items()
                            },
                            text,
                        )
                        break
            # the item was match as INTENT_TURN_ON but we don't have such device - maybe it is radio or podcast???
            if s is False and found_intent == INTENT_TURN_ON:
                m_org = m
                m, s = await hass.helpers.intent.async_handle(
                    DOMAIN,
                    INTENT_PLAY_RADIO,
                    {key: {"value": value} for key, value in match.groupdict().items()},
                    text.replace("włącz", "włącz radio"),
                )
                if s is False:
                    m, s = await hass.helpers.intent.async_handle(
                        DOMAIN,
                        INTENT_PLAY_PODCAST,
                        {
                            key: {"value": value}
                            for key, value in match.groupdict().items()
                        },
                        text.replace("włącz", "włącz podcast"),
                    )
                if s is False:
                    m = m_org
            # the item was match as INTENT_TURN_ON but we don't have such device - maybe it is climate???
            if s is False and found_intent == INTENT_TURN_ON and "ogrzewanie" in text:
                m_org = m
                m, s = await hass.helpers.intent.async_handle(
                    DOMAIN,
                    INTENT_CLIMATE_SET_ALL_ON,
                    {key: {"value": value} for key, value in match.groupdict().items()},
                    text,
                )
                if s is False:
                    m = m_org
            # the item was match as INTENT_TURN_OFF but we don't have such device - maybe it is climate???
            if s is False and found_intent == INTENT_TURN_OFF and "ogrzewanie" in text:
                m_org = m
                m, s = await hass.helpers.intent.async_handle(
                    DOMAIN,
                    INTENT_CLIMATE_SET_ALL_OFF,
                    {key: {"value": value} for key, value in match.groupdict().items()},
                    text,
                )
                if s is False:
                    m = m_org

            # 4. the was no match - try again but with current context
            # only if hot word is disabled
            if found_intent is None and hot_word_on is False:
                suffix = get_context_suffix(hass)
                if suffix is not None:
                    for intent_type, matchers in intents.items():
                        if found_intent is not None:
                            break
                        for matcher in matchers:
                            match = matcher.match(suffix + " " + text)
                            if match:
                                # we have a match
                                found_intent = intent_type
                                m, s = await hass.helpers.intent.async_handle(
                                    DOMAIN,
                                    intent_type,
                                    {
                                        key: {"value": value}
                                        for key, value in match.groupdict().items()
                                    },
                                    suffix + " " + text,
                                )
                                # reset the curr button code
                                # TODO the mic should send a button code too
                                # in this case we will know if the call source
                                CURR_BUTTON_CODE = 0
                                break
            # 5. ask cloud
            if s is False or found_intent is None:
                # no success - try to ask the cloud
                if m is None:
                    # no message / no match
                    m = "Nie rozumiem " + text
                # asking without the suffix
                if text != "":
                    ws_resp = aisCloudWS.ask(text, m)
                    m = ws_resp.text.split("---")[0]
                else:
                    m = "Co proszę? Nic nie słyszę!"

        except Exception as e:
            _LOGGER.info("_process: " + str(e))
            m = "Przepraszam, ale mam problem ze zrozumieniem: " + text
    # return response to the ais dom
    if m.startswith("DO_NOT_SAY"):
        m = m.replace("DO_NOT_SAY", "")
    else:
        _say_it(hass, m, exclude_say_it=calling_client_id)
    # return response to the hass conversation
    intent_resp = intent.IntentResponse()
    intent_resp.async_set_speech(m)
    intent_resp.hass = hass
    return intent_resp


@core.callback
def _match_entity(hass, name, domain=None):
    """Match a name to an entity."""
    from fuzzywuzzy import process as fuzzy_extract

    if domain is not None:
        # entities = hass.states.async_entity_ids(domain)
        entities = {
            state.entity_id: state.name
            for state in hass.states.async_all()
            if state.entity_id.startswith(domain)
        }
    else:
        entities = {state.entity_id: state.name for state in hass.states.async_all()}

    try:
        entity_id = fuzzy_extract.extractOne(name, entities, score_cutoff=86)[2]
    except Exception as e:
        entity_id = None

    if entity_id is not None:
        return hass.states.get(entity_id)
    else:
        return None


class TurnOnIntent(intent.IntentHandler):
    """Handle turning item on intents."""

    intent_type = INTENT_TURN_ON
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle turn on intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["item"]["value"]
        entity = _match_entity(hass, name)
        success = False

        if not entity:
            message = "Nie znajduję urządzenia do włączenia, o nazwie: " + name
        else:
            # check if we can turn_on on this device
            if is_switch(entity.entity_id):
                assumed_state = entity.attributes.get(ATTR_ASSUMED_STATE, False)
                if assumed_state is False:
                    if entity.state == "on":
                        # check if the device is already on
                        message = "Urządzenie " + name + " jest już włączone"
                    elif entity.state == "unavailable":
                        message = "Urządzenie " + name + " jest niedostępne"
                    else:
                        assumed_state = True
                if assumed_state:
                    await hass.services.async_call(
                        core.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity.entity_id}
                    )
                    message = f"OK, włączono {entity.name}"
                success = True
            else:
                message = "Urządzenia " + name + " nie można włączyć"
        return message, success


class TurnOffIntent(intent.IntentHandler):
    """Handle turning item off intents."""

    intent_type = INTENT_TURN_OFF
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle turn off intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["item"]["value"]
        entity = _match_entity(hass, name)
        success = False
        if not entity:
            msg = "Nie znajduję urządzenia do wyłączenia, o nazwie: " + name
        else:
            # check if we can turn_off on this device
            if is_switch(entity.entity_id):
                assumed_state = entity.attributes.get(ATTR_ASSUMED_STATE, False)
                if assumed_state is False:
                    # check if the device is already off
                    if entity.state == "off":
                        msg = f"Urządzenie {entity.name} jest już wyłączone"
                    elif entity.state == "unavailable":
                        msg = f"Urządzenie {entity.name} jest niedostępne"
                    else:
                        assumed_state = True
                if assumed_state:
                    await hass.services.async_call(
                        core.DOMAIN,
                        SERVICE_TURN_OFF,
                        {ATTR_ENTITY_ID: entity.entity_id},
                    )
                    msg = f"OK, wyłączono {entity.name}"
                    success = True
            else:
                msg = "Urządzenia " + name + " nie można wyłączyć"
        return msg, success


class ToggleIntent(intent.IntentHandler):
    """Handle toggle item intents."""

    intent_type = INTENT_TOGGLE
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle toggle intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["item"]["value"]
        entity = _match_entity(hass, name)
        success = False
        if not entity:
            msg = f"Nie znajduję urządzenia do przełączenia, o nazwie: {name}"
        else:
            # check if we can toggle this device
            if not hass.services.has_service(entity.domain, SERVICE_TOGGLE):
                msg = f"Urządzenia {entity.name}  nie można przełączyć"

            elif entity.state == "unavailable":
                msg = f"Urządzenie {entity.name} jest niedostępne"
                success = True
            else:
                await hass.services.async_call(
                    entity.domain, SERVICE_TOGGLE, {ATTR_ENTITY_ID: entity.entity_id}
                )
                msg = f"OK, przełączono {entity.name}"
                success = True

        return msg, success


class StatusIntent(intent.IntentHandler):
    """Handle status item on intents."""

    intent_type = INTENT_STATUS
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle status intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["item"]["value"]
        entity = _match_entity(hass, name)
        success = False

        if not entity:
            message = "Nie znajduję informacji o: " + name
            success = False
        else:
            unit = entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            state = translate_state(entity)
            if unit is None:
                value = state
            else:
                value = f"{state} {unit}"
            message = format(entity.name) + ": " + value
            success = True
        return message, success


class SpellStatusIntent(intent.IntentHandler):
    """Handle spell status item on intents."""

    intent_type = INTENT_SPELL_STATUS
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle status intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["item"]["value"]
        entity = _match_entity(hass, name)
        success = False

        if not entity:
            message = "; ".join(name)
            success = True
        else:
            unit = entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            state = translate_state(entity)
            if unit is None:
                value = state
            else:
                value = f"{state} {unit}"
            message = "; ".join(value)
            success = True
        return message, success


class PlayRadioIntent(intent.IntentHandler):
    """Handle PlayRadio intents."""

    intent_type = INTENT_PLAY_RADIO
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        success = False
        station = None
        try:
            item = slots["item"]["value"]
            station = item
        except Exception:
            pass
        if station is None:
            message = "Powiedz jaką stację mam włączyć"
        else:
            ws_resp = aisCloudWS.audio(
                station, ais_global.G_AN_RADIO, intent_obj.text_input
            )
            json_ws_resp = ws_resp.json()
            json_ws_resp["media_source"] = ais_global.G_AN_RADIO
            name = json_ws_resp["name"]
            if len(name.replace(" ", "")) == 0:
                message = "Niestety nie znajduję radia " + station
            else:
                await hass.services.async_call("ais_cloud", "play_audio", json_ws_resp)
                message = "OK, gramy radio " + name
                success = True
        return message, success


class AisPlayPodcastIntent(intent.IntentHandler):
    """Handle Podcast intents."""

    intent_type = INTENT_PLAY_PODCAST
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"]
        success = False

        if not item:
            message = "Nie wiem jaką audycję chcesz posłuchać."
        else:
            ws_resp = aisCloudWS.audio(
                item, ais_global.G_AN_PODCAST, intent_obj.text_input
            )
            json_ws_resp = ws_resp.json()
            json_ws_resp["media_source"] = ais_global.G_AN_PODCAST
            name = json_ws_resp["name"]
            if len(name.replace(" ", "")) == 0:
                message = "Niestety nie znajduję podcasta " + item
            else:
                await hass.services.async_call("ais_cloud", "play_audio", json_ws_resp)
                message = "OK, pobieram odcinki audycji " + item
                success = True
        return message, success


class AisPlayYtMusicIntent(intent.IntentHandler):
    """Handle Music intents."""

    intent_type = INTENT_PLAY_YT_MUSIC
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"]
        success = False

        if not item:
            message = "Nie wiem jaką muzykę mam szukać "
        else:
            await hass.services.async_call("ais_yt_service", "search", {"query": item})
            # switch UI to YT
            await hass.services.async_call(
                "ais_ai_service", "set_context", {"text": "YouTube"}
            )
            #
            message = "OK, szukam na YouTube " + item
            success = True
        return message, success


class AisPlaySpotifyIntent(intent.IntentHandler):
    """Handle Music intents."""

    intent_type = INTENT_PLAY_SPOTIFY
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"]
        success = False
        # check if we have Spotify enabled
        if not hass.services.has_service("ais_spotify_service", "search"):
            message = (
                "Żeby odtwarzać muzykę z serwisu Spotify, dodaj integrację AIS Spotify. Więcej informacji "
                "znajdziesz w dokumentacji [Asystenta domowego](https://www.ai-speaker.com)"
            )
            return message, True

        if not item:
            message = "Nie wiem jaką muzykę mam szukać "
        else:
            await hass.services.async_call(
                "ais_spotify_service", "search", {"query": item}
            )
            # switch UI to Spotify
            await hass.services.async_call(
                "ais_ai_service", "set_context", {"text": "Spotify"}
            )
            #
            message = "OK, szukam na Spotify " + item
            success = True
        return message, success


class AskQuestionIntent(intent.IntentHandler):
    """Handle AskQuestion intents."""

    intent_type = INTENT_ASK_QUESTION
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"]
        question = item
        if not question:
            message = "Nie wiem o co zapytać"
            return message, False
        else:
            from homeassistant.components import ais_knowledge_service

            message = await ais_knowledge_service.async_process_ask(hass, question)
        return "DO_NOT_SAY " + message, True


class AskWikiQuestionIntent(intent.IntentHandler):
    """Handle AskWikiQuestion intents."""

    intent_type = INTENT_ASKWIKI_QUESTION
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots["item"]["value"]
        question = item
        if not question:
            message = "Nie wiem o co zapytać"
            return message, False
        else:
            from homeassistant.components import ais_knowledge_service

            message = await ais_knowledge_service.async_process_ask_wiki(hass, question)

        return "DO_NOT_SAY " + message, True


class ChangeContextIntent(intent.IntentHandler):
    """Handle ChangeContext intents."""

    intent_type = INTENT_CHANGE_CONTEXT

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        if len(GROUP_ENTITIES) == 0:
            get_groups(hass)
        text = intent_obj.text_input.lower()
        for idx, menu in enumerate(GROUP_ENTITIES, start=0):
            context_key_words = menu["context_key_words"]
            if context_key_words is not None:
                context_key_words = context_key_words.split(",")
                if text in context_key_words:
                    set_curr_group(hass, menu)
                    set_curr_entity(hass, None)
                    message = menu["context_answer"]
                    # special case spotify and youtube
                    if text == "spotify":
                        await hass.services.async_call(
                            "input_select",
                            "select_option",
                            {
                                "entity_id": "input_select.ais_music_service",
                                "option": "Spotify",
                            },
                        )
                    elif text == "youtube":
                        await hass.services.async_call(
                            "input_select",
                            "select_option",
                            {
                                "entity_id": "input_select.ais_music_service",
                                "option": "YouTube",
                            },
                        )
                    return message, True

        message = "Nie znajduję odpowiedzi do kontekstu " + text
        return message, False


class GetTimeIntent(intent.IntentHandler):
    """Handle GetTimeIntent intents."""

    intent_type = INTENT_GET_TIME

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        import babel.dates

        now = datetime.datetime.now()
        message = "Jest " + babel.dates.format_time(now, format="short", locale="pl")
        return message, True


class AisGetWeather(intent.IntentHandler):
    """Handle GetWeather intents."""

    intent_type = INTENT_GET_WEATHER

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        answer = "niestety nie wiem jaka jest pogoda"
        address = ""
        try:
            # try to do reverse_geocode
            from geopy.geocoders import Nominatim

            geolocator = Nominatim(user_agent="AIS dom")
            location = geolocator.reverse(
                query=(
                    intent_obj.hass.config.latitude,
                    intent_obj.hass.config.longitude,
                ),
                exactly_one=True,
                timeout=5,
                language="pl",
                addressdetails=True,
                zoom=10,
            )
            address = (
                    location.address.split(",")[0] + " " + location.address.split(",")[1]
            )
            command = "pogoda w miejscowości " + address
            # ask AIS
            ws_resp = aisCloudWS.ask(command, "niestety nie wiem jaka jest pogoda")
            answer = ws_resp.text.split("---")[0]
        except Exception as e:
            _LOGGER.warning(
                "Handle the intent problem for location " + address + " " + str(e)
            )

        return answer, True


class AisGetWeather48(intent.IntentHandler):
    """Handle GetWeather48 intents."""

    intent_type = INTENT_GET_WEATHER_48

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        answer = "niestety nie wiem jaka będzie pogoda"
        address = ""
        try:
            # try to do reverse_geocode
            from geopy.geocoders import Nominatim

            geolocator = Nominatim(user_agent="AIS dom")
            location = geolocator.reverse(
                query=(
                    intent_obj.hass.config.latitude,
                    intent_obj.hass.config.longitude,
                ),
                exactly_one=True,
                timeout=5,
                language="pl",
                addressdetails=True,
                zoom=10,
            )
            address = (
                    location.address.split(",")[0] + " " + location.address.split(",")[1]
            )
            command = "jaka będzie pogoda jutro w miejscowości " + address
            ws_resp = aisCloudWS.ask(command, answer)
            answer = ws_resp.text.split("---")[0]
        except Exception as e:
            _LOGGER.warning(
                "Handle the intent problem for location " + address + " " + str(e)
            )

        return answer, True


class AisLampsOn(intent.IntentHandler):
    """Handle AisLampsOn intents."""

    intent_type = INTENT_LAMPS_ON

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": "group.all_lights"}
        )
        return "ok", True


class AisLampsOff(intent.IntentHandler):
    """Handle AisLampsOff intents."""

    intent_type = INTENT_LAMPS_OFF

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": "group.all_lights"}
        )
        return "ok", True


class AisSwitchesOn(intent.IntentHandler):
    """Handle AisSwitchesOn intents."""

    intent_type = INTENT_SWITCHES_ON

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "group.all_switches"}
        )
        return "ok", True


class AisSwitchesOff(intent.IntentHandler):
    """Handle AisSwitchesOff intents."""

    intent_type = INTENT_SWITCHES_OFF

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": "group.all_switches"}
        )
        return "ok", True


class GetDateIntent(intent.IntentHandler):
    """Handle GetDateIntent intents."""

    intent_type = INTENT_GET_DATE

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        import babel.dates

        now = datetime.datetime.now()
        message = "Jest " + babel.dates.format_date(now, format="full", locale="pl")
        return message, True


class AisOpenCover(intent.IntentHandler):
    """Handle AisOpenCover intents."""

    intent_type = INTENT_OPEN_COVER
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["item"]["value"]
        entity = _match_entity(hass, name)
        success = False

        if not entity:
            message = "Nie znajduję urządzenia do otwarcia, o nazwie: " + name
        else:
            # check if we can open on this device
            if entity.entity_id.startswith("cover."):
                if entity.state == "on":
                    # check if the device is already on
                    message = "Urządzenie " + name + " jest już otwarte"
                elif entity.state == "unavailable":
                    message = "Urządzenie " + name + " jest niedostępne"
                else:
                    await hass.services.async_call(
                        "cover",
                        SERVICE_OPEN_COVER,
                        {ATTR_ENTITY_ID: entity.entity_id},
                        blocking=True,
                    )
                    message = f"OK, otwieram {entity.name}"
                success = True
            else:
                message = "Urządzenia " + name + " nie można otworzyć"
        return message, success


class AisCloseCover(intent.IntentHandler):
    """Handle AisCloseCover intents."""

    intent_type = INTENT_CLOSE_COVER
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle turn off intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["item"]["value"]
        entity = _match_entity(hass, name)
        success = False
        if not entity:
            msg = "Nie znajduję urządzenia do zamknięcia, o nazwie: " + name
        else:
            # check if we can close on this device
            if entity.entity_id.startswith("cover."):
                # check if the device is already closed
                if entity.state == "off":
                    msg = f"Urządzenie {entity.name} jest już zamknięte"
                elif entity.state == "unavailable":
                    msg = f"Urządzenie {entity.name} jest niedostępne"
                else:
                    await hass.services.async_call(
                        "cover",
                        SERVICE_CLOSE_COVER,
                        {ATTR_ENTITY_ID: entity.entity_id},
                        blocking=True,
                    )
                    msg = f"OK, zamykam {entity.name}"
                    success = True
            else:
                msg = "Urządzenia " + name + " nie można zamknąć"
        return msg, success


class AisStop(intent.IntentHandler):
    """Handle AisStop intents."""

    intent_type = INTENT_STOP

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        await hass.services.async_call(
            "media_player", "media_stop", {"entity_id": "all"}
        )
        message = "ok, stop"
        return message, True


class AisPlay(intent.IntentHandler):
    """Handle AisPlay intents."""

    intent_type = INTENT_PLAY

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        await hass.services.async_call(
            "media_player",
            "media_play",
            {ATTR_ENTITY_ID: "media_player.wbudowany_glosnik"},
        )
        message = "ok, gram"
        return message, True


class AisNext(intent.IntentHandler):
    """Handle AisNext intents."""

    intent_type = INTENT_NEXT

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        await hass.services.async_call(
            "media_player",
            "media_next_track",
            {ATTR_ENTITY_ID: "media_player.wbudowany_glosnik"},
        )
        message = "ok, następny"
        return message, True


class AisPrev(intent.IntentHandler):
    """Handle AisPrev intents."""

    intent_type = INTENT_PREV

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        await hass.services.async_call(
            "media_player",
            "media_previous_track",
            {ATTR_ENTITY_ID: "media_player.wbudowany_glosnik"},
        )
        message = "ok, poprzedni"
        return message, True


class AisSceneActive(intent.IntentHandler):
    """Handle AisSceneActive intents."""

    intent_type = INTENT_SCENE
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["item"]["value"]
        entity = _match_entity(hass, name)
        success = False

        if not entity:
            message = "Nie znajduję sceny, o nazwie: " + name
        else:
            # check if we can open on this device
            if entity.entity_id.startswith("scene."):
                await hass.services.async_call(
                    "scene", "turn_on", {ATTR_ENTITY_ID: entity.entity_id}
                )
                message = f"OK, aktywuję {entity.name}"
                success = True
            else:
                message = name + " nie można aktywować"
        return message, success


class AisRunAutomation(intent.IntentHandler):
    """Handle AisRunAutomation intents."""

    intent_type = INTENT_RUN_AUTOMATION
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["item"]["value"]
        entity = _match_entity(hass, name)
        success = False

        if not entity:
            message = "Nie znajduję automatyzacji, o nazwie: " + name
        else:
            # check if we can trigger the automation
            if entity.entity_id.startswith("automation."):
                await hass.services.async_call(
                    "automation", "trigger", {ATTR_ENTITY_ID: entity.entity_id}
                )
                message = f"OK, uruchamiam {entity.name}"
                success = True
            else:
                message = name + " nie można uruchomić"
        return message, success


class AisAskGoogle(intent.IntentHandler):
    """Handle AisAskGoogle intents."""

    intent_type = INTENT_ASK_GOOGLE
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        hass = intent_obj.hass
        command = slots["item"]["value"]

        if hass.services.has_service("ais_google_home", "command"):
            await hass.services.async_call(
                "ais_google_home", "command", {"text": command}
            )
            m = ""

        else:
            m = (
                "Żeby wysyłać komendy do serwisu Google, dodaj integrację AIS Google Home. Więcej informacji "
                "znajdziesz w dokumentacji [Asystenta domowego]("
                "https://www.ai-speaker.com/docs/ais_app_ai_integration_google_home). "
            )

        return m, True


class AisSayIt(intent.IntentHandler):
    """Handle AisSayIt intents."""

    intent_type = INTENT_SAY_IT
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        try:
            slots = self.async_validate_slots(intent_obj.slots)
            text = slots["item"]["value"]
        except Exception:
            text = None
        success = False
        if not text:
            import random

            answers = [
                "Nie wiem co mam powiedzieć?",
                "Ale co?",
                "Mówie mówie",
                "OK, dobra zaraz coś wymyślę...",
                "Mowa jest tylko srebrem",
                "To samo czy coś nowego?",
            ]
            message = random.choice(answers)
        else:
            # check if we can open on this device
            message = text
            success = True
        return message, success


class AisClimateSetTemperature(intent.IntentHandler):
    """Handle AisClimateSetTemperature intents."""

    intent_type = INTENT_CLIMATE_SET_TEMPERATURE
    slot_schema = {"temp": cv.string, "item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        try:
            hass = intent_obj.hass
            slots = self.async_validate_slots(intent_obj.slots)
            test = slots["temp"]["value"]
            name = slots["item"]["value"]
            # get name from temp
            m = re.search(r"\d+$", test)
            if m:
                temp = m.group()
                name = name + "" + test.replace(temp, "")
            else:
                temp = test

            entity = _match_entity(hass, name)
        except Exception:
            text = None
        success = False
        if not entity:
            msg = "Nie znajduję grzejnika, o nazwie: " + name
        else:
            # check if we can close on this device
            if entity.entity_id.startswith("climate."):
                # check if the device has already this temperature
                attr = hass.states.get(entity.entity_id).attributes
                if attr.get("temperature") == temp:
                    msg = "{} ma już ustawioną temperaturę {} {}".format(
                        entity.name, temp, "stopni"
                    )
                else:
                    await hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {ATTR_ENTITY_ID: entity.entity_id, "temperature": temp},
                    )
                    msg = "OK, ustawiono temperaturę {} {} w {}".format(
                        temp, "stopni", entity.name
                    )
                    success = True
            else:
                msg = "Na urządzeniu " + name + " nie można zmieniać temperatury."
        return msg, success


class AisClimateSetPresentMode(intent.IntentHandler):
    """Handle AisClimateSetPresentMode intents."""

    intent_type = INTENT_CLIMATE_SET_PRESENT_MODE
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        hass = intent_obj.hass
        mode = slots["item"]["value"]

        present_mode = ""
        if mode in ["poza domem", "za domem", "domem"]:
            # Device is in away mode
            present_mode = "away"
        elif mode in ["w domu", "domu", "dom"]:
            # Device is in home mode - No preset is active
            present_mode = "none"
        elif mode in ["eko", "eco", "oszczędzanie", "oszczędny"]:
            # Device is running an energy-saving mode
            present_mode = "eco"
        elif mode in ["podgrzanie", "podgrzewanie"]:
            # Device turn all valve full up
            present_mode = "boost"
        elif mode in ["comfort", "komfort", "wygoda"]:
            #  Device is in comfort mode
            present_mode = "comfort"
        elif mode in ["spanie", "noc"]:
            # Device is prepared for sleep
            present_mode = "sleep"
        elif mode in ["aktywność", "ruch"]:
            # Device is reacting to activity (e.g. movement sensors)
            present_mode = "activity"

        if present_mode != "":
            await hass.services.async_call(
                "climate",
                "set_preset_mode",
                {"entity_id": "all", "preset_mode": present_mode},
            )
            message = "ok, ogrzewanie w trybie " + mode
        else:
            message = "nie znajduje trybu ogrzewania " + mode
        return message, True


class AisClimateSetAllOn(intent.IntentHandler):
    """Handle AisClimateSetAllOn intents."""

    intent_type = INTENT_CLIMATE_SET_ALL_ON

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        await hass.services.async_call(
            "climate", "set_hvac_mode", {"entity_id": "all", "hvac_mode": "heat"}
        )
        message = "ok, całe ogrzewanie włączone"
        return message, True


class AisClimateSetAllOff(intent.IntentHandler):
    """Handle AisClimateSetAllOff intents."""

    intent_type = INTENT_CLIMATE_SET_ALL_OFF

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        await hass.services.async_call(
            "climate", "set_hvac_mode", {"entity_id": "all", "hvac_mode": "off"}
        )
        message = "ok, całe ogrzewanie wyłączone"
        return message, True


class PersonStatusIntent(intent.IntentHandler):
    """Handle status item on intents."""

    intent_type = INTENT_PERSON_STATUS
    slot_schema = {"item": cv.string}

    async def async_handle(self, intent_obj):
        """Handle status intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["item"]["value"]
        entity = _match_entity(hass, name, "person")
        success = False

        if not entity:
            message = "Nie znajduję lokalizacji: " + name
            success = False
        else:
            # try to get address
            address = ""
            if "source" in entity.attributes:
                try:
                    device_tracker = entity.attributes.get("source", "")
                    semsor = (
                            device_tracker.replace("device_tracker", "sensor")
                            + "_geocoded_location"
                    )
                    address = hass.states.get(semsor).state
                    if address != STATE_UNKNOWN:
                        address = ", ostatni przesłany adres to " + address
                except Exception:
                    address = ""
            if entity.state == STATE_UNKNOWN:
                location = "lokalizacja nieznana"
            elif entity.state == STATE_HOME:
                location = "jest w domu"
            elif entity.state == STATE_NOT_HOME:
                location = "jest poza domem" + address
            else:
                location = "lokalizacja " + entity.state
            message = format(entity.name) + ": " + location
            success = True
        return message, success
