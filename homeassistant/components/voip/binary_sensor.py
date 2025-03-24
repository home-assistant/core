"""Binary sensor for VoIP."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .devices import VoIPDevice
from .entity import VoIPEntity

if TYPE_CHECKING:
    from . import DomainData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up VoIP binary sensor entities."""
    domain_data: DomainData = hass.data[DOMAIN]

    @callback
    def async_add_device(device: VoIPDevice) -> None:
        """Add device."""
        async_add_entities([VoIPCallInProgress(device)])

    domain_data.devices.async_add_new_device_listener(async_add_device)

    async_add_entities([VoIPCallInProgress(device) for device in domain_data.devices])


class VoIPCallInProgress(VoIPEntity, BinarySensorEntity):
    """Entity to represent voip call is in progress."""

    entity_description = BinarySensorEntityDescription(
        entity_registry_enabled_default=False,
        key="call_in_progress",
        translation_key="call_in_progress",
    )
    _attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self.voip_device.async_listen_update(self._is_active_changed)
        )

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
                "integration_name": "VoIP",
            },
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="assist_in_progress_deprecated",
            translation_placeholders={
                "integration_name": "VoIP",
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

    @callback
    def _is_active_changed(self, device: VoIPDevice) -> None:
        """Call when active state changed."""
        self._attr_is_on = self.voip_device.is_active
        self.async_write_ha_state()
