"""The solax component."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from solax import InverterResponse, RealTimeAPI, discover
from solax.inverter import InverterError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import INVERTER_MODELS
from .coordinator import SolaxDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

SCAN_INTERVAL = timedelta(seconds=30)


@dataclass(slots=True)
class SolaxData:
    """Class for storing solax data."""

    api: RealTimeAPI
    coordinator: SolaxDataUpdateCoordinator


type SolaxConfigEntry = ConfigEntry[SolaxData]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: SolaxConfigEntry) -> bool:
    """Set up the sensors from a ConfigEntry."""

    kwargs: dict[str, Any] = {"return_when": asyncio.FIRST_COMPLETED}
    if model := entry.data.get(CONF_MODEL):
        kwargs["inverters"] = [INVERTER_MODELS[model]]

    try:
        inverter = await discover(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_PORT],
            entry.data[CONF_PASSWORD],
            **kwargs,
        )
    except Exception as err:
        raise ConfigEntryNotReady from err
    api = RealTimeAPI(inverter)

    async def _async_update() -> InverterResponse:
        try:
            return await api.get_data()
        except InverterError as err:
            raise UpdateFailed from err

    coordinator = SolaxDataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        config_entry=entry,
        name=f"solax {entry.title}",
        update_interval=SCAN_INTERVAL,
        update_method=_async_update,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = SolaxData(api=api, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolaxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
