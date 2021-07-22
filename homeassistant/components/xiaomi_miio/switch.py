"""Support for Xiaomi Smart WiFi Socket and Smart Power Strip."""
import asyncio
from functools import partial
import logging

from miio import AirConditioningCompanionV3, ChuangmiPlug, DeviceException, PowerStrip
from miio.powerstrip import PowerMode
import voluptuous as vol

from homeassistant.components.switch import (
    DEVICE_CLASS_SWITCH,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    CONF_MODEL,
    DOMAIN,
    KEY_COORDINATOR,
    SERVICE_SET_POWER_MODE,
    SERVICE_SET_POWER_PRICE,
    SERVICE_SET_WIFI_LED_OFF,
    SERVICE_SET_WIFI_LED_ON,
)
from .device import XiaomiMiioEntity
from .gateway import XiaomiGatewayDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Switch"
DATA_KEY = "switch.xiaomi_miio"

MODEL_POWER_STRIP_V2 = "zimi.powerstrip.v2"
MODEL_PLUG_V3 = "chuangmi.plug.v3"

KEY_CHANNEL = "channel"
GATEWAY_SWITCH_VARS = {
    "status_ch0": {KEY_CHANNEL: 0},
    "status_ch1": {KEY_CHANNEL: 1},
    "status_ch2": {KEY_CHANNEL: 2},
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL): vol.In(
            [
                "chuangmi.plug.v1",
                "qmi.powerstrip.v1",
                "zimi.powerstrip.v2",
                "chuangmi.plug.m1",
                "chuangmi.plug.m3",
                "chuangmi.plug.v2",
                "chuangmi.plug.v3",
                "chuangmi.plug.hmi205",
                "chuangmi.plug.hmi206",
                "chuangmi.plug.hmi208",
                "lumi.acpartner.v3",
            ]
        ),
    }
)

ATTR_POWER = "power"
ATTR_LOAD_POWER = "load_power"
ATTR_MODEL = "model"
ATTR_POWER_MODE = "power_mode"
ATTR_WIFI_LED = "wifi_led"
ATTR_POWER_PRICE = "power_price"
ATTR_PRICE = "price"

SUCCESS = ["ok"]

FEATURE_SET_POWER_MODE = 1
FEATURE_SET_WIFI_LED = 2
FEATURE_SET_POWER_PRICE = 4

FEATURE_FLAGS_GENERIC = 0

FEATURE_FLAGS_POWER_STRIP_V1 = (
    FEATURE_SET_POWER_MODE | FEATURE_SET_WIFI_LED | FEATURE_SET_POWER_PRICE
)

FEATURE_FLAGS_POWER_STRIP_V2 = FEATURE_SET_WIFI_LED | FEATURE_SET_POWER_PRICE

FEATURE_FLAGS_PLUG_V3 = FEATURE_SET_WIFI_LED

SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

SERVICE_SCHEMA_POWER_MODE = SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_MODE): vol.All(vol.In(["green", "normal"]))}
)

SERVICE_SCHEMA_POWER_PRICE = SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_PRICE): cv.positive_float}
)

