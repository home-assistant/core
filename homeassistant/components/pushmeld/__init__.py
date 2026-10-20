# homeassistant/components/pushmeld/__init__.py
"""The PushMeld integration."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import CONF_MAXCODE, DATA_HASS_CONFIG, DOMAIN

if TYPE_CHECKING:
    from .notify import PushMeldNotificationService

PLATFORMS = [Platform.NOTIFY]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class PushMeldRuntimeData:
    """Runtime data for a PushMeld config entry."""

    notify_service: PushMeldNotificationService | None = None


type PushMeldConfigEntry = ConfigEntry[PushMeldRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the PushMeld integration."""
    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PushMeldConfigEntry) -> bool:
    """Set up a PushMeld notification service from a config entry."""
    entry.runtime_data = PushMeldRuntimeData()

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                CONF_NAME: entry.data[CONF_NAME],
                CONF_MAXCODE: entry.data[CONF_MAXCODE],
                "entry_id": entry.entry_id,
            },
            hass.data[DATA_HASS_CONFIG],
        ),
        name="pushmeld notification service",
    )
    return True


async def async_unload_entry(_hass: HomeAssistant, entry: PushMeldConfigEntry) -> bool:
    """Unload a PushMeld config entry."""
    if notify_service := entry.runtime_data.notify_service:
        await notify_service.async_unregister_services()
        entry.runtime_data.notify_service = None

    return True
