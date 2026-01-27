"""Fixtures for the Aladdin Connect integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from goodwe import Inverter
from goodwe.const import GOODWE_UDP_PORT
import pytest

TEST_HOST = "1.2.3.4"
TEST_PORT = GOODWE_UDP_PORT
TEST_SERIAL = "123456789"


@pytest.fixture(name="mock_inverter")
def fixture_mock_inverter() -> Generator[MagicMock]:
    """Set up inverter fixture."""
    mock_inverter = MagicMock(spec=Inverter)
    mock_inverter.serial_number = TEST_SERIAL
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

    with (
        patch(
            "homeassistant.components.goodwe.config_flow.connect",
            return_value=mock_inverter,
        ),
        patch("homeassistant.components.goodwe.connect", return_value=mock_inverter),
    ):
        yield mock_inverter