SERVICE_TO_METHOD = {
    SERVICE_SET_WIFI_LED_ON: {"method": "async_set_wifi_led_on"},
    SERVICE_SET_WIFI_LED_OFF: {"method": "async_set_wifi_led_off"},
    SERVICE_SET_POWER_MODE: {
        "method": "async_set_power_mode",
        "schema": SERVICE_SCHEMA_POWER_MODE,
    },
    SERVICE_SET_POWER_PRICE: {
        "method": "async_set_power_price",
        "schema": SERVICE_SCHEMA_POWER_PRICE,
    },
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import Miio configuration from YAML."""
    _LOGGER.warning(
        "Loading Xiaomi Miio Switch via platform setup is deprecated; Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switch from a config entry."""
    entities = []

    host = config_entry.data[CONF_HOST]
    token = config_entry.data[CONF_TOKEN]
    name = config_entry.title
    model = config_entry.data[CONF_MODEL]
    unique_id = config_entry.unique_id

    if config_entry.data[CONF_FLOW_TYPE] == CONF_GATEWAY:
        gateway = hass.data[DOMAIN][config_entry.entry_id][CONF_GATEWAY]
        # Gateway sub devices
        sub_devices = gateway.devices
        coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
        for sub_device in sub_devices.values():
            if sub_device.device_type != "Switch":
                continue
            switch_variables = set(sub_device.status) & set(GATEWAY_SWITCH_VARS)
            if switch_variables:
                entities.extend(
                    [
                        XiaomiGatewaySwitch(
                            coordinator, sub_device, config_entry, variable
                        )
                        for variable in switch_variables
                    ]
                )

    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE or (
        config_entry.data[CONF_FLOW_TYPE] == CONF_GATEWAY
        and model == "lumi.acpartner.v3"
    ):
        if DATA_KEY not in hass.data:
            hass.data[DATA_KEY] = {}

        _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

        if model in ["chuangmi.plug.v1", "chuangmi.plug.v3", "chuangmi.plug.hmi208"]:
            plug = ChuangmiPlug(host, token, model=model)

            # The device has two switchable channels (mains and a USB port).
            # A switch device per channel will be created.
            for channel_usb in (True, False):
                if channel_usb:
                    unique_id_ch = f"{unique_id}-USB"
                else:
                    unique_id_ch = f"{unique_id}-mains"
                device = ChuangMiPlugSwitch(
                    name, plug, config_entry, unique_id_ch, channel_usb
                )
                entities.append(device)
                hass.data[DATA_KEY][host] = device
        elif model in ["qmi.powerstrip.v1", "zimi.powerstrip.v2"]:
            plug = PowerStrip(host, token, model=model)
            device = XiaomiPowerStripSwitch(name, plug, config_entry, unique_id)
            entities.append(device)
            hass.data[DATA_KEY][host] = device
        elif model in [
            "chuangmi.plug.m1",
            "chuangmi.plug.m3",
            "chuangmi.plug.v2",
            "chuangmi.plug.hmi205",
            "chuangmi.plug.hmi206",
        ]:
            plug = ChuangmiPlug(host, token, model=model)
            device = XiaomiPlugGenericSwitch(name, plug, config_entry, unique_id)
            entities.append(device)
            hass.data[DATA_KEY][host] = device
        elif model in ["lumi.acpartner.v3"]:
            plug = AirConditioningCompanionV3(host, token)
            device = XiaomiAirConditioningCompanionSwitch(
                name, plug, config_entry, unique_id
            )
            entities.append(device)
            hass.data[DATA_KEY][host] = device
        else:
            _LOGGER.error(
                "Unsupported device found! Please create an issue at "
                "https://github.com/rytilahti/python-miio/issues "
                "and provide the following data: %s",
                model,
            )

        async def async_service_handler(service):
            """Map services to methods on XiaomiPlugGenericSwitch."""
            method = SERVICE_TO_METHOD.get(service.service)
            params = {
                key: value
                for key, value in service.data.items()
                if key != ATTR_ENTITY_ID
            }
            entity_ids = service.data.get(ATTR_ENTITY_ID)
            if entity_ids:
                devices = [
                    device
                    for device in hass.data[DATA_KEY].values()
                    if device.entity_id in entity_ids
                ]
            else:
                devices = hass.data[DATA_KEY].values()

            update_tasks = []
            for device in devices:
                if not hasattr(device, method["method"]):
                    continue
                await getattr(device, method["method"])(**params)
                update_tasks.append(device.async_update_ha_state(True))

            if update_tasks:
                await asyncio.wait(update_tasks)

        for plug_service, method in SERVICE_TO_METHOD.items():
            schema = method.get("schema", SERVICE_SCHEMA)
            hass.services.async_register(
                DOMAIN, plug_service, async_service_handler, schema=schema
            )

    async_add_entities(entities, update_before_add=True)


class XiaomiGatewaySwitch(XiaomiGatewayDevice, SwitchEntity):
    """Representation of a XiaomiGatewaySwitch."""

    _attr_device_class = DEVICE_CLASS_SWITCH

    def __init__(self, coordinator, sub_device, entry, variable):
        """Initialize the XiaomiSensor."""
        super().__init__(coordinator, sub_device, entry)
        self._channel = GATEWAY_SWITCH_VARS[variable][KEY_CHANNEL]
        self._data_key = f"status_ch{self._channel}"
        self._unique_id = f"{sub_device.sid}-ch{self._channel}"
        self._name = f"{sub_device.name} ch{self._channel} ({sub_device.sid})"

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._sub_device.status[self._data_key] == "on"

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.hass.async_add_executor_job(self._sub_device.on, self._channel)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.hass.async_add_executor_job(self._sub_device.off, self._channel)

    async def async_toggle(self, **kwargs):
        """Toggle the switch."""
        await self.hass.async_add_executor_job(self._sub_device.toggle, self._channel)


class XiaomiPlugGenericSwitch(XiaomiMiioEntity, SwitchEntity):
    """Representation of a Xiaomi Plug Generic."""

    def __init__(self, name, device, entry, unique_id):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id)

        self._icon = "mdi:power-socket"
        self._available = False
        self._state = None
        self._state_attrs = {ATTR_TEMPERATURE: None, ATTR_MODEL: self._model}
        self._device_features = FEATURE_FLAGS_GENERIC
        self._skip_update = False

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a plug command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )

            _LOGGER.debug("Response received from plug: %s", result)

            # The Chuangmi Plug V3 returns 0 on success on usb_on/usb_off.
            if func in ["usb_on", "usb_off"] and result == 0:
                return True

            return result == SUCCESS
        except DeviceException as exc:
            if self._available:
                _LOGGER.error(mask_error, exc)
                self._available = False

            return False

    async def async_turn_on(self, **kwargs):
        """Turn the plug on."""
        result = await self._try_command("Turning the plug on failed", self._device.on)

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs):
        """Turn the plug off."""
        result = await self._try_command(
            "Turning the plug off failed", self._device.off
        )

        if result:
            self._state = False
            self._skip_update = True

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.is_on
            self._state_attrs[ATTR_TEMPERATURE] = state.temperature

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)

    async def async_set_wifi_led_on(self):
        """Turn the wifi led on."""
        if self._device_features & FEATURE_SET_WIFI_LED == 0:
            return

        await self._try_command(
            "Turning the wifi led on failed", self._device.set_wifi_led, True
        )

    async def async_set_wifi_led_off(self):
        """Turn the wifi led on."""
        if self._device_features & FEATURE_SET_WIFI_LED == 0:
            return

        await self._try_command(
            "Turning the wifi led off failed", self._device.set_wifi_led, False
        )

    async def async_set_power_price(self, price: int):
        """Set the power price."""
        if self._device_features & FEATURE_SET_POWER_PRICE == 0:
            return

        await self._try_command(
            "Setting the power price of the power strip failed",
            self._device.set_power_price,
            price,
        )


