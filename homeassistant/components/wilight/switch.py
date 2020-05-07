"""Support for WiLight switches."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.switch import ToggleEntity
from homeassistant.const import TIME_HOURS, TIME_SECONDS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_component import EntityComponent

from . import DATA_DEVICE_REGISTER, WiLightDevice
from .const import ITEM_SWITCH, SWITCH_NONE, SWITCH_PAUSE_VALVE, SWITCH_V1, SWITCH_VALVE

SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)

# Bitfield of features supported by the valve switch entity
SUPPORT_WATERING_TIME = 1
SUPPORT_PAUSE_TIME = 2

# Attr of features supported by the valve switch entity
ATTR_WATERING_TIME = "watering_time"
ATTR_PAUSE_TIME = "pausing_time"

# Service of features supported by the valve switch entity
SERVICE_SET_WATERING_TIME = "set_watering_time"
SERVICE_SET_PAUSE_TIME = "set_pausing_time"

# Range of features supported by the valve switch entity
RANGE_WATERING_TIME = 1800
RANGE_PAUSING_TIME = 24

# Service call validation schemas
VALID_WATERING_TIME = vol.All(
    vol.Coerce(int), vol.Range(min=1, max=RANGE_WATERING_TIME)
)
VALID_PAUSE_TIME = vol.All(vol.Coerce(int), vol.Range(min=1, max=RANGE_PAUSING_TIME))

CONF_WATERING_TIME = "watering_seconds"

CONF_PAUSING_TIME = "pausing_hours"

DEVICE_MAP_INDEX = [
    "DESC_INDEX",
    "ICON_INDEX",
    "UNIT_OF_MEASURE_INDEX",
]

DEVICE_MAP = {
    "watering_time": ["Tempo de irrigação", "mdi:water", TIME_SECONDS],
    "pausing_time": ["Tempo de Pausa", "mdi:pause-circle-outline", TIME_HOURS],
}


def devices_from_config(hass, discovery_info):
    """Parse configuration and add WiLights switch devices."""
    device_id = discovery_info[0]
    model = discovery_info[1]
    indexes = discovery_info[2]
    item_names = discovery_info[3]
    item_types = discovery_info[4]
    device_client = hass.data[DATA_DEVICE_REGISTER][device_id]
    item_sub_types = discovery_info[5]
    devices = []
    for i in range(0, len(indexes)):
        if item_types[i] != ITEM_SWITCH:
            continue
        if item_sub_types[i] == SWITCH_NONE:
            continue
        index = indexes[i]
        item_name = item_names[i]
        item_type = f"{item_types[i]}.{item_sub_types[i]}"
        if item_sub_types[i] == SWITCH_V1:
            device = WiLightSwitch(
                item_name, index, device_id, model, item_type, device_client
            )
        elif item_sub_types[i] == SWITCH_VALVE:
            device = WiLightValveSwitch(
                ATTR_WATERING_TIME,
                item_name,
                index,
                device_id,
                model,
                item_type,
                device_client,
            )
        elif item_sub_types[i] == SWITCH_PAUSE_VALVE:
            device = WiLightValveSwitch(
                ATTR_PAUSE_TIME,
                item_name,
                index,
                device_id,
                model,
                item_type,
                device_client,
            )
        devices.append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the WiLights platform."""
    async_add_entities(devices_from_config(hass, discovery_info))


async def async_setup(hass, config):
    """Expose switch control via state machine and services."""
    component = hass.data["switch"] = EntityComponent(
        _LOGGER, "switch", hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_WATERING_TIME,
        {vol.Required(ATTR_WATERING_TIME): VALID_WATERING_TIME},
        "async_set_watering_time",
        [SUPPORT_WATERING_TIME],
    )

    component.async_register_entity_service(
        SERVICE_SET_PAUSE_TIME,
        {vol.Required(ATTR_PAUSE_TIME): VALID_PAUSE_TIME},
        "async_set_pause_time",
        [SUPPORT_PAUSE_TIME],
    )

    return True


class WiLightSwitch(WiLightDevice, ToggleEntity):
    """Representation of a WiLights switch."""

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        self._status = event
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._status["on"]

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._client.turn_on(self._index)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.turn_off(self._index)

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(self.handle_event_callback, self._index)
        self._status = await self._client.status(self._index)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"wilight_device_available_{self._device_id}",
                self._availability_callback,
            )
        )


def wilight_to_hass_pause_time(value):
    """Convert wilight pause_time seconds to hass hour."""
    return int(value / 3600)


def hass_to_wilight_pause_time(value):
    """Convert hass pause_time hours to wilight seconds."""
    return int(value * 3600)


class WiLightValveSwitch(WiLightDevice, ToggleEntity):
    """Representation of a WiLights Valve switch."""

    def __init__(self, sensor_type, *args):
        """Initialize a switch for Hydrawise device."""
        super().__init__(*args)
        self._sensor_type = sensor_type

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        self._status = event
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self._name} {DEVICE_MAP[self._sensor_type][DEVICE_MAP_INDEX.index('DESC_INDEX')]}"

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return DEVICE_MAP[self._sensor_type][
            DEVICE_MAP_INDEX.index("UNIT_OF_MEASURE_INDEX")
        ]

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._status["on"]

    @property
    def watering_time(self):
        """Return watering time of valve switch.

        None is unknown, 1 is minimum, 1800 is maximum.
        """
        if self._sensor_type == ATTR_WATERING_TIME:
            if "timer_target" in self._status:
                return self._status["timer_target"]
            else:
                return None
        else:
            return None

    @property
    def pausing_time(self):
        """Return pause time of valve switch.

        None is unknown, 1 is minimum, 24 is maximum.
        """
        if self._sensor_type == ATTR_PAUSE_TIME:
            if "timer_target" in self._status:
                return wilight_to_hass_pause_time(self._status["timer_target"])
            else:
                return None
        else:
            return None

    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {}

        watering_time = self.watering_time
        if watering_time is not None:
            data[ATTR_WATERING_TIME] = self.watering_time

        pausing_time = self.pausing_time
        if pausing_time is not None:
            data[ATTR_PAUSE_TIME] = self.pausing_time

        return data

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0

        if self.watering_time is not None:
            supported_features |= SUPPORT_WATERING_TIME

        if self.pausing_time is not None:
            supported_features |= SUPPORT_PAUSE_TIME

        return supported_features

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return DEVICE_MAP[self._sensor_type][DEVICE_MAP_INDEX.index("ICON_INDEX")]

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._client.turn_on(self._index)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.turn_off(self._index)

    async def async_set_watering_time(self, **kwargs):
        """Set the watering time."""
        if self._sensor_type == ATTR_WATERING_TIME:
            if ATTR_WATERING_TIME in kwargs:
                target_time = kwargs[ATTR_WATERING_TIME]
                await self._client.set_switch_time(self._index, target_time)

    async def async_set_pause_time(self, **kwargs):
        """Set the pause time."""
        if self._sensor_type == ATTR_PAUSE_TIME:
            if ATTR_PAUSE_TIME in kwargs:
                target_time = hass_to_wilight_pause_time(kwargs[ATTR_PAUSE_TIME])
                await self._client.set_switch_time(self._index, target_time)

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(self.handle_event_callback, self._index)
        self._status = await self._client.status(self._index)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"wilight_device_available_{self._device_id}",
                self._availability_callback,
            )
        )
