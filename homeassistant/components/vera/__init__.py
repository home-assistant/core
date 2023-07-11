"""Support for Vera devices."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable
import logging
from typing import Any, Generic, TypeVar

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
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.dt import utc_from_timestamp

from .common import (
    ControllerData,
    SubscriptionRegistry,
    get_configured_platforms,
    get_controller_data,
    set_controller_data,
)
from .config_flow import fix_device_id_list, new_options
from .const import CONF_CONTROLLER, CONF_LEGACY_UNIQUE_ID, DOMAIN, VERA_ID_FORMAT

_LOGGER = logging.getLogger(__name__)

VERA_ID_LIST_SCHEMA = vol.Schema([int])

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_CONTROLLER): cv.url,
                    vol.Optional(CONF_EXCLUDE, default=[]): VERA_ID_LIST_SCHEMA,
                    vol.Optional(CONF_LIGHTS, default=[]): VERA_ID_LIST_SCHEMA,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up for Vera controllers."""
    hass.data[DOMAIN] = {}

    if not (config := base_config.get(DOMAIN)):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config,
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Do setup of vera."""
    # Use options entered during initial config flow or provided from configuration.yml
    if entry.data.get(CONF_LIGHTS) or entry.data.get(CONF_EXCLUDE):
        hass.config_entries.async_update_entry(
            entry=entry,
            data=entry.data,
            options=new_options(
                entry.data.get(CONF_LIGHTS, []),
                entry.data.get(CONF_EXCLUDE, []),
            ),
        )

    saved_light_ids = entry.options.get(CONF_LIGHTS, [])
    saved_exclude_ids = entry.options.get(CONF_EXCLUDE, [])

    base_url = entry.data[CONF_CONTROLLER]
    light_ids = fix_device_id_list(saved_light_ids)
    exclude_ids = fix_device_id_list(saved_exclude_ids)

    # If the ids were corrected. Update the config entry.
    if light_ids != saved_light_ids or exclude_ids != saved_exclude_ids:
        hass.config_entries.async_update_entry(
            entry=entry, options=new_options(light_ids, exclude_ids)
        )

    # Initialize the Vera controller.
    subscription_registry = SubscriptionRegistry(hass)
    controller = veraApi.VeraController(base_url, subscription_registry)

    try:
        all_devices = await hass.async_add_executor_job(controller.get_devices)

        all_scenes = await hass.async_add_executor_job(controller.get_scenes)
    except RequestException as exception:
        # There was a network related error connecting to the Vera controller.
        _LOGGER.exception("Error communicating with Vera API")
        raise ConfigEntryNotReady from exception

    # Exclude devices unwanted by user.
    devices = [device for device in all_devices if device.device_id not in exclude_ids]

    vera_devices: defaultdict[Platform, list[veraApi.VeraDevice]] = defaultdict(list)
    for device in devices:
        device_type = map_vera_device(device, light_ids)
        if device_type is not None:
            vera_devices[device_type].append(device)

    vera_scenes = []
    for scene in all_scenes:
        vera_scenes.append(scene)

    controller_data = ControllerData(
        controller=controller,
        devices=vera_devices,
        scenes=vera_scenes,
        config_entry=entry,
    )

    set_controller_data(hass, entry, controller_data)

    # Forward the config data to the necessary platforms.
    await hass.config_entries.async_forward_entry_setups(
        entry, platforms=get_configured_platforms(controller_data)
    )

    def stop_subscription(event):
        """Stop SubscriptionRegistry updates."""
        controller.stop()

    await hass.async_add_executor_job(controller.start)
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_subscription)
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Withings config entry."""
    controller_data: ControllerData = get_controller_data(hass, config_entry)

    tasks: list[Awaitable] = [
        hass.config_entries.async_forward_entry_unload(config_entry, platform)
        for platform in get_configured_platforms(controller_data)
    ]
    tasks.append(hass.async_add_executor_job(controller_data.controller.stop))
    await asyncio.gather(*tasks)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def map_vera_device(
    vera_device: veraApi.VeraDevice, remap: list[int]
) -> Platform | None:
    """Map vera classes to Home Assistant types."""

    type_map = {
        veraApi.VeraDimmer: Platform.LIGHT,
        veraApi.VeraBinarySensor: Platform.BINARY_SENSOR,
        veraApi.VeraSensor: Platform.SENSOR,
        veraApi.VeraArmableDevice: Platform.SWITCH,
        veraApi.VeraLock: Platform.LOCK,
        veraApi.VeraThermostat: Platform.CLIMATE,
        veraApi.VeraCurtain: Platform.COVER,
        veraApi.VeraSceneController: Platform.SENSOR,
        veraApi.VeraSwitch: Platform.SWITCH,
    }

    def map_special_case(instance_class: type, entity_type: Platform) -> Platform:
        if instance_class is veraApi.VeraSwitch and vera_device.device_id in remap:
            return Platform.LIGHT
        return entity_type

    return next(
        iter(
            map_special_case(instance_class, entity_type)
            for instance_class, entity_type in type_map.items()
            if isinstance(vera_device, instance_class)
        ),
        None,
    )


_DeviceTypeT = TypeVar("_DeviceTypeT", bound=veraApi.VeraDevice)


class VeraDevice(Generic[_DeviceTypeT], Entity):
    """Representation of a Vera device entity."""

    def __init__(
        self, vera_device: _DeviceTypeT, controller_data: ControllerData
    ) -> None:
        """Initialize the device."""
        self.vera_device = vera_device
        self.controller = controller_data.controller

        self._name = self.vera_device.name
        # Append device id to prevent name clashes in HA.
        self.vera_id = VERA_ID_FORMAT.format(
            slugify(vera_device.name), vera_device.vera_device_id
        )

        if controller_data.config_entry.data.get(CONF_LEGACY_UNIQUE_ID):
            self._unique_id = str(self.vera_device.vera_device_id)
        else:
            self._unique_id = f"vera_{controller_data.config_entry.unique_id}_{self.vera_device.vera_device_id}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.controller.register(self.vera_device, self._update_callback)

    def _update_callback(self, _device: _DeviceTypeT) -> None:
        """Update the state."""
        self.schedule_update_ha_state(True)

    def update(self):
        """Force a refresh from the device if the device is unavailable."""
        refresh_needed = self.vera_device.should_poll or not self.available
        _LOGGER.debug("%s: update called (refresh=%s)", self._name, refresh_needed)
        if refresh_needed:
            self.vera_device.refresh()

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attr = {}

        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level

        if self.vera_device.is_armable:
            armed = self.vera_device.is_armed
            attr[ATTR_ARMED] = "True" if armed else "False"

        if self.vera_device.is_trippable:
            if (last_tripped := self.vera_device.last_trip) is not None:
                utc_time = utc_from_timestamp(int(last_tripped))
                attr[ATTR_LAST_TRIP_TIME] = utc_time.isoformat()
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
            tripped = self.vera_device.is_tripped
            attr[ATTR_TRIPPED] = "True" if tripped else "False"

        attr["Vera Device Id"] = self.vera_device.vera_device_id

        return attr

    @property
    def available(self):
        """If device communications have failed return false."""
        return not self.vera_device.comm_failure

    @property
    def unique_id(self) -> str:
        """Return a unique ID.

        The Vera assigns a unique and immutable ID number to each device.
        """
        return self._unique_id
