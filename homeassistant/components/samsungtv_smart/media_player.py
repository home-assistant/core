"""Support for interface with an Samsung TV."""
from aiohttp import ClientConnectionError, ClientSession, ClientResponseError
from async_timeout import timeout
import asyncio
from datetime import datetime, timedelta
import json
import logging
from socket import error as socketError
from time import sleep
import voluptuous as vol
from wakeonlan import send_magic_packet
from websocket import WebSocketTimeoutException

from .api.samsungws import SamsungTVWS, ArtModeStatus
from .api.smartthings import SmartThingsTV, STStatus
from .api.upnp import upnp

from homeassistant.components.media_player import DEVICE_CLASS_TV, MediaPlayerEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.service import async_call_from_config, CONF_SERVICE_ENTITY_ID
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util import dt as dt_util, Throttle

from homeassistant.components.media_player.const import (
    MEDIA_TYPE_APP,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_URL,
    MEDIA_TYPE_VIDEO,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)

from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_API_KEY,
    CONF_BROADCAST_ADDRESS,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_ID,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    CONF_SERVICE,
    CONF_SERVICE_DATA,
    CONF_TIMEOUT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)

from . import get_token_file
from .const import (
    DOMAIN,
    CONF_APP_LAUNCH_METHOD,
    CONF_APP_LIST,
    CONF_APP_LOAD_METHOD,
    CONF_CHANNEL_LIST,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_DEVICE_OS,
    CONF_DUMP_APPS,
    CONF_POWER_ON_DELAY,
    CONF_POWER_ON_METHOD,
    CONF_SHOW_CHANNEL_NR,
    CONF_SOURCE_LIST,
    CONF_SYNC_TURN_OFF,
    CONF_SYNC_TURN_ON,
    CONF_USE_MUTE_CHECK,
    CONF_USE_ST_CHANNEL_INFO,
    CONF_USE_ST_STATUS_INFO,
    CONF_WOL_REPEAT,
    CONF_WS_NAME,
    CONF_LOGO_OPTION,
    DATA_OPTIONS,
    DEFAULT_APP,
    DEFAULT_PORT,
    DEFAULT_POWER_ON_DELAY,
    DEFAULT_SOURCE_LIST,
    DEFAULT_TIMEOUT,
    MAX_WOL_REPEAT,
    SERVICE_SELECT_PICTURE_MODE,
    SERVICE_SET_ART_MODE,
    SERVICE_REMOTE_KEY,
    STD_APP_LIST,
    WS_PREFIX,
    AppLoadMethod,
    AppLaunchMethod,
    PowerOnMethod,
)
from .logo import LOGO_OPTION_DEFAULT, Logo

ATTR_ART_MODE_STATUS = "art_mode_status"
ATTR_IP_ADDRESS = "ip_address"
ATTR_PICTURE_MODE = "picture_mode"
ATTR_PICTURE_MODE_LIST = "picture_mode_list"
ATTR_REMOTE_KEY = "key_id"

CMD_OPEN_BROWSER = "open_browser"
CMD_RUN_APP = "run_app"
CMD_RUN_APP_REMOTE = "run_app_remote"
CMD_RUN_APP_REST = "run_app_rest"
CMD_SEND_KEY = "send_key"
CMD_SEND_TEXT = "send_text"

DELAYED_SOURCE_TIMEOUT = 80
KEYHOLD_MAX_DELAY = 5.0
KEYPRESS_DEFAULT_DELAY = 0.5
KEYPRESS_MAX_DELAY = 2.0
KEYPRESS_MIN_DELAY = 0.2
MAX_ST_ERROR_COUNT = 4
MAX_ST_CONN_ERROR_COUNT = 3
MEDIA_TYPE_BROWSER = "browser"
MEDIA_TYPE_KEY = "send_key"
MEDIA_TYPE_TEXT = "send_text"
POWER_OFF_DELAY = 20
POWER_ON_DELAY = 5
ST_APP_SEPARATOR = "/"
ST_UPDATE_TIMEOUT = 5

SERVICE_TURN_OFF = "homeassistant.turn_off"
SERVICE_TURN_ON = "homeassistant.turn_on"
MAX_CONTROLLED_ENTITY = 4

MIN_TIME_BETWEEN_APP_SCANS = timedelta(seconds=60)
SUPPORT_REMOTE_KEYS= 64 #2^35, hass goes up to 2^19


SUPPORT_SAMSUNGTV_SMART = (
    SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_STOP
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
)

SUPPORT_SAMSUNGTV_TVONLY = (
    SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_REMOTE_KEYS
)

SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Samsung TV from a config entry."""

    # session used by aiohttp
    session = hass.helpers.aiohttp_client.async_get_clientsession()

    entry_id = config_entry.entry_id
    config = config_entry.data.copy()
    add_conf = hass.data[DOMAIN][config_entry.unique_id]
    for attr, value in add_conf.items():
        if value:
            config[attr] = value

    hostname = config[CONF_HOST]
    port = config.get(CONF_PORT, DEFAULT_PORT)
    token_file = get_token_file(hass, hostname, port)
    logo_file = hass.config.path(STORAGE_DIR, f"{DOMAIN}_logo_paths")

    async_add_entities(
        [SamsungTVDevice(config, entry_id, session, token_file, logo_file)], True
    )

    # register services
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_SELECT_PICTURE_MODE,
        {vol.Required(ATTR_PICTURE_MODE): cv.string},
        "async_select_picture_mode",
    )
    platform.async_register_entity_service(
        SERVICE_SET_ART_MODE,
        {},
        "async_set_art_mode",
    )
    platform.async_register_entity_service(
        SERVICE_REMOTE_KEY,
        {vol.Required(ATTR_REMOTE_KEY): cv.string},
        "remote_key",
        [SUPPORT_REMOTE_KEYS],

    )

    _LOGGER.info(
        "Samsung TV %s:%d added as '%s'",
        hostname,
        port,
        config.get(CONF_NAME, hostname),
    )


class SamsungTVDevice(MediaPlayerEntity):
    """Representation of a Samsung TV."""

    def __init__(self, config, entry_id, session: ClientSession, token_file, logo_file):
        """Initialize the Samsung device."""

        self._entry_id = entry_id
        self._session = session
        self._host = config[CONF_HOST]
        self._mac = config.get(CONF_MAC)

        # Set entity attributes
        self._attr_name = config.get(CONF_NAME, self._host)
        self._attr_unique_id = config.get(CONF_ID, entry_id)
        self._attr_icon = "mdi:television"
        self._attr_device_class = DEVICE_CLASS_TV
        self._attr_supported_features = SUPPORT_SAMSUNGTV_SMART
        self._attr_media_title = None
        self._attr_media_image_url = None

        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, self._attr_unique_id)},
            ATTR_NAME: self._attr_name,
        }
        self._attr_device_info.update(
            self._get_add_dev_info(
                config.get(CONF_DEVICE_MODEL),
                config.get(CONF_DEVICE_NAME),
                config.get(CONF_DEVICE_OS),
                self._mac,
            )
        )

        # Save a reference to the imported config
        self._broadcast = config.get(CONF_BROADCAST_ADDRESS)

        # load sources list
        self._default_source_used = False
        source_list = SamsungTVDevice._load_param_list(
            config.get(CONF_SOURCE_LIST, {})
        )
        if not source_list:
            source_list = DEFAULT_SOURCE_LIST
            self._default_source_used = True
        self._source_list = source_list

        # load apps list
        self._dump_apps = True
        app_list = SamsungTVDevice._load_param_list(
            config.get(CONF_APP_LIST)
        )
        if app_list is not None:
            double_list = SamsungTVDevice._split_app_list(app_list, "/")
            self._app_list = double_list["app"]
            self._app_list_ST = double_list["appST"]
        else:
            self._app_list = None
            self._app_list_ST = None

        # load channels list
        self._channel_list = SamsungTVDevice._load_param_list(
            config.get(CONF_CHANNEL_LIST)
        )

        self._source = None
        self._running_app = None
        # Assume that the TV is not muted and volume is 0
        self._muted = False
        self._volume = 0
        # Assume that the TV is in Play mode
        self._playing = True
        self._state = STATE_UNAVAILABLE
        # Mark the end of a shutdown command (need to wait 15 seconds before
        # sending the next command to avoid turning the TV back ON).
        self._end_of_power_off = None
        self._power_on_detected = None
        self._set_update_forced = False
        self._update_forced_time = None
        self._fake_on = None
        self._delayed_set_source = None
        self._delayed_set_source_time = None
        self._st_conn_error_count = 0

        ws_name = config.get(CONF_WS_NAME, self._attr_name)
        ws_port = config.get(CONF_PORT, DEFAULT_PORT)
        ws_timeout = config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        self._ws = SamsungTVWS(
            name=f"{WS_PREFIX} {ws_name}",  # this is the name shown in the TV list of external device.
            host=self._host,
            port=ws_port,
            timeout=ws_timeout,
            key_press_delay=KEYPRESS_DEFAULT_DELAY,
            token_file=token_file,
            app_list=self._app_list,
        )

        self._upnp = upnp(host=self._host, session=session)

        self._st = None
        api_key = config.get(CONF_API_KEY)
        device_id = config.get(CONF_DEVICE_ID)
        if api_key and device_id:
            self._st = SmartThingsTV(
                api_key=api_key,
                device_id=device_id,
                use_channel_info=True,
                session=session,
            )
            self. _attr_supported_features |= SUPPORT_SELECT_SOUND_MODE

        self._st_error_count = 0
        self._setvolumebyst = False

        self._logo_option = LOGO_OPTION_DEFAULT[0]
        self._logo = Logo(
            logo_option=self._logo_option,
            logo_file_download=logo_file,
            session=session,
        )

    @staticmethod
    def _get_add_dev_info(dev_model, dev_name, dev_os, dev_mac):
        dev_info = {ATTR_MANUFACTURER: "Samsung Electronics"}
        model = dev_model or "Samsung TV"
        if dev_name:
            model = f"{model} ({dev_name})"
        dev_info[ATTR_MODEL] = model
        if dev_os:
            dev_info[ATTR_SW_VERSION] = dev_os
        if dev_mac:
            dev_info["connections"] = {(CONNECTION_NETWORK_MAC, dev_mac)}

        return dev_info

    @staticmethod
    def _load_param_list(src_list):

        if src_list is None:
            return None
        if isinstance(src_list, dict):
            return src_list

        result = {}
        try:
            result = json.loads(src_list)
        except TypeError:
            _LOGGER.error("Invalid format parameter: %s", str(src_list))
        return result

    @staticmethod
    def _split_app_list(app_list, sep=ST_APP_SEPARATOR):
        retval = {"app": {}, "appST": {}}

        for app_name, value in app_list.items():
            value_split = value.split(sep, 1)
            app_id = value_split[0]
            if len(value_split) == 1:
                st_app_id = STD_APP_LIST.get(app_id, app_id) or app_id
            else:
                st_app_id = value_split[1]
            retval["app"][app_name] = app_id
            retval["appST"][app_name] = st_app_id

        return retval

    def _get_option(self, param, default=None):
        entry_id = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if not entry_id:
            return default
        option = entry_id[DATA_OPTIONS].get(param)
        return default if option is None else option

    def _power_off_in_progress(self):
        return (
            self._end_of_power_off is not None
            and self._end_of_power_off > dt_util.utcnow()
        )

    def _update_forced(self):
        if self._set_update_forced:
            self._update_forced_time = datetime.now()
            self._power_on_detected = datetime.min
            self._set_update_forced = False
            return False

        if not self._update_forced_time:
            return False

        call_time = datetime.now()
        difference = (call_time - self._update_forced_time).total_seconds()
        if difference >= 10:
            self._update_forced_time = None
            return False
        return True

    def _delay_power_on(self, result):
        if result and self._state == STATE_OFF:

            power_on_delay = self._get_option(
                CONF_POWER_ON_DELAY, DEFAULT_POWER_ON_DELAY
            )

            if power_on_delay > 0:
                if not self._power_on_detected:
                    self._power_on_detected = datetime.now()
                difference = (datetime.now() - self._power_on_detected).total_seconds()
                if difference < power_on_delay:
                    return False
        else:
            if self._ws.artmode_status == ArtModeStatus.On:
                self._power_on_detected = datetime.min
            else:
                self._power_on_detected = None

        return result

    async def _update_volume_info(self):
        if self._state == STATE_ON:

            # if self._st and self._setvolumebyst:
            # self._volume = self._st.volume
            # self._muted = self._st.muted
            # return

            self._volume = int(await self._upnp.async_get_volume()) / 100
            self._muted = await self._upnp.async_get_mute()

    def _ping_device(self):

        result = self._ws.ping_device()
        if result and self._st:
            use_st_status = self._get_option(CONF_USE_ST_STATUS_INFO, True)
            if (
                self._st.state == STStatus.STATE_OFF and
                self._st.prev_state != STStatus.STATE_OFF and
                self._state == STATE_ON and use_st_status
            ):
                result = False

        if result:
            self._ws.start_client()
            self._ws.get_running_app()
            if (
                self._ws.artmode_status == ArtModeStatus.On or
                self._ws.artmode_status == ArtModeStatus.Unavailable
            ):
                result = False
        else:
            self._ws.stop_client()

        return result

    async def _get_running_app(self):

        if self._app_list is not None:

            for app, app_id in self._app_list.items():
                if self._ws.running_app:
                    if app_id == self._ws.running_app:
                        self._running_app = app
                        return
                if self._st and self._st.channel_name != "":
                    st_app_id = self._app_list_ST.get(app, "")
                    if st_app_id == self._st.channel_name:
                        self._running_app = app
                        return

        self._running_app = DEFAULT_APP

    def _get_st_sources(self):
        if self._state != STATE_ON or not self._st:
            _LOGGER.debug(
                "Samsung TV is OFF or SmartThings not configured, _get_st_sources not executed"
            )
            return

        st_source_list = {}
        source_list = self._st.source_list
        if source_list:

            def get_next_name(index):
                if index >= len(source_list):
                    return ""
                next_input = source_list[index]
                if not (
                        next_input.upper() in ["DIGITALTV", "TV"]
                        or next_input.startswith("HDMI")
                ):
                    return next_input
                return ""

            for i in range(len(source_list)):
                try:
                    # SmartThings source list is an array that may contain the input or the assigned name,
                    # if we found a name that is not an input we use it as input name
                    input_name = source_list[i]
                    is_tv = input_name.upper() in ["DIGITALTV", "TV"]
                    is_hdmi = input_name.startswith("HDMI")
                    if is_tv or is_hdmi:
                        input_type = "ST_TV" if is_tv else "ST_" + input_name
                        if input_type in st_source_list.values():
                            continue

                        name = self._st.get_source_name(input_name)
                        if not name:
                            name = get_next_name(i + 1)
                        st_source_list[name or input_name] = input_type

                except Exception:
                    pass

        if len(st_source_list) > 0:
            _LOGGER.info(
                "Samsung TV: loaded sources list from SmartThings: "
                + str(st_source_list)
            )
            self._source_list = st_source_list
            self._default_source_used = False

    @Throttle(MIN_TIME_BETWEEN_APP_SCANS)
    def _gen_installed_app_list(self, **kwargs):
        """Get apps installed on TV"""

        if self._dump_apps:
            self._dump_apps = self._get_option(CONF_DUMP_APPS, False)

        if not (self._app_list is None or self._dump_apps):
            return

        app_list = self._ws.installed_app
        if not app_list:
            return

        app_load_method = AppLoadMethod(
            self._get_option(CONF_APP_LOAD_METHOD, AppLoadMethod.All.value)
        )

        # app_list is a list of dict
        filtered_app_list = {}
        filtered_app_list_st = {}
        dump_app_list = {}
        for app in app_list.values():
            try:
                app_name = app.app_name
                app_id = app.app_id
                st_app_id = STD_APP_LIST.get(app_id)
                # app_list is automatically created only with apps in hard coded short list (STD_APP_LIST)
                # other available apps are dumped in a file that can be used to create a custom list
                # this is to avoid unuseful long list that can impact performance
                if app_load_method != AppLoadMethod.NotLoad:
                    if app_id in STD_APP_LIST or app_load_method == AppLoadMethod.All:
                        filtered_app_list[app_name] = app_id
                        filtered_app_list_st[app_name] = st_app_id or app_id

                dump_app_list[app_name] = (
                    app_id + ST_APP_SEPARATOR + st_app_id
                    if st_app_id else app_id
                )

            except Exception:
                pass

        if self._app_list is None:
            self._app_list = filtered_app_list
            self._app_list_ST = filtered_app_list_st

        if self._dump_apps:
            _LOGGER.info(
                "List of available apps for SamsungTV %s: %s",
                self._attr_name,
                dump_app_list,
            )
            self._dump_apps = False

    def _get_source(self):
        """Return the current input source."""
        if self.state != STATE_ON:
            self._source = None
            return self._source

        if self._running_app != DEFAULT_APP or not self._st:
            self._source = self._running_app
            return self._source

        if self._st.state != STStatus.STATE_ON:
            self._source = self._running_app
            return self._source

        if self._st.source in ["digitalTv", "TV"]:
            cloud_key = "ST_TV"
        else:
            cloud_key = "ST_" + self._st.source

        found_source = self._running_app
        for attr, value in self._source_list.items():
            if value == cloud_key:
                found_source = attr
                break

        self._source = found_source
        return self._source

    async def _smartthings_keys(self, source_key):
        if not self._st:
            _LOGGER.error("SmartThings not configured. Command not valid: %s", source_key)
            return False
        if self._st.state != STStatus.STATE_ON:
            _LOGGER.warning("SmartThings not available. Command not sent: %s", source_key)
            return False

        if source_key.startswith("ST_HDMI"):
            await self._st.async_select_source(source_key.replace("ST_", ""))
        elif source_key == "ST_TV":
            await self._st.async_select_source("digitalTv")
        elif source_key == "ST_CHUP":
            await self._st.async_send_command("stepchannel", "up")
        elif source_key == "ST_CHDOWN":
            await self._st.async_send_command("stepchannel", "down")
        elif source_key.startswith("ST_CH"):
            ch_num = source_key.replace("ST_CH", "")
            if ch_num.isdigit():
                await self._st.async_send_command("selectchannel", ch_num)
        elif source_key == "ST_MUTE":
            await self._st.async_send_command(
                "audiomute", "off" if self._muted else "on"
            )
        elif source_key == "ST_VOLUP":
            await self._st.async_send_command("stepvolume", "up")
        elif source_key == "ST_VOLDOWN":
            await self._st.async_send_command("stepvolume", "down")
        elif source_key.startswith("ST_VOL"):
            vol_lev = source_key.replace("ST_VOL", "")
            if vol_lev.isdigit():
                await self._st.async_send_command("setvolume", vol_lev)
        else:
            _LOGGER.error("Unsupported SmartThings command: %s", source_key)
            return False
        return True

    async def async_update(self):
        """Update state of device."""

        if self._update_forced():
            return

        """Required to get source and media title"""
        if self._st:
            use_channel_info = self._get_option(CONF_USE_ST_CHANNEL_INFO, True)
            try:
                with timeout(ST_UPDATE_TIMEOUT):
                    await self._st.async_device_update(use_channel_info)
                self._st_error_count = 0
            except (
                asyncio.TimeoutError,
                ClientConnectionError,
                ClientResponseError,
            ) as ex:
                self._st_error_count += 1
                _LOGGER.debug("SamsungTV Smart - Error: [%s]", ex)

        if self._st_error_count >= MAX_ST_ERROR_COUNT:
            _LOGGER.error("SamsungTV Smart - Error refreshing from SmartThings")
            self._st_error_count = 0

        result = await self.hass.async_add_executor_job(self._ping_device)

        use_mute_check = self._get_option(CONF_USE_MUTE_CHECK, True)
        if not result:
            self._fake_on = None
        elif self._state == STATE_OFF and use_mute_check:
            first_detect = self._fake_on is None
            if first_detect or self._fake_on is True:
                is_muted = await self._upnp.async_get_mute()
                self._fake_on = is_muted or not self._upnp.connected
                if self._fake_on:
                    if first_detect:
                        _LOGGER.debug("SamsungTV Smart - Detected fake power on, status not updated")
                    result = False

        result = self._delay_power_on(result)
        # result = result and self._ws.is_connected

        if result and self._st:
            if self._st.state != self._st.state.STATE_ON:
                if self._st_conn_error_count < MAX_ST_CONN_ERROR_COUNT:
                    self._st_conn_error_count += 1
                    if self._st_conn_error_count == MAX_ST_CONN_ERROR_COUNT:
                        _LOGGER.warning(
                            "SamsungTV Smart - SmartThings connection is offline."
                            " Check connection status on the phone App"
                        )
            else:
                if self._st_conn_error_count >= MAX_ST_CONN_ERROR_COUNT:
                    _LOGGER.warning("SamsungTV Smart - SmartThings connection now is online")
                self._st_conn_error_count = 0

        self._state = STATE_ON if result else STATE_OFF

        if self.state == STATE_ON:
            if self._delayed_set_source:
                difference = (datetime.now() - self._delayed_set_source_time).total_seconds()
                if difference > DELAYED_SOURCE_TIMEOUT:
                    self._delayed_set_source = None
                else:
                    await self.async_select_source(self._delayed_set_source, False)
            await self._update_volume_info()
            await self._get_running_app()
            await self._update_media()

        if self._state == STATE_OFF:
            self._end_of_power_off = None

        if self._state == STATE_OFF:
            self._attr_supported_features = SUPPORT_TURN_ON
        else:
            if self._get_source() == "TV" or self._get_source() == "TV/HDMI":
                self._attr_supported_features = SUPPORT_SAMSUNGTV_TVONLY
            else:
                self._attr_supported_features = SUPPORT_SAMSUNGTV_SMART

    def send_command(
        self, payload, command_type=CMD_SEND_KEY, key_press_delay: float = 0, press=False
    ):
        """Send a key to the tv and handles exceptions."""
        if key_press_delay < 0:
            key_press_delay = None  # means "default" provided with constructor

        ret_val = False
        try:
            if command_type == CMD_RUN_APP:
                ret_val = self._ws.run_app(payload)
            elif command_type == CMD_RUN_APP_REMOTE:
                app_cmd = payload.split(",")
                app_id = app_cmd[0]
                action_type = ""
                if len(app_cmd) > 1:
                    action_type = app_cmd[1]
                ret_val = self._ws.run_app(app_id, action_type, "", use_remote=True)
            elif command_type == CMD_RUN_APP_REST:
                result = self._ws.rest_app_run(payload)
                _LOGGER.debug("Rest API result launching app %s: %s", payload, result)
                ret_val = True
            elif command_type == CMD_OPEN_BROWSER:
                ret_val = self._ws.open_browser(payload)
            elif command_type == CMD_SEND_TEXT:
                ret_val = self._ws.send_text(payload)
            elif command_type == CMD_SEND_KEY:
                hold_delay = 0
                source_keys = payload.split(",")
                key_code = source_keys[0]
                if len(source_keys) > 1:

                    def get_hold_time():
                        hold_time = source_keys[1].replace(" ", "")
                        if not hold_time:
                            return 0
                        if not hold_time.isdigit():
                            return 0
                        hold_time = int(hold_time)/1000
                        return min(hold_time, KEYHOLD_MAX_DELAY)

                    hold_delay = get_hold_time()

                if hold_delay > 0:
                    ret_val = self._ws.hold_key(key_code, hold_delay)
                else:
                    ret_val = self._ws.send_key(
                        key_code, key_press_delay, "Press" if press else "Click"
                    )
            else:
                _LOGGER.debug("Send command: invalid command type -> %s", command_type)

        except (ConnectionResetError, AttributeError, BrokenPipeError):
            _LOGGER.debug(
                "Error in send_command() -> ConnectionResetError/AttributeError/BrokenPipeError"
                    )

        except WebSocketTimeoutException:
            _LOGGER.debug(
                "Failed sending payload %s command_type %s",
                payload,
                command_type,
                exc_info=True,
            )

        except OSError:
            _LOGGER.debug("Error in send_command() -> OSError")

        return ret_val

    async def async_send_command(
        self, payload, command_type=CMD_SEND_KEY, key_press_delay: float = 0, press=False
    ):
        return await self.hass.async_add_executor_job(
            self.send_command, payload, command_type, key_press_delay, press
        )

    async def _update_media(self):
        logo_option_changed = False
        new_media_title = self._get_new_media_title()

        if not new_media_title:
            self._attr_media_image_url = None
            self._attr_media_title = None
            return

        _LOGGER.debug(
            "New media title is: %s, old media title is: %s, running app is: %s",
            new_media_title,
            self._attr_media_title,
            self._running_app,
        )

        new_logo_option = self._get_option(CONF_LOGO_OPTION, self._logo_option)
        if self._logo_option != new_logo_option:
            self._logo_option = new_logo_option
            self._logo.set_logo_color(new_logo_option)
            logo_option_changed = True

        if new_media_title == self._attr_media_title and not logo_option_changed:
            return

        media_image_url = await self._logo.async_find_match(new_media_title)
        self._attr_media_image_url = media_image_url
        self._attr_media_title = new_media_title

    def _get_new_media_title(self):
        if self._state != STATE_ON:
            return None

        if self._st:
            if self._st.state == STStatus.STATE_OFF:
                return None

            if self._running_app == DEFAULT_APP:
                if self._st.source in ["digitalTv", "TV"]:
                    if self._st.channel_name != "":
                        show_channel_number = self._get_option(CONF_SHOW_CHANNEL_NR, False)
                        if show_channel_number and self._st.channel != "":
                            return self._st.channel_name + " (" + self._st.channel + ")"
                        return self._st.channel_name
                    if self._st.channel != "":
                        return self._st.channel

                elif self._st.channel_name != "":
                    # the channel name holds the running app ID
                    # regardless of the self._cloud_source value
                    return self._st.channel_name

        return self._get_source()

    @property
    def media_channel(self):
        """Channel currently playing."""
        if self._state == STATE_ON:
            if self._st:
                if self._st.source in ["digitalTv", "TV"] and self._st.channel != "":
                    return self._st.channel
        return None

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        if self._state == STATE_ON:
            if self._running_app == DEFAULT_APP:
                if self.media_channel:
                    return MEDIA_TYPE_CHANNEL
                else:
                    return MEDIA_TYPE_VIDEO
            else:
                return MEDIA_TYPE_APP
        return STATE_OFF

    @property
    def app_id(self):
        """ID of the current running app."""
        if self._state == STATE_ON:
            app = None
            if self._app_list_ST and self._running_app != DEFAULT_APP:
                app = self._app_list_ST.get(self._running_app, None)
            if app:
                return app
            elif self._st:
                if not self._st.channel and self._st.channel_name:
                    return self._st.channel_name
            return DEFAULT_APP
        return None

    @property
    def state(self):
        """Return the state of the device."""

        # Warning: we assume that after a sending a power off command, the command is successful
        # so for 20 seconds (defined in POWER_OFF_DELAY) the state will be off regardless of the actual state.
        # This is to have better feedback to the command in the UI, but the logic might cause other issues in the future
        if self._power_off_in_progress():
            return STATE_OFF

        return self._state

    @property
    def source_list(self):
        """List of available input sources."""
        # try to get source list from SmartThings if a custom source list is not defined
        if self._st and self._default_source_used:
            self._get_st_sources()

        self._gen_installed_app_list()

        source_list = []
        source_list.extend(list(self._source_list))
        if self._app_list:
            source_list.extend(list(self._app_list))
        if self._channel_list:
            source_list.extend(list(self._channel_list))
        return source_list

    @property
    def channel_list(self):
        """List of available channels."""
        if self._channel_list is None:
            return None
        return list(self._channel_list)

    @property
    def source(self):
        """Return the current input source."""
        return self._get_source()

    @property
    def sound_mode(self):
        """Name of the current sound mode."""
        if self._st:
            return self._st.sound_mode
        return None

    @property
    def sound_mode_list(self):
        """List of available sound modes."""
        if self._st:
            return self._st.sound_mode_list or None
        return None

    def _send_wol_packet(self, wol_repeat=None):
        if not self._mac:
            _LOGGER.error(
                "MAC address not configured, impossible send WOL packet"
            )
            return False

        if not wol_repeat:
            wol_repeat = self._get_option(CONF_WOL_REPEAT, 1)
        wol_repeat = max(1, min(wol_repeat, MAX_WOL_REPEAT))
        ip_address = self._broadcast or "255.255.255.255"
        send_success = False
        for i in range(wol_repeat):
            if i > 0:
                sleep(0.25)
            try:
                send_magic_packet(self._mac, ip_address=ip_address)
                send_success = True
            except socketError as exc:
                _LOGGER.warning(
                    "Failed tentative n.%s to send WOL packet: %s",
                    i,
                    exc,
                )
            except (TypeError, ValueError) as exc:
                _LOGGER.error("Error sending WOL packet: %s", exc)
                return False

        return send_success

    async def _async_power_on(self, set_art_mode=False):
        """Turn the media player on."""
        cmd_power_on = "KEY_POWER"
        cmd_power_art = "KEY_POWER"
        if set_art_mode:
            if self._ws.artmode_status == ArtModeStatus.Off:
                # art mode from on
                await self.async_send_command(cmd_power_art)
                self._state = STATE_OFF
                return True

        if self._ws.artmode_status == ArtModeStatus.On:
            if set_art_mode:
                return False
            # power on from art mode
            await self.async_send_command(cmd_power_art)
            return True

        if self.state != STATE_OFF:
            return False

        result = True
        if not await self.async_send_command(cmd_power_on):
            turn_on_method = PowerOnMethod(
                self._get_option(CONF_POWER_ON_METHOD, PowerOnMethod.WOL.value)
            )

            if turn_on_method == PowerOnMethod.SmartThings and self._st:
                await self._st.async_turn_on()
            else:
                result = await self.hass.async_add_executor_job(
                    self._send_wol_packet
                )

        if result:
            self._state = STATE_OFF
            self._end_of_power_off = None
            self._ws.set_power_on_request(set_art_mode)

        return result

    async def _async_turn_on(self, set_art_mode=False):
        """Turn the media player on."""
        self._delayed_set_source = None
        if not await self._async_power_on(set_art_mode):
            return False
        if self._state == STATE_OFF:
            def update_status():
                if self._state != STATE_ON:
                    self.async_schedule_update_ha_state(True)
                    self._set_update_forced = True

            self.hass.loop.call_later(POWER_ON_DELAY, update_status)
            self._power_on_detected = datetime.min
            await self._async_switch_entity(not set_art_mode)

        return True

    async def async_turn_on(self):
        """Turn the media player on."""
        await self._async_turn_on()

    async def async_set_art_mode(self):
        """Turn the media player on setting in art mode."""
        await self._async_turn_on(True)

    def _turn_off(self):
        """Turn off media player."""
        if self._power_off_in_progress():
            return False

        cmd_power_off = "KEY_POWER"
        cmd_power_art = "KEY_POWER"
        self._ws.set_power_off_request()
        if self._state == STATE_ON:
            if self._ws.artmode_status == ArtModeStatus.Unsupported:
                self.send_command(cmd_power_off)
            else:
                self.send_command(f"{cmd_power_art},3000")
        elif self._ws.artmode_status == ArtModeStatus.On:
            self.send_command(f"{cmd_power_art},3000")
        else:
            return False

        self._end_of_power_off = dt_util.utcnow() + timedelta(
            seconds=POWER_OFF_DELAY
        )

        return True

    async def async_turn_off(self):
        """Turn the media player on."""
        result = await self.hass.async_add_executor_job(self._turn_off)
        if result:
            await self._async_switch_entity(False)

    def remote_key(self,key_id):
        """send a rc key"""
        self.send_command(key_id)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        # self._volume = int(self._upnp.get_volume()) / 100
        if self.support_volume_set:
            return self._volume
        else:
            return None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        # self._muted = self._upnp.get_mute()
        return self._muted

    def volume_up(self):
        """Volume up the media player."""
        self.send_command("KEY_VOLUP")
        if self.support_volume_set:
            self._volume = min(1.0, self._volume + 0.01)

    def volume_down(self):
        """Volume down media player."""
        self.send_command("KEY_VOLDOWN")
        if self.support_volume_set:
            self._volume = max(0.0, self._volume - 0.01)

    def mute_volume(self, mute):
        """Send mute command."""
        self.send_command("KEY_MUTE")
        if self.support_volume_set:
            self._muted = False if self._muted else True

    async def async_set_volume_level(self, volume):
        if self._st and self._setvolumebyst:
            await self._st.async_send_command("setvolume", int(volume * 100))
        else:
            await self._upnp.async_set_volume(int(volume * 100))
        self._volume = volume

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self.send_command("KEY_PLAY")

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self.send_command("KEY_PAUSE")

    def media_stop(self):
        """Send media pause command to media player."""
        self._playing = False
        self.send_command("KEY_STOP")

    def media_next_track(self):
        """Send next track command."""
        if self.media_channel:
            self.send_command("KEY_CHUP")
        else:
            self.send_command("KEY_FF")

    def media_previous_track(self):
        """Send the previous track command."""
        if self.media_channel:
            self.send_command("KEY_CHDOWN")
        else:
            self.send_command("KEY_REWIND")

    async def _async_send_keys(self, source_key):
        """Send key / chained keys."""
        prev_wait = True

        if "+" in source_key:
            all_source_keys = source_key.split("+")
            for this_key in all_source_keys:
                if this_key.isdigit():
                    prev_wait = True
                    await asyncio.sleep(
                        min(
                            max((int(this_key) / 1000), KEYPRESS_MIN_DELAY),
                            KEYPRESS_MAX_DELAY,
                        )
                    )
                else:
                    # put a default delay between key if set explicit
                    if not prev_wait:
                        await asyncio.sleep(KEYPRESS_DEFAULT_DELAY)
                    prev_wait = False
                    if this_key.startswith("ST_"):
                        await self._smartthings_keys(this_key)
                    else:
                        await self.async_send_command(this_key)

            return True

        if source_key.startswith("ST_"):
            return await self._smartthings_keys(source_key)

        return await self.async_send_command(source_key)

    async def _async_set_channel_source(self, channel_source=None):
        """Select the source for a channel."""

        if not channel_source:
            if self._running_app == DEFAULT_APP:
                return True
            _LOGGER.error("Current source invalid for channel")
            return False

        if self._source == channel_source:
            return True

        if channel_source not in self._source_list:
            _LOGGER.error("Invalid channel source: %s", channel_source)
            return False

        await self.async_select_source(channel_source)
        if self._source != channel_source:
            _LOGGER.error("Error selecting channel source: %s", channel_source)
            return False
        await asyncio.sleep(3)

        return True

    async def _async_set_channel(self, channel):
        """Set a specific channel."""

        if channel.startswith("http"):
            await self.async_play_media(MEDIA_TYPE_URL, channel)
            return True

        channel_cmd = channel.split("@")
        channel_no = channel_cmd[0]
        channel_source = None
        if len(channel_cmd) > 1:
            channel_source = channel_cmd[1]

        try:
            cv.positive_int(channel_no)
        except vol.Invalid:
            _LOGGER.error("Channel must be positive integer")
            return False

        if not await self._async_set_channel_source(channel_source):
            return False

        if self._st:
            return await self._smartthings_keys(f"ST_CH{channel_no}")

        def send_digit():
            for digit in channel_no:
                self.send_command("KEY_" + digit)
                sleep(KEYPRESS_DEFAULT_DELAY)
            self.send_command("KEY_ENTER")
        await self.hass.async_add_executor_job(send_digit)
        return True

    async def _async_launch_app(self, app_data):
        """Launch app with different methods."""

        method = CMD_RUN_APP
        app_cmd = app_data.split("@")
        app_id = app_cmd[0]
        if len(app_cmd) > 1:
            method = app_cmd[1]
        else:
            app_launch_method = AppLaunchMethod(
                self._get_option(CONF_APP_LAUNCH_METHOD, AppLaunchMethod.Standard.value)
            )

            if app_launch_method == AppLaunchMethod.Remote:
                method = CMD_RUN_APP_REMOTE
            elif app_launch_method == AppLaunchMethod.Rest:
                method = CMD_RUN_APP_REST

        await self.async_send_command(app_id, method)

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Support running different media type command."""
        media_type = media_type.lower()

        # Type channel
        if media_type == MEDIA_TYPE_CHANNEL:
            await self._async_set_channel(media_id)

        # Launch an app
        elif media_type == MEDIA_TYPE_APP:
            await self._async_launch_app(media_id)

        # Send custom key
        elif media_type == MEDIA_TYPE_KEY:
            try:
                cv.string(media_id)
            except vol.Invalid:
                _LOGGER.error('Media ID must be a string (ex: "KEY_HOME"')
                return

            source_key = media_id
            await self._async_send_keys(source_key)

        # Play media
        elif media_type == MEDIA_TYPE_URL:
            try:
                cv.url(media_id)
            except vol.Invalid:
                _LOGGER.error('Media ID must be an url (ex: "http://"')
                return

            await self._upnp.async_set_current_media(media_id)
            self._playing = True

        # Trying to make stream component work on TV
        elif media_type == "application/vnd.apple.mpegurl":
            await self._upnp.async_set_current_media(media_id)
            self._playing = True

        elif media_type == MEDIA_TYPE_BROWSER:
            await self.async_send_command(media_id, CMD_OPEN_BROWSER)

        elif media_type == MEDIA_TYPE_TEXT:
            await self.async_send_command(media_id, CMD_SEND_TEXT)

        else:
            _LOGGER.error("Unsupported media type: %s", media_type)
            return

    async def async_select_source(self, source, reset_delayed=True):
        """Select input source."""
        if not reset_delayed:
            if self._st:
                if self._st.state != STStatus.STATE_ON:
                    # wait for smartthings available
                    return

        running_app = DEFAULT_APP
        self._delayed_set_source = None

        if self.state != STATE_ON:
            if await self._async_turn_on():
                self._delayed_set_source = source
                self._delayed_set_source_time = datetime.now()
            return

        if self._source_list and source in self._source_list:
            source_key = self._source_list[source]
            if not await self._async_send_keys(source_key):
                return
        elif self._app_list and source in self._app_list:
            app_id = self._app_list[source]
            running_app = source
            await self._async_launch_app(app_id)
            if self._st:
                self._st.set_application(self._app_list_ST[source])
        elif self._channel_list and source in self._channel_list:
            source_key = self._channel_list[source]
            await self._async_set_channel(source_key)
            return
        else:
            _LOGGER.error("Unsupported source")
            return

        self._running_app = running_app
        self._source = source

    async def async_select_sound_mode(self, sound_mode):
        """Select sound mode."""
        if not self._st:
            raise NotImplementedError()
        await self._st.async_set_sound_mode(sound_mode)

    async def async_select_picture_mode(self, picture_mode):
        """Select picture mode."""
        if not self._st:
            raise NotImplementedError()
        await self._st.async_set_picture_mode(picture_mode)

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        data = {
            ATTR_IP_ADDRESS: self._host
        }
        if self._ws.artmode_status != ArtModeStatus.Unsupported:
            status_on = self._ws.artmode_status == ArtModeStatus.On
            data.update({
                ATTR_ART_MODE_STATUS: STATE_ON if status_on else STATE_OFF
            })
        if self._st:
            picture_mode = self._st.picture_mode
            picture_mode_list = self._st.picture_mode_list
            if picture_mode:
                data[ATTR_PICTURE_MODE] = picture_mode
            if picture_mode_list:
                data[ATTR_PICTURE_MODE_LIST] = picture_mode_list

        return data

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        await self.hass.async_add_executor_job(self._ws.stop_client)

    async def _async_switch_entity(self, power_on: bool):

        if power_on:
            service_name = SERVICE_TURN_ON
            conf_entity = CONF_SYNC_TURN_ON
        else:
            service_name = SERVICE_TURN_OFF
            conf_entity = CONF_SYNC_TURN_OFF

        entity_list = self._get_option(conf_entity)
        if not entity_list:
            return

        entity_array = entity_list.split(",")

        for index, entity in enumerate(entity_array):
            if index >= MAX_CONTROLLED_ENTITY:
                _LOGGER.warning(
                    "SamsungTV Smart - Maximum %s entities can be controlled",
                    MAX_CONTROLLED_ENTITY,
                )
                break
            if entity:
                await self._async_call_service(service_name, entity)

        return

    async def _async_call_service(
            self,
            service_name,
            entity_id,
            variable_data=None,
    ):
        service_data = {
            CONF_SERVICE: service_name,
            CONF_SERVICE_ENTITY_ID: entity_id,
        }

        if variable_data:
            service_data[CONF_SERVICE_DATA] = variable_data

        try:
            await async_call_from_config(
                self.hass, service_data, blocking=False, validate_config=True,
            )
        except HomeAssistantError as ex:
            _LOGGER.error("SamsungTV Smart - error %s", ex)

        return
