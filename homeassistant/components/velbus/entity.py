"""Support for Velbus devices."""
from __future__ import annotations

from velbusaio.channels import Channel as VelbusChannel

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class VelbusEntity(Entity):
    """Representation of a Velbus entity."""

    _attr_should_poll: bool = False

    def __init__(self, channel: VelbusChannel) -> None:
        """Initialize a Velbus entity."""
        self._channel = channel
        self._attr_name = channel.get_name()
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, str(channel.get_module_address())),
            },
            manufacturer="Velleman",
            model=channel.get_module_type_name(),
            name=channel.get_full_name(),
            sw_version=channel.get_module_sw_version(),
        )
        serial = channel.get_module_serial() or str(channel.get_module_address())
        self._attr_unique_id = f"{serial}-{channel.get_channel_number()}"

    async def async_added_to_hass(self) -> None:
        """Add listener for state changes."""
        self._channel.on_status_update(self._on_update)

    async def _on_update(self) -> None:
        self.async_write_ha_state()
