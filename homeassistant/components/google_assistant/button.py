"""Support for buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import GoogleConfigEntry
from .const import CONF_PROJECT_ID, CONF_SERVICE_ACCOUNT, DATA_CONFIG, DOMAIN
from .http import GoogleConfig


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GoogleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the platform."""
    yaml_config: ConfigType = hass.data[DOMAIN][DATA_CONFIG]
    google_config = config_entry.runtime_data

    entities = []

    if CONF_SERVICE_ACCOUNT in yaml_config:
        entities.append(SyncButton(config_entry.data[CONF_PROJECT_ID], google_config))

    async_add_entities(entities)


class SyncButton(ButtonEntity):
    """Representation of a synchronization button."""

    _attr_has_entity_name = True
    _attr_translation_key = "sync_devices"

    def __init__(self, project_id: str, google_config: GoogleConfig) -> None:
        """Initialize button."""
        super().__init__()
        self._google_config = google_config
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_unique_id = f"{project_id}_sync"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, project_id)},
            name="Google Assistant",
        )

    async def async_press(self) -> None:
        """Press the button."""
        assert self._context
        agent_user_id = self._google_config.get_agent_user_id_from_context(
            self._context
        )
        result = await self._google_config.async_sync_entities(agent_user_id)
        if result != 200:
            raise HomeAssistantError(
                f"Unable to sync devices with result code: {result}, check log for more"
                " info."
            )
