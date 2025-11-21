"""Satel Integra base entity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from satel_integra.satel_integra import AsyncSatel

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import (
    DOMAIN,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
)

SubentryTypeToEntityType: dict[str, str] = {
    SUBENTRY_TYPE_PARTITION: "alarm_panel",
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT: "switch",
    SUBENTRY_TYPE_ZONE: "zones",
    SUBENTRY_TYPE_OUTPUT: "outputs",
}


class SatelIntegraEntity(Entity):
    """Defines a base Satel Integra entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        controller: AsyncSatel,
        config_entry_id: str,
        subentry: ConfigSubentry,
        device_number: int,
    ) -> None:
        """Initialize the Satel Integra entity."""

        self._satel = controller
        self._device_number = device_number

        entity_type = SubentryTypeToEntityType[subentry.subentry_type]

        if TYPE_CHECKING:
            assert entity_type is not None

        self._attr_unique_id = f"{config_entry_id}_{entity_type}_{device_number}"

        self._attr_device_info = DeviceInfo(
            name=subentry.data[CONF_NAME], identifiers={(DOMAIN, self._attr_unique_id)}
        )
