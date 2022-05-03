"""The Elro Connects integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from elro.api import K1

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, SERVICE_RELOAD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CONNECTOR_ID, DEFAULT_INTERVAL, DOMAIN
from .device import ElroConnectsK1

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SIREN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elro Connects from a config entry."""

    current_device_set: set | None = None

    async def _async_update_data() -> dict[int, dict]:
        """Update data via API."""
        nonlocal current_device_set
        try:
            await elro_connects_api.async_update()
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
        return elro_connects_api.data

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
        entry.data[CONF_HOST],
        entry.data[CONF_CONNECTOR_ID],
        entry.data[CONF_PORT],
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
