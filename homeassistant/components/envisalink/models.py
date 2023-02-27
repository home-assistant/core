"""Models for Envisalink."""
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, LOGGER


class EnvisalinkDevice(Entity):
    """Representation of an Envisalink device."""

    def __init__(self, name, controller, state_update_type, state_update_key):
        """Initialize the device."""
        self._controller = controller
        self._attr_should_poll = False
        self._attr_name = name
        self._state_update_type = state_update_type
        self._state_update_key = state_update_key

    async def async_added_to_hass(self) -> None:
        """Register this entity to receive state change updates from the underlying device."""

        def state_updated():
            LOGGER.debug("state_updated for '%s'", self._attr_name)
            self.async_write_ha_state()

        self.async_on_remove(
            self._controller.add_state_change_listener(
                self._state_update_type, self._state_update_key, state_updated
            )
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this WLED device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._controller.unique_id)},
            name=self._controller.alarm_name,
            manufacturer="eyezon",
            model=(
                f"Envisalink {self._controller.controller.envisalink_version}: "
                f"{self._controller.controller.panel_type}"
            ),
            sw_version=self._controller.controller.firmware_version,
            hw_version=self._controller.controller.envisalink_version,
            configuration_url=f"http://{self._controller.controller.host}",
        )

    @property
    def available(self) -> bool:
        """Return if this entity is available or not."""
        return self._controller.available and super().available
