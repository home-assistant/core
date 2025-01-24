"""Home Assistant DVS Portal Integration.

This integration allows Home Assistant to interact with the DVS Portal API,
retrieving data such as parking balance, and managing car reservations.
"""

import logging
from typing import TypedDict

from dvsportal import DVSPortal, exceptions as dvs_exceptions

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .coordinator import DVSPortalCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class DVSPortalRuntimeData(TypedDict):
    """Typed runtime data for dvsportal."""

    dvs_portal: DVSPortal
    coordinator: DVSPortalCoordinator
    ha_registered_license_plates: set[str]


type DVSPortalConfigEntry = ConfigEntry[DVSPortalRuntimeData]


async def async_setup_entry(
    hass: core.HomeAssistant, entry: DVSPortalConfigEntry
) -> bool:
    """Set up the dvsportal component from a config entry."""

    api_host = entry.data[CONF_HOST]
    identifier = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    user_agent = entry.data.get("user_agent", "HomeAssistant")

    dvs_portal = DVSPortal(
        api_host=api_host,
        identifier=identifier,
        password=password,
        user_agent=user_agent,
    )

    try:
        # Verify login still works
        await dvs_portal.token()

        # Setup and init stuff
        coordinator = DVSPortalCoordinator(hass, dvs_portal)

        entry.runtime_data = DVSPortalRuntimeData(
            dvs_portal=dvs_portal,
            coordinator=coordinator,
            ha_registered_license_plates=set(),
        )
        await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

        # Check if the first refresh is successful
        await coordinator.async_config_entry_first_refresh()
    except dvs_exceptions.DVSPortalError as ex:
        await dvs_portal.close()
        raise exceptions.ConfigEntryNotReady("Failed to initialize DVSPortal") from ex

    async def async_unload_entry(
        hass: core.HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Unload a config entry."""
        runtime_data: DVSPortalRuntimeData = entry.runtime_data

        # Ensure dvs_portal.close() is called to clean up the session
        if dvs_portal := runtime_data.get("dvs_portal"):
            try:
                await dvs_portal.close()
            except Exception as ex:  # noqa: BLE001
                _LOGGER.warning("Failed to close DVSPortal session: %s", ex)

        unload_ok = await hass.config_entries.async_forward_entry_unload(
            entry, "sensor"
        )
        if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id)

        return unload_ok

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_{entry.entry_id}_unload", async_unload_entry
        )
    )

    async def async_update_options(
        hass: core.HomeAssistant, entry: config_entries.ConfigEntry
    ):
        """Update options."""
        await hass.config_entries.async_reload(entry.entry_id)

    entry.add_update_listener(async_update_options)

    return True
