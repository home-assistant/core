"""Base entities for the Netio integration."""

from typing import override

from Netio import Netio

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NetioDataUpdateCoordinator


class NetioOutputEntity(CoordinatorEntity[NetioDataUpdateCoordinator]):
    """Entity for a single output of a Netio device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NetioDataUpdateCoordinator, output_id: int) -> None:
        """Initialize the output entity."""
        super().__init__(coordinator)
        self._output_id = output_id
        self._attr_device_info = coordinator.device_info
        self._last_output_name: str | None = None

    @property
    def output(self) -> Netio.OUTPUT | None:
        """Return the current data of the output."""
        return self.coordinator.data.get(self._output_id)

    @property
    def output_name(self) -> str:
        """Return the name of the output configured on the device.

        The last known name is kept so the entity name does not flip to a
        generic one while the output is missing from a poll.
        """
        if (output := self.output) is not None:
            self._last_output_name = output.Name or None
        if self._last_output_name is not None:
            return self._last_output_name
        return f"Output {self._output_id}"

    @property
    @override
    def available(self) -> bool:
        """Return True if the output is present in coordinator data."""
        return super().available and self._output_id in self.coordinator.data
