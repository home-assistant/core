"""
Support for Xiaomi Smart WiFi Socket and Smart Power Strip.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/switch.xiaomi_miio/
"""
import asyncio
from functools import partial
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA,
                                             DOMAIN, )
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_TOKEN,
                                 ATTR_ENTITY_ID, )
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Xiaomi Miio Switch'
DATA_KEY = 'switch.xiaomi_miio'

CONF_MODEL = 'model'
MODEL_POWER_STRIP_V2 = 'zimi.powerstrip.v2'
MODEL_PLUG_V3 = 'chuangmi.plug.v3'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MODEL): vol.In(
        ['chuangmi.plug.v1',
         'qmi.powerstrip.v1',
         'zimi.powerstrip.v2',
         'chuangmi.plug.m1',
         'chuangmi.plug.v2',
         'chuangmi.plug.v3']),
})

REQUIREMENTS = ['python-miio==0.3.9', 'construct==2.9.41']

ATTR_POWER = 'power'
ATTR_TEMPERATURE = 'temperature'
ATTR_LOAD_POWER = 'load_power'
ATTR_MODEL = 'model'
ATTR_MODE = 'mode'
ATTR_POWER_MODE = 'power_mode'
ATTR_WIFI_LED = 'wifi_led'
ATTR_POWER_PRICE = 'power_price'
ATTR_PRICE = 'price'

SUCCESS = ['ok']

FEATURE_SET_POWER_MODE = 1
FEATURE_SET_WIFI_LED = 2
FEATURE_SET_POWER_PRICE = 4

FEATURE_FLAGS_GENERIC = 0

FEATURE_FLAGS_POWER_STRIP_V1 = (FEATURE_SET_POWER_MODE |
                                FEATURE_SET_WIFI_LED |
                                FEATURE_SET_POWER_PRICE)

FEATURE_FLAGS_POWER_STRIP_V2 = (FEATURE_SET_WIFI_LED |
                                FEATURE_SET_POWER_PRICE)

FEATURE_FLAGS_PLUG_V3 = (FEATURE_SET_WIFI_LED)

SERVICE_SET_WIFI_LED_ON = 'xiaomi_miio_set_wifi_led_on'
SERVICE_SET_WIFI_LED_OFF = 'xiaomi_miio_set_wifi_led_off'
SERVICE_SET_POWER_MODE = 'xiaomi_miio_set_power_mode'
SERVICE_SET_POWER_PRICE = 'xiaomi_miio_set_power_price'

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

SERVICE_SCHEMA_POWER_MODE = SERVICE_SCHEMA.extend({
    vol.Required(ATTR_MODE): vol.All(vol.In(['green', 'normal'])),
})

SERVICE_SCHEMA_POWER_PRICE = SERVICE_SCHEMA.extend({
    vol.Required(ATTR_PRICE): vol.All(vol.Coerce(float), vol.Range(min=0))
})

