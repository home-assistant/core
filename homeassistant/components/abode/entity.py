"""Support for Abode Security System entities."""

from jaraco.abode.automation import Automation as AbodeAuto
from jaraco.abode.devices.base import Device as AbodeDev

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import AbodeSystem
from .const import ATTRIBUTION, DOMAIN


class AbodeEntity(Entity):
    """Representation of an Abode entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, data: AbodeSystem) -> None:
        """Initialize Abode entity."""
        self._data = data
        self._attr_should_poll = data.polling

    async def async_added_to_hass(self) -> None:
        """Subscribe to Abode connection status updates."""
        await self.hass.async_add_executor_job(
            self._data.abode.events.add_connection_status_callback,
            self.unique_id,
            self._update_connection_status,
        )

        self.hass.data[DOMAIN].entity_ids.add(self.entity_id)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from Abode connection status updates."""
        await self.hass.async_add_executor_job(
            self._data.abode.events.remove_connection_status_callback, self.unique_id
        )

    def _update_connection_status(self) -> None:
        """Update the entity available property."""
        self._attr_available = self._data.abode.events.connected
        self.schedule_update_ha_state()


class AbodeDevice(AbodeEntity):
    """Representation of an Abode device."""

    def __init__(self, data: AbodeSystem, device: AbodeDev) -> None:
        """Initialize Abode device."""
        super().__init__(data)
        self._device = device
        self._attr_unique_id = device.uuid

    async def async_added_to_hass(self) -> None:
        """Subscribe to device events."""
        await super().async_added_to_hass()
        await self.hass.async_add_executor_job(
            self._data.abode.events.add_device_callback,
            self._device.id,
            self._update_callback,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from device events."""
        await super().async_will_remove_from_hass()
        await self.hass.async_add_executor_job(
            self._data.abode.events.remove_all_device_callbacks, self._device.id
        )

    def update(self) -> None:
        """Update device state."""
        self._device.refresh()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return {
            "device_id": self._device.id,
            "battery_low": self._device.battery_low,
            "no_response": self._device.no_response,
            "device_type": self._device.type,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            manufacturer="Abode",
            model=self._device.type,
            name=self._device.name,
        )

    def _update_callback(self, device: AbodeDev) -> None:
        """Update the device state."""
        self.schedule_update_ha_state()


class AbodeAutomation(AbodeEntity):
    """Representation of an Abode automation."""

    def __init__(self, data: AbodeSystem, automation: AbodeAuto) -> None:
        """Initialize for Abode automation."""
        super().__init__(data)
        self._automation = automation
        self._attr_name = automation.name
        self._attr_unique_id = automation.automation_id
        self._attr_extra_state_attributes = {
            "type": "CUE automation",
        }

    def update(self) -> None:
        """Update automation state."""
        self._automation.refresh()
