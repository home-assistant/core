"""Base class for Lutron devices."""

from pylutron import Keypad, Lutron, LutronEntity, LutronEvent

from homeassistant.const import ATTR_IDENTIFIERS, ATTR_VIA_DEVICE
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
    def unique_id(self) -> str:
        """Return a unique ID."""

        if self._lutron_device.uuid is None:
            return f"{self._controller.guid}_{self._lutron_device.legacy_uuid}"
        return f"{self._controller.guid}_{self._lutron_device.uuid}"

    def update(self) -> None:
        """Update the entity's state."""
        self._request_state()
        self._update_attrs()


class LutronDevice(LutronBaseEntity):
    """Representation of a Lutron device entity."""

    def __init__(
        self, area_name: str, lutron_device: LutronEntity, controller: Lutron
    ) -> None:
        """Initialize the device."""
        super().__init__(area_name, lutron_device, controller)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Lutron",
            name=lutron_device.name,
            suggested_area=area_name,
            via_device=(DOMAIN, controller.guid),
        )


class LutronKeypad(LutronBaseEntity):
    """Representation of a Lutron Keypad."""

    def __init__(
        self,
        area_name: str,
        lutron_device: LutronEntity,
        controller: Lutron,
        keypad: Keypad,
    ) -> None:
        """Initialize the device."""
        super().__init__(area_name, lutron_device, controller)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, keypad.id)},
            manufacturer="Lutron",
            name=keypad.name,
        )
        if keypad.type == "MAIN_REPEATER":
            self._attr_device_info[ATTR_IDENTIFIERS].add((DOMAIN, controller.guid))
        else:
            self._attr_device_info[ATTR_VIA_DEVICE] = (DOMAIN, controller.guid)