class XiaomiPowerStripSwitch(XiaomiPlugGenericSwitch):
    """Representation of a Xiaomi Power Strip."""

    def __init__(self, name, plug, model, unique_id):
        """Initialize the plug switch."""
        super().__init__(name, plug, model, unique_id)

        if self._model == MODEL_POWER_STRIP_V2:
            self._device_features = FEATURE_FLAGS_POWER_STRIP_V2
        else:
            self._device_features = FEATURE_FLAGS_POWER_STRIP_V1

        self._state_attrs[ATTR_LOAD_POWER] = None

        if self._device_features & FEATURE_SET_POWER_MODE == 1:
            self._state_attrs[ATTR_POWER_MODE] = None

        if self._device_features & FEATURE_SET_WIFI_LED == 1:
            self._state_attrs[ATTR_WIFI_LED] = None

        if self._device_features & FEATURE_SET_POWER_PRICE == 1:
            self._state_attrs[ATTR_POWER_PRICE] = None

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.is_on
            self._state_attrs.update(
                {ATTR_TEMPERATURE: state.temperature, ATTR_LOAD_POWER: state.load_power}
            )

            if self._device_features & FEATURE_SET_POWER_MODE == 1 and state.mode:
                self._state_attrs[ATTR_POWER_MODE] = state.mode.value

            if self._device_features & FEATURE_SET_WIFI_LED == 1 and state.wifi_led:
                self._state_attrs[ATTR_WIFI_LED] = state.wifi_led

            if (
                self._device_features & FEATURE_SET_POWER_PRICE == 1
                and state.power_price
            ):
                self._state_attrs[ATTR_POWER_PRICE] = state.power_price

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)

    async def async_set_power_mode(self, mode: str):
        """Set the power mode."""
        if self._device_features & FEATURE_SET_POWER_MODE == 0:
            return

        await self._try_command(
            "Setting the power mode of the power strip failed",
            self._device.set_power_mode,
            PowerMode(mode),
        )


