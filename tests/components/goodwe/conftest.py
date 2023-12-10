"""Fixtures for the Aladdin Connect integration tests."""
from unittest.mock import AsyncMock, MagicMock

from goodwe import OperationMode
import pytest


@pytest.fixture(name="mock_inverter")
def fixture_mock_inverter():
    """Set up inverter fixture."""
    mock_inverter = MagicMock()
    mock_inverter.arm_version = 1
    mock_inverter.arm_svn_version = 1
    mock_inverter.arm_firmware = "dummy.arm.version"
    mock_inverter.firmware = "dummy.fw.version"
    mock_inverter.model_name = "MOCK"
    mock_inverter.dsp1_version = 0
    mock_inverter.dsp2_version = 0
    mock_inverter.dsp_svn_version = 0

    mock_inverter.read_runtime_data = AsyncMock(return_value={})
    mock_inverter.read_setting = AsyncMock(return_value=None)
    mock_inverter.get_operation_modes = AsyncMock(return_value=())
    mock_inverter.get_operation_mode = AsyncMock(return_value=OperationMode.GENERAL)
    mock_inverter.get_grid_export_limit = AsyncMock(return_value=0)
    mock_inverter.get_ongrid_battery_dod = AsyncMock(return_value=50)
    mock_inverter.sensors.return_value = ()
    mock_inverter.settings.return_value = ()

    return mock_inverter