SERVICE_TO_METHOD = {
    SERVICE_SET_WIFI_LED_ON: {'method': 'async_set_wifi_led_on'},
    SERVICE_SET_WIFI_LED_OFF: {'method': 'async_set_wifi_led_off'},
    SERVICE_SET_POWER_MODE: {
        'method': 'async_set_power_mode',
        'schema': SERVICE_SCHEMA_POWER_MODE},
    SERVICE_SET_POWER_PRICE: {
        'method': 'async_set_power_price',
        'schema': SERVICE_SCHEMA_POWER_PRICE},
}


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the switch from config."""
    from miio import Device, DeviceException
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    model = config.get(CONF_MODEL)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    devices = []
    unique_id = None

    if model is None:
        try:
            miio_device = Device(host, token)
            device_info = miio_device.info()
            model = device_info.model
            unique_id = "{}-{}".format(model, device_info.mac_address)
            _LOGGER.info("%s %s %s detected",
                         model,
                         device_info.firmware_version,
                         device_info.hardware_version)
        except DeviceException:
            raise PlatformNotReady

    if model in ['chuangmi.plug.v1', 'chuangmi.plug.v3']:
        from miio import ChuangmiPlug
        plug = ChuangmiPlug(host, token, model=model)

        # The device has two switchable channels (mains and a USB port).
        # A switch device per channel will be created.
        for channel_usb in [True, False]:
            device = ChuangMiPlugSwitch(
                name, plug, model, unique_id, channel_usb)
            devices.append(device)
            hass.data[DATA_KEY][host] = device

    elif model in ['qmi.powerstrip.v1', 'zimi.powerstrip.v2']:
        from miio import PowerStrip
        plug = PowerStrip(host, token)
        device = XiaomiPowerStripSwitch(name, plug, model, unique_id)
        devices.append(device)
        hass.data[DATA_KEY][host] = device
    elif model in ['chuangmi.plug.m1', 'chuangmi.plug.v2']:
        from miio import ChuangmiPlug
        plug = ChuangmiPlug(host, token, model=model)
        device = XiaomiPlugGenericSwitch(name, plug, model, unique_id)
        devices.append(device)
        hass.data[DATA_KEY][host] = device
    else:
        _LOGGER.error(
            'Unsupported device found! Please create an issue at '
            'https://github.com/rytilahti/python-miio/issues '
            'and provide the following data: %s', model)
        return False

    async_add_devices(devices, update_before_add=True)

    async def async_service_handler(service):
        """Map services to methods on XiaomiPlugGenericSwitch."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [device for device in hass.data[DATA_KEY].values() if
                       device.entity_id in entity_ids]
        else:
            devices = hass.data[DATA_KEY].values()

        update_tasks = []
        for device in devices:
            if not hasattr(device, method['method']):
                continue
            await getattr(device, method['method'])(**params)
            update_tasks.append(device.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks, loop=hass.loop)

    for plug_service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[plug_service].get('schema', SERVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN, plug_service, async_service_handler, schema=schema)


