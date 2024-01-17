"""Base class for Lutron devices."""

from pylutron import Lutron, LutronEntity, LutronEvent

from homeassistant.helpers.entity import Entity


class LutronDevice(Entity):
    """Representation of a Lutron device entity."""

    _attr_should_poll = False

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

    def _update_callback(
        self, _device: LutronEntity, _context: None, _event: LutronEvent, _params: dict
    ) -> None:
        """Run when invoked by pylutron when the device state changes."""
        self.schedule_update_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{self._area_name} {self._lutron_device.name}"

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        # Temporary fix for https://github.com/thecynic/pylutron/issues/70
        if self._lutron_device.uuid is None:
            return None
        return f"{self._controller.guid}_{self._lutron_device.uuid}"
