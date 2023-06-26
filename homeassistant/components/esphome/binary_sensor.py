"""Support for ESPHome binary sensors."""
from __future__ import annotations

from aioesphomeapi import BinarySensorInfo, BinarySensorState, EntityInfo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from .domain_data import DomainData
from .entity import (
    EsphomeAssistEntity,
    EsphomeEntity,
    platform_async_setup_entry,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
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

    entry_data = DomainData.get(hass).get_entry_data(entry)
    assert entry_data.device_info is not None
    if entry_data.device_info.voice_assistant_version:
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
        key="assist_in_progress",
        translation_key="assist_in_progress",
    )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._entry_data.assist_pipeline_state
