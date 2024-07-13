"""Setup the Motionblinds Bluetooth tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from motionblindsble.const import MotionBlindType
import pytest

from homeassistant.components.motionblinds_ble.const import (
    CONF_BLIND_TYPE,
    CONF_LOCAL_NAME,
    CONF_MAC_CODE,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS

from . import FIXTURE_ADDRESS, FIXTURE_DISPLAY_NAME, FIXTURE_LOCAL_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def blind_type() -> MotionBlindType:
    """Blind type fixture."""
    return MotionBlindType.ROLLER


@pytest.fixture
def mock_motion_device(blind_type) -> Generator[AsyncMock]:
    """Mock a MotionDevice."""

    with (
        patch(
            "homeassistant.components.motionblinds_ble.MotionDevice",
            autospec=True,
        ) as mock_device,
        patch(
            "homeassistant.components.motionblinds_ble.MotionDevice",
            new=mock_device,
        ),
    ):
        device = mock_device.return_value
        device.ble_device = Mock()
        device.display_name = FIXTURE_DISPLAY_NAME
        device.blind_type = blind_type
        yield device


@pytest.fixture
def mock_config_entry(blind_type: MotionBlindType) -> MockConfigEntry:
    """Config entry fixture."""
    return MockConfigEntry(
        title="mock_title",
        domain=DOMAIN,
        unique_id="cc:cc:cc:cc:cc:cc",
        data={
            CONF_ADDRESS: "cc:cc:cc:cc:cc:cc",
            CONF_LOCAL_NAME: "Motionblind CCCC",
            CONF_MAC_CODE: "CCCC",
            CONF_BLIND_TYPE: blind_type.name.lower(),
        },
    )


@pytest.fixture(name="motionblinds_ble_connect", autouse=True)
def motion_blinds_connect_fixture(
    enable_bluetooth: None,
) -> Generator[tuple[AsyncMock, Mock]]:
    """Mock motion blinds ble connection and entry setup."""
    device = Mock()
    device.name = FIXTURE_LOCAL_NAME
    device.address = FIXTURE_ADDRESS

    bleak_scanner = AsyncMock()
    bleak_scanner.discover.return_value = [device]

    with (
        patch(
            "homeassistant.components.motionblinds_ble.config_flow.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "homeassistant.components.motionblinds_ble.config_flow.bluetooth.async_get_scanner",
            return_value=bleak_scanner,
        ),
        patch(
            "homeassistant.components.motionblinds_ble.async_setup_entry",
            return_value=True,
        ),
    ):
        yield bleak_scanner, device