class ChuangMiPlugSwitch(XiaomiPlugGenericSwitch):
    """Representation of a Chuang Mi Plug V1 and V3."""

    def __init__(self, name, plug, entry, unique_id, channel_usb):
        """Initialize the plug switch."""
        name = f"{name} USB" if channel_usb else name

        if unique_id is not None and channel_usb:
            unique_id = f"{unique_id}-usb"

        super().__init__(name, plug, entry, unique_id)
        self._channel_usb = channel_usb

        if self._model == MODEL_PLUG_V3:
            self._device_features = FEATURE_FLAGS_PLUG_V3
            self._state_attrs[ATTR_WIFI_LED] = None
            if self._channel_usb is False:
                self._state_attrs[ATTR_LOAD_POWER] = None

    async def async_turn_on(self, **kwargs):
        """Turn a channel on."""
        if self._channel_usb:
            result = await self._try_command(
                "Turning the plug on failed", self._device.usb_on
            )
        else:
            result = await self._try_command(
                "Turning the plug on failed", self._device.on
            )

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs):
        """Turn a channel off."""
        if self._channel_usb:
            result = await self._try_command(
                "Turning the plug off failed", self._device.usb_off
            )
        else:
            result = await self._try_command(
                "Turning the plug off failed", self._device.off
            )

        if result:
            self._state = False
            self._skip_update = True

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            if self._channel_usb:
                self._state = state.usb_power
            else:
                self._state = state.is_on

            self._state_attrs[ATTR_TEMPERATURE] = state.temperature

            if state.wifi_led:
                self._state_attrs[ATTR_WIFI_LED] = state.wifi_led

            if self._channel_usb is False and state.load_power:
                self._state_attrs[ATTR_LOAD_POWER] = state.load_power

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)


class XiaomiAirConditioningCompanionSwitch(XiaomiPlugGenericSwitch):
    """Representation of a Xiaomi AirConditioning Companion."""

    def __init__(self, name, plug, model, unique_id):
        """Initialize the acpartner switch."""
        super().__init__(name, plug, model, unique_id)

        self._state_attrs.update({ATTR_TEMPERATURE: None, ATTR_LOAD_POWER: None})

    async def async_turn_on(self, **kwargs):
        """Turn the socket on."""
        result = await self._try_command(
            "Turning the socket on failed", self._device.socket_on
        )

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs):
        """Turn the socket off."""
        result = await self._try_command(
            "Turning the socket off failed", self._device.socket_off
        )

        if result:
            self._state = False
            self._skip_update = True

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.power_socket == "on"
            self._state_attrs[ATTR_LOAD_POWER] = state.load_power

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)
