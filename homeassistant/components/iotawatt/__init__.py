"""The iotawatt integration."""
import logging

from httpx import AsyncClient
from iotawattpy.iotawatt import Iotawatt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import COORDINATOR, DOMAIN
from .coordinator import IotawattUpdater

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up iotawatt from a config entry."""

    session = AsyncClient()
    api = Iotawatt(
        entry.data[CONF_NAME],
        entry.data[CONF_HOST],
        session,
        entry.data.get(CONF_USERNAME, None),
        entry.data.get(CONF_PASSWORD, None),
    )

    coordinator = IotawattUpdater(
        hass,
        api=api,
        name="IoTaWatt",
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True
