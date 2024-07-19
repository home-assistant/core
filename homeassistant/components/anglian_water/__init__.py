"""Anglian Water (UK) integration."""

from __future__ import annotations

from dataclasses import dataclass

from pyanglianwater import API, AnglianWater
from pyanglianwater.exceptions import ServiceUnavailableError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_DEVICE_ID, DOMAIN
from .coordinator import AnglianWaterDataUpdateCoordinator

type AnglianWaterConfigEntry = ConfigEntry[AnglianWaterConfig]

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


@dataclass
class AnglianWaterConfig:
    """Represent a config for Anglian Water."""

    coordinator: AnglianWaterDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: AnglianWaterConfigEntry
) -> bool:
    """Set up this integration using UI."""
    try:
        _api = await API.create_via_login_existing_device(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_DEVICE_ID],
        )
    except ServiceUnavailableError as exception:
        raise ConfigEntryNotReady(
            exception, translation_domain=DOMAIN, translation_key="maintenance"
        ) from exception
    aw = AnglianWater()
    aw.api = _api
    # for future:
    aw.current_tariff = "not_set"
    aw.current_tariff_rate = 0.0

    coordinator = AnglianWaterDataUpdateCoordinator(hass=hass, client=aw)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AnglianWaterConfig(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
