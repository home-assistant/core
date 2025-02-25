"""Support for connections to a Bosch Alarm Panel."""

from collections.abc import Callable


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

    async def disconnect(self):
        """Stop observing connection status changes."""
        self.panel.connection_status_observer.detach(self._on_connection_status_change)
        await self.panel.disconnect()
