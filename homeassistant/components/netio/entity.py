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

    @property
    def output(self) -> Netio.OUTPUT | None:
        """Return the current data of the output."""
        return self.coordinator.data.get(self._output_id)

    @property
    def output_name(self) -> str:
        """Return the name of the output configured on the device."""
        if (output := self.output) is None or not output.Name:
            return f"Output {self._output_id}"
        return output.Name

    @property
    @override
    def available(self) -> bool:
        """Return True if the output is present in coordinator data."""
        return super().available and self._output_id in self.coordinator.data
