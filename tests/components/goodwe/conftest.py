"""Fixtures for the Aladdin Connect integration tests."""

from unittest.mock import AsyncMock, MagicMock

from goodwe import Inverter
import pytest


@pytest.fixture(name="mock_inverter")
def fixture_mock_inverter():
    """Set up inverter fixture."""
    mock_inverter = MagicMock(spec=Inverter)
    mock_inverter.serial_number = "dummy_serial_nr"
    mock_inverter.arm_version = 1
    mock_inverter.arm_svn_version = 2
    mock_inverter.arm_firmware = "dummy.arm.version"
    mock_inverter.firmware = "dummy.fw.version"
    mock_inverter.model_name = "MOCK"
    mock_inverter.rated_power = 10000
    mock_inverter.dsp1_version = 3
    mock_inverter.dsp2_version = 4
    mock_inverter.dsp_svn_version = 5

    mock_inverter.read_runtime_data = AsyncMock(return_value={})

    return mock_inverter
