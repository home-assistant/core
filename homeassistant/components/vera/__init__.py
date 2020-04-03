"""Support for Vera devices."""
import asyncio
from collections import defaultdict
import logging

import pyvera as veraApi
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ARMED,
    ATTR_BATTERY_LEVEL,
    ATTR_LAST_TRIP_TIME,
    ATTR_TRIPPED,
    CONF_EXCLUDE,
    CONF_LIGHTS,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import convert, slugify
from homeassistant.util.dt import utc_from_timestamp

from .common import ControllerData, get_configured_platforms
from .config_flow import new_options
from .const import (
    ATTR_CURRENT_ENERGY_KWH,
    ATTR_CURRENT_POWER_W,
    CONF_CONTROLLER,
    DOMAIN,
    VERA_ID_FORMAT,
)

_LOGGER = logging.getLogger(__name__)

VERA_ID_LIST_SCHEMA = vol.Schema([int])

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CONTROLLER): cv.url,
                vol.Optional(CONF_EXCLUDE, default=[]): VERA_ID_LIST_SCHEMA,
                vol.Optional(CONF_LIGHTS, default=[]): VERA_ID_LIST_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, base_config: dict) -> bool:
    """Set up for Vera controllers."""
    config = base_config.get(DOMAIN)

    if not config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config,
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Do setup of vera."""
    # Use options entered during initial config flow or provided from configuration.yml
    if config_entry.data.get(CONF_LIGHTS) or config_entry.data.get(CONF_EXCLUDE):
        hass.config_entries.async_update_entry(
            entry=config_entry,
            data=config_entry.data,
            options=new_options(
                config_entry.data.get(CONF_LIGHTS, []),
                config_entry.data.get(CONF_EXCLUDE, []),
            ),
        )

    base_url = config_entry.data[CONF_CONTROLLER]
    light_ids = config_entry.options.get(CONF_LIGHTS, [])
    exclude_ids = config_entry.options.get(CONF_EXCLUDE, [])

    # Initialize the Vera controller.
    controller = veraApi.VeraController(base_url)
    controller.start()

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP,
        lambda event: hass.async_add_executor_job(controller.stop),
    )

    try:
        all_devices = await hass.async_add_executor_job(controller.get_devices)

        all_scenes = await hass.async_add_executor_job(controller.get_scenes)
    except RequestException:
        # There was a network related error connecting to the Vera controller.
        _LOGGER.exception("Error communicating with Vera API")
        return False

    # Exclude devices unwanted by user.
    devices = [device for device in all_devices if device.device_id not in exclude_ids]

    vera_devices = defaultdict(list)
    for device in devices:
        device_type = map_vera_device(device, light_ids)
        if device_type is None:
            continue

        vera_devices[device_type].append(device)

    vera_scenes = []
    for scene in all_scenes:
        vera_scenes.append(scene)

    controller_data = ControllerData(
        controller=controller, devices=vera_devices, scenes=vera_scenes
    )

    hass.data[DOMAIN] = controller_data

    # Forward the config data to the necessary platforms.
    for platform in get_configured_platforms(controller_data):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Withings config entry."""
    controller_data = hass.data[DOMAIN]

    tasks = [
        hass.config_entries.async_forward_entry_unload(config_entry, platform)
        for platform in get_configured_platforms(controller_data)
    ]
    await asyncio.gather(*tasks)

    return True


def map_vera_device(vera_device, remap):
    """Map vera classes to Home Assistant types."""

    if isinstance(vera_device, veraApi.VeraDimmer):
        return "light"
    if isinstance(vera_device, veraApi.VeraBinarySensor):
        return "binary_sensor"
    if isinstance(vera_device, veraApi.VeraSensor):
        return "sensor"
    if isinstance(vera_device, veraApi.VeraArmableDevice):
        return "switch"
    if isinstance(vera_device, veraApi.VeraLock):
        return "lock"
    if isinstance(vera_device, veraApi.VeraThermostat):
        return "climate"
    if isinstance(vera_device, veraApi.VeraCurtain):
        return "cover"
    if isinstance(vera_device, veraApi.VeraSceneController):
        return "sensor"
    if isinstance(vera_device, veraApi.VeraSwitch):
        if vera_device.device_id in remap:
            return "light"
        return "switch"
    return None


class VeraDevice(Entity):
    """Representation of a Vera device entity."""

    def __init__(self, vera_device, controller):
        """Initialize the device."""
        self.vera_device = vera_device
        self.controller = controller

        self._name = self.vera_device.name
        # Append device id to prevent name clashes in HA.
        self.vera_id = VERA_ID_FORMAT.format(
            slugify(vera_device.name), vera_device.device_id
        )

        self.controller.register(vera_device, self._update_callback)

    def _update_callback(self, _device):
        """Update the state."""
        self.schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Get polling requirement from vera device."""
        return self.vera_device.should_poll

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level

        if self.vera_device.is_armable:
            armed = self.vera_device.is_armed
            attr[ATTR_ARMED] = "True" if armed else "False"

        if self.vera_device.is_trippable:
            last_tripped = self.vera_device.last_trip
            if last_tripped is not None:
                utc_time = utc_from_timestamp(int(last_tripped))
                attr[ATTR_LAST_TRIP_TIME] = utc_time.isoformat()
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
            tripped = self.vera_device.is_tripped
            attr[ATTR_TRIPPED] = "True" if tripped else "False"

        power = self.vera_device.power
        if power:
            attr[ATTR_CURRENT_POWER_W] = convert(power, float, 0.0)

        energy = self.vera_device.energy
        if energy:
            attr[ATTR_CURRENT_ENERGY_KWH] = convert(energy, float, 0.0)

        attr["Vera Device Id"] = self.vera_device.vera_device_id

        return attr

    @property
    def unique_id(self) -> str:
        """Return a unique ID.

        The Vera assigns a unique and immutable ID number to each device.
        """
        return str(self.vera_device.vera_device_id)
