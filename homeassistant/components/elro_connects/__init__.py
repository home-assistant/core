"""The Elro Connects integration."""
from __future__ import annotations

import copy
from datetime import timedelta
import logging

from elro.api import K1
from elro.device import ATTR_DEVICE_STATE, STATE_OFFLINE, STATE_UNKNOWN

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_RELOAD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_INTERVAL, DOMAIN
from .device import ElroConnectsK1

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SIREN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elro Connects from a config entry."""

    current_device_set: set | None = None

    async def _async_update_data() -> dict[int, dict]:
        """Update data via API."""
        nonlocal current_device_set
        # get state from coordinator cash in case the current state is unknown
        coordinator_update: dict[int, dict] = copy.deepcopy(coordinator.data or {})
        # set initial state to offline
        for device_id, state_base in coordinator_update.items():
            state_base[ATTR_DEVICE_STATE] = STATE_OFFLINE
        try:
            await elro_connects_api.async_update()
            device_update = copy.deepcopy(elro_connects_api.data)
            for device_id, device_data in device_update.items():
                if device_id not in coordinator_update:
                    # new device, or known state
                    coordinator_update[device_id] = device_data
                elif device_data[ATTR_DEVICE_STATE] == STATE_UNKNOWN:
                    # update device state only, other data is not valid
                    coordinator_update[device_id][ATTR_DEVICE_STATE] = device_data[
                        ATTR_DEVICE_STATE
                    ]
                else:
                    # update full state
                    coordinator_update[device_id] = device_data

        except K1.K1ConnectionError as err:
            raise UpdateFailed(err) from err
        new_set = set(elro_connects_api.data.keys())
        if current_device_set is None:
            current_device_set = new_set
        if new_set - current_device_set:
            current_device_set = new_set
            # New devices discovered, trigger a reload
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RELOAD,
                {},
                blocking=False,
            )
        return coordinator_update

    async def async_reload(call: ServiceCall) -> None:
        """Reload the integration."""
        await async_unload_entry(hass, entry)
        await async_setup_entry(hass, entry)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN.title(),
        update_method=_async_update_data,
        update_interval=timedelta(seconds=DEFAULT_INTERVAL),
    )
    elro_connects_api = ElroConnectsK1(
        coordinator,
        entry,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = elro_connects_api

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    entry.async_on_unload(
        entry.add_update_listener(elro_connects_api.async_update_settings)
    )
    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_RELOAD, async_reload
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    elro_connects_api: ElroConnectsK1 = hass.data[DOMAIN][entry.entry_id]
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await elro_connects_api.async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
