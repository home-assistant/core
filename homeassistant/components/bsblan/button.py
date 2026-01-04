"""Button platform for BSB-Lan integration."""

from __future__ import annotations

from bsblan import BSBLANError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BSBLanConfigEntry, BSBLanData
from .const import DOMAIN
from .coordinator import BSBLanFastCoordinator
from .entity import BSBLanEntity

PARALLEL_UPDATES = 1

BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="sync_time",
        translation_key="sync_time",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BSBLanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BSB-Lan button entities from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        BSBLanButtonEntity(data.fast_coordinator, data, description)
        for description in BUTTON_DESCRIPTIONS
    )


class BSBLanButtonEntity(BSBLanEntity, ButtonEntity):
    """Defines a BSB-Lan button entity."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: BSBLanFastCoordinator,
        data: BSBLanData,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize BSB-Lan button entity."""
        super().__init__(coordinator, data)
        self.entity_description = description
        self._attr_unique_id = f"{data.device.MAC}-{description.key}"
        self._client = data.client

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.key == "sync_time":
            await self._async_sync_time()

    async def _async_sync_time(self) -> None:
        """Synchronize BSB-LAN device time with Home Assistant."""
        try:
            device_time = await self._client.time()
            current_time = dt_util.now()
            current_time_str = current_time.strftime("%d.%m.%Y %H:%M:%S")

            # Only sync if device time differs from HA time
            if device_time.time.value != current_time_str:
                await self._client.set_time(current_time_str)
        except BSBLANError as err:
            device_name = "Unknown"
            if self._attr_device_info:
                device_name = str(self._attr_device_info.get("name", "Unknown"))
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="sync_time_failed",
                translation_placeholders={
                    "device_name": device_name,
                    "error": str(err),
                },
            ) from err
