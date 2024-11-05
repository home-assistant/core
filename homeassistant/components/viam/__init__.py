"""The viam integration."""

from __future__ import annotations

from viam.app.viam_client import ViamClient
from viam.rpc.dial import DialOptions

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_API_ID, DOMAIN
from .manager import ViamConfigEntry, ViamManager
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Viam services."""

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ViamConfigEntry) -> bool:
    """Set up viam from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    api_key_id = entry.data[CONF_API_ID]

    dial_options = DialOptions.with_api_key(api_key, api_key_id)
    viam_client = await ViamClient.create_from_dial_options(dial_options=dial_options)
    manager = ViamManager(hass, viam_client, entry.entry_id, dict(entry.data))

    entry.runtime_data = manager

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ViamConfigEntry) -> bool:
    """Unload a config entry."""
    manager = entry.runtime_data
    manager.unload()

    return True
