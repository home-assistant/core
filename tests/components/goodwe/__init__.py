"""Tests for the Goodwe integration."""
from typing import Any

from goodwe import Inverter, OperationMode, Sensor


class MockInverter(Inverter):
    """Mock implementation of inverter abstract class."""

    def __init__(self) -> None:
        """Mock inverter constructor."""
        super().__init__("localhost")
        self.arm_version = 1
        self.arm_firmware = "dummy.arm.version"
        self.firmware = "dummy.fw.version"
        self.model_name = "MOCK"

    async def read_device_info(self):
        """Request the device information from the inverter."""

    async def read_runtime_data(
        self, include_unknown_sensors: bool = False
    ) -> dict[str, Any]:
        """Request the runtime data from the inverter."""
        return {}

    async def read_setting(self, setting_id: str) -> Any:
        """Read the value of specific inverter setting/configuration parameter."""
        return None

    async def write_setting(self, setting_id: str, value: Any) -> None:
        """Set the value of specific inverter settings/configuration parameter."""

    async def read_settings_data(self) -> dict[str, Any]:
        """Request the settings data from the inverter."""
        return {}

    async def get_grid_export_limit(self) -> int:
        """Get the current grid export limit in W."""
        return 0

    async def set_grid_export_limit(self, export_limit: int) -> None:
        """Set the current grid export limit in W."""

    async def get_operation_modes(
        self, include_emulated: bool
    ) -> tuple[OperationMode, ...]:
        """Return list of supported inverter operation modes."""
        return ()

    async def get_operation_mode(self) -> OperationMode:
        """Get the inverter operation mode."""
        return OperationMode.GENERAL

    async def set_operation_mode(
        self,
        operation_mode: OperationMode,
        eco_mode_power: int = 100,
        eco_mode_soc: int = 100,
    ) -> None:
        """Set the inverter operation mode."""

    async def get_ongrid_battery_dod(self) -> int:
        """Get the On-Grid Battery DoD."""
        return 0

    async def set_ongrid_battery_dod(self, dod: int) -> None:
        """Set the On-Grid Battery DoD."""

    def sensors(self) -> tuple[Sensor, ...]:
        """Return tuple of sensor definitions."""
        return ()

    def settings(self) -> tuple[Sensor, ...]:
        """Return tuple of settings definitions."""
        return ()