class XiaomiPlugGenericSwitch(SwitchDevice):
    """Representation of a Xiaomi Plug Generic."""

    def __init__(self, name, plug, model, unique_id):
        """Initialize the plug switch."""
        self._name = name
        self._plug = plug
        self._model = model
        self._unique_id = unique_id

        self._icon = 'mdi:power-socket'
        self._available = False
        self._state = None
        self._state_attrs = {
            ATTR_TEMPERATURE: None,
            ATTR_MODEL: self._model,
        }
        self._device_features = FEATURE_FLAGS_GENERIC
        self._skip_update = False

    @property
    def should_poll(self):
        """Poll the plug."""
        return True

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a plug command handling error messages."""
        from miio import DeviceException
        try:
            result = await self.hass.async_add_job(
                partial(func, *args, **kwargs))

            _LOGGER.debug("Response received from plug: %s", result)

            # The Chuangmi Plug V3 returns 0 on success on usb_on/usb_off.
            if func in ['usb_on', 'usb_off'] and result == 0:
                return True

            return result == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            self._available = False
            return False

    async def async_turn_on(self, **kwargs):
        """Turn the plug on."""
        result = await self._try_command(
            "Turning the plug on failed.", self._plug.on)

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs):
        """Turn the plug off."""
        result = await self._try_command(
            "Turning the plug off failed.", self._plug.off)

        if result:
            self._state = False
            self._skip_update = True

    async def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException

        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_job(self._plug.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.is_on
            self._state_attrs.update({
                ATTR_TEMPERATURE: state.temperature
            })

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    async def async_set_wifi_led_on(self):
        """Turn the wifi led on."""
        if self._device_features & FEATURE_SET_WIFI_LED == 0:
            return

        await self._try_command(
            "Turning the wifi led on failed.",
            self._plug.set_wifi_led, True)

    async def async_set_wifi_led_off(self):
        """Turn the wifi led on."""
        if self._device_features & FEATURE_SET_WIFI_LED == 0:
            return

        await self._try_command(
            "Turning the wifi led off failed.",
            self._plug.set_wifi_led, False)

    async def async_set_power_price(self, price: int):
        """Set the power price."""
        if self._device_features & FEATURE_SET_POWER_PRICE == 0:
            return

        await self._try_command(
            "Setting the power price of the power strip failed.",
            self._plug.set_power_price, price)


class XiaomiPowerStripSwitch(XiaomiPlugGenericSwitch):
    """Representation of a Xiaomi Power Strip."""

    def __init__(self, name, plug, model, unique_id):
        """Initialize the plug switch."""
        super().__init__(name, plug, model, unique_id)

        if self._model == MODEL_POWER_STRIP_V2:
            self._device_features = FEATURE_FLAGS_POWER_STRIP_V2
        else:
            self._device_features = FEATURE_FLAGS_POWER_STRIP_V1

        self._state_attrs.update({
            ATTR_LOAD_POWER: None,
        })

        if self._device_features & FEATURE_SET_POWER_MODE == 1:
            self._state_attrs[ATTR_POWER_MODE] = None

        if self._device_features & FEATURE_SET_WIFI_LED == 1:
            self._state_attrs[ATTR_WIFI_LED] = None

        if self._device_features & FEATURE_SET_POWER_PRICE == 1:
            self._state_attrs[ATTR_POWER_PRICE] = None

    async def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException

        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_job(self._plug.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.is_on
            self._state_attrs.update({
                ATTR_TEMPERATURE: state.temperature,
                ATTR_LOAD_POWER: state.load_power,
            })

            if self._device_features & FEATURE_SET_POWER_MODE == 1 and \
                    state.mode:
                self._state_attrs[ATTR_POWER_MODE] = state.mode.value

            if self._device_features & FEATURE_SET_WIFI_LED == 1 and \
                    state.wifi_led:
                self._state_attrs[ATTR_WIFI_LED] = state.wifi_led

            if self._device_features & FEATURE_SET_POWER_PRICE == 1 and \
                    state.power_price:
                self._state_attrs[ATTR_POWER_PRICE] = state.power_price

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    async def async_set_power_mode(self, mode: str):
        """Set the power mode."""
        if self._device_features & FEATURE_SET_POWER_MODE == 0:
            return

        from miio.powerstrip import PowerMode

        await self._try_command(
            "Setting the power mode of the power strip failed.",
            self._plug.set_power_mode, PowerMode(mode))


class ChuangMiPlugSwitch(XiaomiPlugGenericSwitch):
    """Representation of a Chuang Mi Plug V1 and V3."""

    def __init__(self, name, plug, model, unique_id, channel_usb):
        """Initialize the plug switch."""
        name = '{} USB'.format(name) if channel_usb else name

        if unique_id is not None and channel_usb:
            unique_id = "{}-{}".format(unique_id, 'usb')

        super().__init__(name, plug, model, unique_id)
        self._channel_usb = channel_usb

        if self._model == MODEL_PLUG_V3:
            self._device_features = FEATURE_FLAGS_PLUG_V3
            self._state_attrs.update({
                ATTR_WIFI_LED: None,
                ATTR_LOAD_POWER: None,
            })

    async def async_turn_on(self, **kwargs):
        """Turn a channel on."""
        if self._channel_usb:
            result = await self._try_command(
                "Turning the plug on failed.", self._plug.usb_on)
        else:
            result = await self._try_command(
                "Turning the plug on failed.", self._plug.on)

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs):
        """Turn a channel off."""
        if self._channel_usb:
            result = await self._try_command(
                "Turning the plug on failed.", self._plug.usb_off)
        else:
            result = await self._try_command(
                "Turning the plug on failed.", self._plug.off)

        if result:
            self._state = False
            self._skip_update = True

    async def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException

        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_job(self._plug.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            if self._channel_usb:
                self._state = state.usb_power
            else:
                self._state = state.is_on

            self._state_attrs.update({
                ATTR_TEMPERATURE: state.temperature
            })

            if state.wifi_led:
                self._state_attrs[ATTR_WIFI_LED] = state.wifi_led

            if state.load_power:
                self._state_attrs[ATTR_LOAD_POWER] = state.load_power

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)
