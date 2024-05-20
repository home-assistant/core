"""The solax component."""

from dataclasses import dataclass
import logging

from solax import InverterResponse, RealTimeAPI, real_time_api
from solax.inverter import InverterError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

PLATFORMS = [Platform.SENSOR]


@dataclass(slots=True)
class SolaxData:
    """Class for storing solax data."""

    api: RealTimeAPI
    coordinator: DataUpdateCoordinator[InverterResponse]


type SolaxConfigEntry = ConfigEntry[SolaxData]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: SolaxConfigEntry) -> bool:
    """Set up the sensors from a ConfigEntry."""

    try:
        api = await real_time_api(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_PORT],
            entry.data[CONF_PASSWORD],
        )
    except Exception as err:
        raise ConfigEntryNotReady from err

    async def _async_update() -> InverterResponse:
        try:
            return await api.get_data()
        except InverterError as err:
            raise UpdateFailed from err

    coordinator = DataUpdateCoordinator[InverterResponse](
        hass,
        logger=_LOGGER,
        name=f"solax {entry.title}",
        update_method=_async_update,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = SolaxData(api=api, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolaxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
