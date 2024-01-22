"""Entity representing a Netgear LTE entity."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from . import ModemData
from .const import DISPATCHER_NETGEAR_LTE, DOMAIN, MANUFACTURER


class LTEEntity(Entity):
    """Base LTE entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        config_entry: ConfigEntry,
        modem_data: ModemData,
        description: EntityDescription,
    ) -> None:
        """Initialize a Netgear LTE entity."""
        self.entity_description = description
        self.modem_data = modem_data
        self._attr_unique_id = f"{description.key}_{modem_data.data.serial_number}"
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{config_entry.data[CONF_HOST]}",
            identifiers={(DOMAIN, modem_data.data.serial_number)},
            manufacturer=MANUFACTURER,
            model=modem_data.data.items["general.model"],
            serial_number=modem_data.data.serial_number,
            sw_version=modem_data.data.items["general.fwversion"],
            hw_version=modem_data.data.items["general.hwversion"],
        )

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
