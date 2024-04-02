"""Interfaces with TotalConnect buttons."""

import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up TotalConnect buttons based on a config entry."""
    buttons: list = []

    client_locations = hass.data[DOMAIN][entry.entry_id].client.locations

    for location_id, location in client_locations.items():
        buttons.append(TotalConnectClearBypassButton(location))
        buttons.append(TotalConnectBypassAllButton(location))

        buttons.extend(
            TotalConnectZoneBypassButton(location_id, zone)
            for zone in location.zones.values()
            if zone.can_be_bypassed
        )

    async_add_entities(buttons)


class TotalConnectZoneBypassButton(ButtonEntity):
    """Represent an TotalConnect zone bypass button."""

    def __init__(self, location_id, zone):
        """Initialize the TotalConnect status."""
        self._zone = zone
        self.entity_description: ButtonEntityDescription = ButtonEntityDescription(
            key="bypass", name="Bypass", entity_category=EntityCategory.DIAGNOSTIC
        )
        self._attr_name = f"{zone.description} {self.entity_description.name}"
        self._attr_unique_id = (
            f"{location_id}_{zone.zoneid}_{self.entity_description.key}"
        )

    def press(self):
        """Press the bypass button."""
        self._zone.bypass()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        identifier = self._zone.sensor_serial_number or f"zone_{self._zone.zoneid}"
        return DeviceInfo(
            name=self._zone.description,
            identifiers={(DOMAIN, identifier)},
            serial_number=self._zone.sensor_serial_number,
        )


class TotalConnectPanelButton(ButtonEntity):
    """Generic TotalConnect panel button."""

    def __init__(self, location):
        """Initialize the TotalConnect clear bypass button."""
        self._location = location
        self._device = self._location.devices[self._location.security_device_id]
        self._attr_name = f"{self.entity_description.name}"
        self._attr_unique_id = f"{location.location_id}_{self.entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.serial_number)},
            name=self._device.name,
            serial_number=self._device.serial_number,
        )


class TotalConnectClearBypassButton(TotalConnectPanelButton):
    """Clear Bypass button."""

    entity_description: ButtonEntityDescription = ButtonEntityDescription(
        key="clear_bypass",
        name="Clear Bypass",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def press(self):
        """Press the clear bypass button."""
        self._location.clear_bypass()


class TotalConnectBypassAllButton(TotalConnectPanelButton):
    """Bypass All button."""

    entity_description: ButtonEntityDescription = ButtonEntityDescription(
        key="bypass_all", name="Bypass All", entity_category=EntityCategory.DIAGNOSTIC
    )

    def press(self):
        """Press the bypass all button."""
        self._location.zone_bypass_all()
