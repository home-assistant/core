import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.components.binary_sensor import DEVICE_CLASSES
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_DEVICES, \
    CONF_NAME, CONF_DEVICE_CLASS, EVENT_HOMEASSISTANT_STOP, CONF_MODE, \
    CONF_SCAN_INTERVAL, CONF_FORCE_UPDATE, CONF_EXCLUDE, CONF_SENSORS, \
    CONF_TIMEOUT, CONF_PAYLOAD_OFF
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType

from . import utils
from .sonoff_camera import EWeLinkCameras
from .sonoff_cloud import ConsumptionHelper
from .sonoff_main import EWeLinkRegistry, get_attrs

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'sonoff'

# https://github.com/AlexxIT/SonoffLAN/issues/14
SCAN_INTERVAL = timedelta(minutes=5)

CONF_DEBUG = 'debug'
CONF_DEFAULT_CLASS = 'default_class'
CONF_DEVICEKEY = 'devicekey'
CONF_RELOAD = 'reload'
CONF_RFBRIDGE = 'rfbridge'

CONF_MODES = ['auto', 'cloud', 'local']
CONF_RELOADS = ['once', 'always']

# copy all binary device_class without light
BINARY_DEVICE = [p for p in DEVICE_CLASSES if p != 'light']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_MODE, default='auto'): vol.In(CONF_MODES),
        vol.Optional(CONF_RELOAD, default='once'): vol.In(CONF_RELOADS),
        vol.Optional(CONF_DEFAULT_CLASS, default='switch'): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_FORCE_UPDATE): cv.ensure_list,
        vol.Optional(CONF_SENSORS): cv.ensure_list,
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
        vol.Optional(CONF_RFBRIDGE): {
            cv.string: vol.Schema({
                vol.Optional(CONF_NAME): cv.string,
                vol.Optional(CONF_DEVICE_CLASS): cv.string,
                vol.Optional(CONF_TIMEOUT, default=120): cv.positive_int,
                vol.Optional(CONF_PAYLOAD_OFF): cv.string
            }, extra=vol.ALLOW_EXTRA),
        },
        vol.Optional(CONF_DEVICES): {
            cv.string: vol.Schema({
                vol.Optional(CONF_NAME): cv.string,
                vol.Optional(CONF_DEVICE_CLASS): vol.Any(str, list),
                vol.Optional(CONF_DEVICEKEY): cv.string,
                vol.Optional(CONF_FORCE_UPDATE): cv.boolean
            }, extra=vol.ALLOW_EXTRA),
        },
    }, extra=vol.ALLOW_EXTRA),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistantType, hass_config: dict):
    session = async_get_clientsession(hass)
    hass.data[DOMAIN] = registry = EWeLinkRegistry(session)

    config = hass_config[DOMAIN]

    # init debug if needed
    if config[CONF_DEBUG]:
        debug = utils.SonoffDebug(hass)
        _LOGGER.setLevel(logging.DEBUG)
        _LOGGER.addHandler(debug)

        info = await hass.helpers.system_info.async_get_system_info()
        info.pop('installation_type', None)  # fix HA v0.109.6
        info.pop('timezone')
        _LOGGER.debug(f"SysInfo: {info}")

    # main init phase
    mode = config[CONF_MODE]

    _LOGGER.debug(f"{mode.upper()} mode start")

    cachefile = hass.config.path('.sonoff.json')
    registry.cache_load_devices(cachefile)

    has_credentials = CONF_USERNAME in config and CONF_PASSWORD in config

    # in mode=local with reload=once - do not connect to cloud servers
    local_once = (mode == 'local' and config[CONF_RELOAD] == 'once' and
                  registry.devices)

    if has_credentials and not local_once:
        if await registry.cloud_login(config[CONF_USERNAME],
                                      config[CONF_PASSWORD]):
            await registry.cloud_load_devices(cachefile)

        else:
            _LOGGER.warning("Can't connect to eWeLink Cloud")
            # don't start the cloud below
            has_credentials = False

    elif mode == 'cloud':
        _LOGGER.error("For cloud mode login / password required")
        return False

    confdevices = config.get(CONF_DEVICES)
    if confdevices:
        registry.concat_devices(confdevices)

    default_class = config[CONF_DEFAULT_CLASS]
    utils.init_device_class(default_class)

    # List of attributes that invoke force_update
    if CONF_FORCE_UPDATE in config:
        force_update = set(config[CONF_FORCE_UPDATE])
        _LOGGER.debug(f"Init force_update for attributes: {force_update}")
    else:
        force_update = None

    if CONF_SENSORS in config:
        sensors = config[CONF_SENSORS]
        _LOGGER.debug(f"Init auto sensors for: {sensors}")
    else:
        sensors = []

    def add_device(deviceid: str, state: dict, *args):
        device = registry.devices[deviceid]

        # device with handlers already added
        if 'handlers' in device:
            return
        else:
            device['handlers'] = []

        device_class = device.get(CONF_DEVICE_CLASS)
        # ignore device if user wants
        if device_class == CONF_EXCLUDE:
            return

        # TODO: right place?
        device['available'] = device.get('online') or device.get('host')

        # collect info for logs
        device['extra'] = utils.get_device_info(device)

        # TODO: fix remove camera info from logs
        state.pop('partnerDevice', None)

        info = {'uiid': device['uiid'], 'extra': device['extra'],
                'params': state}
        _LOGGER.debug(f"{deviceid} == Init   | {info}")

        # fix cloud attrs like currentTemperature and currentHumidity
        get_attrs(state)

        # set device force_update if needed
        if force_update and force_update & state.keys():
            device[CONF_FORCE_UPDATE] = True

        if not device_class:
            device_class = utils.guess_device_class(device)

        if not device_class:
            # Fallback guess device_class from device state
            if 'switch' in state:
                device_class = default_class
            elif 'switches' in state:
                device_class = [default_class] * 4
            else:
                device_class = 'binary_sensor'

        if isinstance(device_class, str):  # read single device_class
            if device_class in BINARY_DEVICE:
                device_class = 'binary_sensor'
            info = {'deviceid': deviceid, 'channels': None}
            hass.async_create_task(discovery.async_load_platform(
                hass, device_class, DOMAIN, info, hass_config))

        else:  # read multichannel device_class
            for info in utils.parse_multichannel_class(device_class):
                info['deviceid'] = deviceid
                hass.async_create_task(discovery.async_load_platform(
                    hass, info.pop('component'), DOMAIN, info, hass_config))

        for attribute in sensors:
            if attribute in state:
                info = {'deviceid': deviceid, 'attribute': attribute}
                hass.async_create_task(discovery.async_load_platform(
                    hass, 'sensor', DOMAIN, info, hass_config))

    async def send_command(call: ServiceCall):
        """Service for send raw command to device.

        :param call: `device` - required param, all other params - optional
        """
        data = dict(call.data)
        deviceid = str(data.pop('device'))

        if len(deviceid) == 10:
            await registry.send(deviceid, data)

        elif len(deviceid) == 6:
            await cameras.send(deviceid, data['cmd'])

        else:
            _LOGGER.error(f"Wrong deviceid {deviceid}")

    hass.services.async_register(DOMAIN, 'send_command', send_command)

    async def update_consumption(call: ServiceCall):
        if not hasattr(registry, 'consumption'):
            _LOGGER.debug("Create ConsumptionHelper")
            registry.consumption = ConsumptionHelper(registry.cloud)
        await registry.consumption.update()

    hass.services.async_register(DOMAIN, 'update_consumption',
                                 update_consumption)

    if CONF_SCAN_INTERVAL in config:
        global SCAN_INTERVAL
        SCAN_INTERVAL = config[CONF_SCAN_INTERVAL]

    if mode in ('auto', 'cloud') and has_credentials:
        utils.handle_cloud_error(hass)

        # immediately add all cloud devices
        for deviceid, device in registry.devices.items():
            if 'params' not in device:
                continue
            conn = 'online' if device['online'] else 'offline'
            device['params']['cloud'] = conn
            add_device(deviceid, device['params'], None)

        await registry.cloud_start()

    if mode in ('auto', 'local'):
        # add devices only on first discovery
        await registry.local_start([add_device])

    # cameras starts only on first command to it
    cameras = EWeLinkCameras()

    # create binary sensors for RF Bridge
    if CONF_RFBRIDGE in config:
        for k, v in config[CONF_RFBRIDGE].items():
            v['trigger'] = k
            hass.async_create_task(discovery.async_load_platform(
                hass, 'binary_sensor', DOMAIN, v, hass_config))

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, registry.stop)

    return True
