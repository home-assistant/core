"""Base class for Lutron devices."""

from typing import override

from pylutron import Keypad, Lutron, LutronEntity, LutronEvent

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class LutronBaseEntity(Entity):
    """Base class for Lutron entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, area_name: str, lutron_device: LutronEntity, controller: Lutron
    ) -> None:
        """Initialize the device."""
        self._lutron_device = lutron_device
        self._controller = controller
        self._area_name = area_name

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._lutron_device.subscribe(self._update_callback, None)

    def _request_state(self) -> None:
        """Request the state."""

    def _update_attrs(self) -> None:
        """Update the entity's attributes."""

    def _update_callback(
        self, _device: LutronEntity, _context: None, _event: LutronEvent, _params: dict
    ) -> None:
        """Run when invoked by pylutron when the device state changes."""
        self._update_attrs()
        self.schedule_update_ha_state()

    @property
    @override
    def unique_id(self) -> str:
        """Return a unique ID."""
        device_uuid = self._lutron_device.uuid or self._lutron_device.legacy_uuid
        return f"{self._controller.guid}_{device_uuid}"

    def update(self) -> None:
        """Update the entity's state."""
        self._request_state()
        self._update_attrs()


class LutronDevice(LutronBaseEntity):
    """Representation of a Lutron device entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        area_name: str,
        lutron_device: LutronEntity,
        controller: Lutron,
        config_entry_id: str,
    ) -> None:
        """Initialize the device."""
        super().__init__(area_name, lutron_device, controller)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Lutron",
            name=lutron_device.name,
            suggested_area=area_name,
            via_device_id=dr.async_get_device_id_by_identifier(
                hass, (DOMAIN, controller.guid), config_entry_id=config_entry_id
            ),
        )


class LutronKeypad(LutronBaseEntity):
    """Representation of a Lutron Keypad."""

    def __init__(
        self,
        hass: HomeAssistant,
        area_name: str,
        lutron_device: LutronEntity,
        controller: Lutron,
        keypad: Keypad,
        config_entry_id: str,
    ) -> None:
        """Initialize the device."""
        super().__init__(area_name, lutron_device, controller)
        self._keypad = keypad
        device_uuid = keypad.uuid or keypad.legacy_uuid
        identifiers = {(DOMAIN, f"{controller.guid}_{device_uuid}")}
        # The main repeater keypad is the controller device itself, so it owns
        # the controller identifier instead of linking to it via a via device.
        if keypad.type == "MAIN_REPEATER":
            identifiers.add((DOMAIN, controller.guid))
            self._attr_device_info = DeviceInfo(
                identifiers=identifiers,
                manufacturer="Lutron",
                name=keypad.name,
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers=identifiers,
                manufacturer="Lutron",
                name=keypad.name,
                via_device_id=dr.async_get_device_id_by_identifier(
                    hass, (DOMAIN, controller.guid), config_entry_id=config_entry_id
                ),
            )
