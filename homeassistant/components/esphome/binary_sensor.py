"""Support for ESPHome binary sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aioesphomeapi import BinarySensorInfo, BinarySensorState, EntityInfo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from .const import DOMAIN
from .entity import EsphomeAssistEntity, EsphomeEntity, platform_async_setup_entry
from .entry_data import ESPHomeConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ESPHome binary sensors based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=BinarySensorInfo,
        entity_type=EsphomeBinarySensor,
        state_type=BinarySensorState,
    )

    entry_data = entry.runtime_data
    assert entry_data.device_info is not None
    if entry_data.device_info.voice_assistant_feature_flags_compat(
        entry_data.api_version
    ):
        async_add_entities([EsphomeAssistInProgressBinarySensor(entry_data)])


class EsphomeBinarySensor(
    EsphomeEntity[BinarySensorInfo, BinarySensorState], BinarySensorEntity
):
    """A binary sensor implementation for ESPHome."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self._static_info.is_status_binary_sensor:
            # Status binary sensors indicated connected state.
            # So in their case what's usually _availability_ is now state
            return self._entry_data.available
        if not self._has_state or self._state.missing_state:
            return None
        return self._state.state

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        self._attr_device_class = try_parse_enum(
            BinarySensorDeviceClass, self._static_info.device_class
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._static_info.is_status_binary_sensor or super().available


class EsphomeAssistInProgressBinarySensor(EsphomeAssistEntity, BinarySensorEntity):
    """A binary sensor implementation for ESPHome for use with assist_pipeline."""

    entity_description = BinarySensorEntityDescription(
        entity_registry_enabled_default=False,
        key="assist_in_progress",
        translation_key="assist_in_progress",
    )

    async def async_added_to_hass(self) -> None:
        """Create issue."""
        await super().async_added_to_hass()
        if TYPE_CHECKING:
            assert self.registry_entry is not None
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"assist_in_progress_deprecated_{self.registry_entry.id}",
            breaks_in_ha_version="2025.4",
            data={
                "entity_id": self.entity_id,
                "entity_uuid": self.registry_entry.id,
                "integration_name": "ESPHome",
            },
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="assist_in_progress_deprecated",
            translation_placeholders={
                "integration_name": "ESPHome",
            },
        )

    async def async_will_remove_from_hass(self) -> None:
        """Remove issue."""
        await super().async_will_remove_from_hass()
        if TYPE_CHECKING:
            assert self.registry_entry is not None
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            f"assist_in_progress_deprecated_{self.registry_entry.id}",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._entry_data.assist_pipeline_state
