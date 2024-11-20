"""The Z-Wave-Me WS integration."""

from zwave_me_ws import ZWaveMeData

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class ZWaveMeEntity(Entity):
    """Representation of a ZWaveMe device."""

    def __init__(self, controller, device):
        """Initialize the device."""
        self.controller = controller
        self.device = device
        self._attr_name = device.title
        self._attr_unique_id: str = (
            f"{self.controller.config.unique_id}-{self.device.id}"
        )
        self._attr_should_poll = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.deviceIdentifier)},
            name=self._attr_name,
            manufacturer=self.device.manufacturer,
            sw_version=self.device.firmware,
            suggested_area=self.device.locationName,
        )

    async def async_added_to_hass(self) -> None:
        """Connect to an updater."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"ZWAVE_ME_INFO_{self.device.id}", self.get_new_data
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"ZWAVE_ME_UNAVAILABLE_{self.device.id}",
                self.set_unavailable_status,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"ZWAVE_ME_DESTROY_{self.device.id}", self.delete_entity
            )
        )

    @callback
    def get_new_data(self, new_data: ZWaveMeData) -> None:
        """Update info in the HAss."""
        self.device = new_data
        self._attr_available = not new_data.isFailed
        self.async_write_ha_state()

    @callback
    def set_unavailable_status(self):
        """Update status in the HAss."""
        self._attr_available = False
        self.async_write_ha_state()

    @callback
    def delete_entity(self) -> None:
        """Remove this entity."""
        self.hass.async_create_task(self.async_remove(force_remove=True))
