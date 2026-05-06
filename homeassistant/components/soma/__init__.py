"""Support for Soma Smartshades."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.soma_api import SomaApi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, HOST, PORT

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PORT): cv.string}
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class SomaData:
    """Runtime data for the Soma integration."""

    api: SomaApi
    devices: list[dict[str, Any]]


type SomaConfigEntry = ConfigEntry[SomaData]

PLATFORMS = [Platform.COVER, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Soma component."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            data=config[DOMAIN],
            context={"source": config_entries.SOURCE_IMPORT},
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SomaConfigEntry) -> bool:
    """Set up Soma from a config entry."""
    api = await hass.async_add_executor_job(SomaApi, entry.data[HOST], entry.data[PORT])
    devices = await hass.async_add_executor_job(api.list_devices)
    entry.runtime_data = SomaData(api, devices["shades"])

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SomaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
