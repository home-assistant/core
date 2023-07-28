"""Entity representing a Netgear LTE entity."""

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import ModemData
from .const import DISPATCHER_NETGEAR_LTE


class LTEEntity(Entity):
    """Base LTE entity."""

    _attr_should_poll = False

    def __init__(
        self,
        modem_data: ModemData,
        sensor_type: str,
    ) -> None:
        """Initialize a Netgear LTE entity."""
        self.modem_data = modem_data
        self.sensor_type = sensor_type
        self._attr_name = f"Netgear LTE {sensor_type}"
        self._attr_unique_id = f"{sensor_type}_{modem_data.data.serial_number}"

    async def async_added_to_hass(self) -> None:
        """Register callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCHER_NETGEAR_LTE, self.async_write_ha_state
            )
        )

    async def async_update(self) -> None:
        """Force update of state."""
        await self.modem_data.async_update()

    @property
    def available(self) -> bool:
        """Return the availability of the sensor."""
        return self.modem_data.data is not None
