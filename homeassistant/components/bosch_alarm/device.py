"""Support for connections to a Bosch Alarm Panel."""

from collections.abc import Callable

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


class PanelConnection:
    """Collate information about a given alarm panel."""

    def __init__(self, panel, unique_id, model) -> None:
        """Collate information about a given alarm panel."""
        self.panel = panel
        self.unique_id = unique_id
        self.model = model
        self.on_connect: list[Callable] = []
        panel.connection_status_observer.attach(self._on_connection_status_change)

    def _on_connection_status_change(self):
        if not self.panel.connection_status():
            return
        for on_connect_handler in self.on_connect:
            on_connect_handler()
        self.on_connect.clear()

    def device_info(self):
        """Format the alarm panel information as a DeviceInfo."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=f"Bosch {self.model}",
            manufacturer="Bosch Security Systems",
            model=self.model,
            sw_version=self.panel.firmware_version,
        )

    async def disconnect(self):
        """Stop observing connection status changes."""
        self.panel.connection_status_observer.detach(self._on_connection_status_change)
        await self.panel.disconnect()
