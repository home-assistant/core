"""Support for RainMachine devices."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from functools import partial
from typing import Any

from regenmaschine import Client
from regenmaschine.controller import Controller
from regenmaschine.errors import RainMachineError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util.network import is_ip_address

from .config_flow import get_client_controller
from .const import (
    CONF_ZONE_RUN_TIME,
    DATA_CONTROLLER,
    DATA_COORDINATOR,
    DATA_PROGRAMS,
    DATA_PROVISION_SETTINGS,
    DATA_RESTRICTIONS_CURRENT,
    DATA_RESTRICTIONS_UNIVERSAL,
    DATA_ZONES,
    DOMAIN,
    LOGGER,
)

DEFAULT_ATTRIBUTION = "Data provided by Green Electronics LLC"
DEFAULT_ICON = "mdi:water"
DEFAULT_SSL = True
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=15)

CONFIG_SCHEMA = cv.deprecated(DOMAIN)

PLATFORMS = ["binary_sensor", "sensor", "switch"]


async def async_update_programs_and_zones(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Update program and zone DataUpdateCoordinators.

    Program and zone updates always go together because of how linked they are:
    programs affect zones and certain combinations of zones affect programs.
    """
    await asyncio.gather(
        *[
            hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
                DATA_PROGRAMS
            ].async_refresh(),
            hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
                DATA_ZONES
            ].async_refresh(),
        ]
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RainMachine as config entry."""
    hass.data.setdefault(DOMAIN, {DATA_CONTROLLER: {}, DATA_COORDINATOR: {}})
    hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id] = {}
    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(session=websession)

    try:
        await client.load_local(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_PASSWORD],
            port=entry.data[CONF_PORT],
            ssl=entry.data.get(CONF_SSL, DEFAULT_SSL),
        )
    except RainMachineError as err:
        raise ConfigEntryNotReady from err

    # regenmaschine can load multiple controllers at once, but we only grab the one
    # we loaded above:
    controller = hass.data[DOMAIN][DATA_CONTROLLER][
        entry.entry_id
    ] = get_client_controller(client)

    entry_updates: dict[str, Any] = {}
    if not entry.unique_id or is_ip_address(entry.unique_id):
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = controller.mac
    if CONF_ZONE_RUN_TIME in entry.data:
        # If a zone run time exists in the config entry's data, pop it and move it to
        # options:
        data = {**entry.data}
        entry_updates["data"] = data
        entry_updates["options"] = {
            **entry.options,
            CONF_ZONE_RUN_TIME: data.pop(CONF_ZONE_RUN_TIME),
        }
    if entry_updates:
        hass.config_entries.async_update_entry(entry, **entry_updates)

    async def async_update(api_category: str) -> dict:
        """Update the appropriate API data based on a category."""
        data: dict = {}

        try:
            if api_category == DATA_PROGRAMS:
                data = await controller.programs.all(include_inactive=True)
            elif api_category == DATA_PROVISION_SETTINGS:
                data = await controller.provisioning.settings()
            elif api_category == DATA_RESTRICTIONS_CURRENT:
                data = await controller.restrictions.current()
            elif api_category == DATA_RESTRICTIONS_UNIVERSAL:
                data = await controller.restrictions.universal()
            else:
                data = await controller.zones.all(details=True, include_inactive=True)
        except RainMachineError as err:
            raise UpdateFailed(err) from err

        return data

    controller_init_tasks = []
    for api_category in (
        DATA_PROGRAMS,
        DATA_PROVISION_SETTINGS,
        DATA_RESTRICTIONS_CURRENT,
        DATA_RESTRICTIONS_UNIVERSAL,
        DATA_ZONES,
    ):
        coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
            api_category
        ] = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f'{controller.name} ("{api_category}")',
            update_interval=DEFAULT_UPDATE_INTERVAL,
            update_method=partial(async_update, api_category),
        )
        controller_init_tasks.append(coordinator.async_refresh())

    await asyncio.gather(*controller_init_tasks)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an RainMachine config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATOR].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class RainMachineEntity(CoordinatorEntity):
    """Define a generic RainMachine entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        controller: Controller,
        entity_type: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_info = {
            "identifiers": {(DOMAIN, controller.mac)},
            "connections": {(dr.CONNECTION_NETWORK_MAC, controller.mac)},
            "name": controller.name,
            "manufacturer": "RainMachine",
            "model": (
                f"Version {controller.hardware_version} "
                f"(API: {controller.api_version})"
            ),
            "sw_version": controller.software_version,
        }
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        # The colons are removed from the device MAC simply because that value
        # (unnecessarily) makes up the existing unique ID formula and we want to avoid
        # a breaking change:
        self._attr_unique_id = f"{controller.mac.replace(':', '')}_{entity_type}"
        self._controller = controller
        self._entity_type = entity_type

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        raise NotImplementedError
