# homeassistant/components/pushmeld/__init__.py
"""The PushMeld integration."""

from asyncio import Future
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import CONF_MAXCODE, DATA_HASS_CONFIG, DOMAIN

if TYPE_CHECKING:
    from .notify import PushMeldNotificationService

PLATFORMS = [Platform.NOTIFY]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class PushMeldRuntimeData:
    """Runtime data for a PushMeld config entry."""

    notify_service_ready: Future[None]
    notify_service: PushMeldNotificationService | None = None


type PushMeldConfigEntry = ConfigEntry[PushMeldRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the PushMeld integration."""
    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PushMeldConfigEntry) -> bool:
    """Set up a PushMeld notification service from a config entry."""
    title = entry.title.strip()
    if not title:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="config_entry_error_invalid_name",
        )

    entry.runtime_data = PushMeldRuntimeData(
        notify_service_ready=hass.loop.create_future()
    )

    service_name = slugify(title)
    if hass.services.has_service(NOTIFY_DOMAIN, service_name):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="config_entry_error_name_exists",
            translation_placeholders={"service_name": service_name},
        )

    discovery_task = entry.async_create_task(
        hass,
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                CONF_MAXCODE: entry.data[CONF_MAXCODE],
                CONF_NAME: title,
                "entry_id": entry.entry_id,
            },
            hass.data[DATA_HASS_CONFIG],
        ),
        name="pushmeld notification service",
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    try:
        await entry.runtime_data.notify_service_ready
    except BaseException:
        if not discovery_task.done():
            discovery_task.cancel()
        raise

    return True


async def async_unload_entry(_hass: HomeAssistant, _entry: PushMeldConfigEntry) -> bool:
    """Unload a PushMeld config entry."""
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: PushMeldConfigEntry
) -> None:
    """Reload the notification action when the entry title changes."""
    hass.config_entries.async_schedule_reload(entry.entry_id)
