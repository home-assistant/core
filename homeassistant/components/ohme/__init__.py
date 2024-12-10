"""The ohme integration."""

from dataclasses import dataclass
import logging

from ohme import OhmeApiClient

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import PLATFORMS
from .coordinator import OhmeAdvancedSettingsCoordinator, OhmeChargeSessionsCoordinator

_LOGGER = logging.getLogger(__name__)

type OhmeConfigEntry = ConfigEntry[OhmeRuntimeData]


@dataclass
class OhmeRuntimeData:
    """Store volatile data."""

    client: OhmeApiClient
    coordinators: list[DataUpdateCoordinator]


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry):
    """Set up Ohme from a config entry."""

    client = OhmeApiClient(entry.data["email"], entry.data["password"])

    entry.runtime_data = OhmeRuntimeData(client, [])

    await client.async_create_session()
    await client.async_update_device_info()

    coordinators = [
        OhmeChargeSessionsCoordinator(
            hass=hass, config_entry=entry
        ),  # COORDINATOR_CHARGESESSIONS
        OhmeAdvancedSettingsCoordinator(
            hass=hass, config_entry=entry
        ),  # COORDINATOR_ADVANCED
    ]

    # We can function without these so setup can continue
    coordinators_optional = [OhmeAdvancedSettingsCoordinator]

    for coordinator in coordinators:
        # Catch failures if this is an 'optional' coordinator
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            allow_failure = False
            for optional in coordinators_optional:
                allow_failure = (
                    True if isinstance(coordinator, optional) else allow_failure
                )

            if allow_failure:
                _LOGGER.error(
                    "%s failed to setup. This coordinator is optional so the integration will still function, but please raise an issue if this persists",
                    coordinator.__class__.__name__,
                )
            else:
                raise

    entry.runtime_data.coordinators = coordinators

    # Setup entities
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
