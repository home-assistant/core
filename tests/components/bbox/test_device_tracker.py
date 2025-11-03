"""Tests for the Bbox device tracker platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import requests

from homeassistant.components.bbox.device_tracker import (
    MIN_TIME_BETWEEN_SCANS,
    PLATFORM_SCHEMA,
    get_scanner,
)
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component


async def test_device_tracker_entities_created(
    hass: HomeAssistant,
    device_tracker_config: dict,
    mock_bbox_api: MagicMock,
) -> None:
    """Test that device tracker entities are created when integration is set up."""
    assert await async_setup_component(
        hass, DEVICE_TRACKER_DOMAIN, device_tracker_config
    )
    await hass.async_block_till_done()

    states = hass.states.async_all(DEVICE_TRACKER_DOMAIN)

    # Each connected device should create a device tracker entity
    assert len(states) == 2

    for state in states:
        assert state.state == STATE_HOME
        assert "scanner" in state.attributes
        assert "source_type" in state.attributes


async def test_device_tracker_no_devices(
    hass: HomeAssistant,
    device_tracker_config: dict,
    mock_bbox_api: MagicMock,
) -> None:
    """Test device tracker when no devices are connected."""
    mock_bbox_api.get_all_connected_devices.return_value = []

    assert await async_setup_component(
        hass, DEVICE_TRACKER_DOMAIN, device_tracker_config
    )
    await hass.async_block_till_done()

    states = hass.states.async_all(DEVICE_TRACKER_DOMAIN)
    assert len(states) == 2
    for state in states:
        assert state.state == STATE_NOT_HOME


async def test_device_tracker_api_failure(
    hass: HomeAssistant,
    device_tracker_config: dict,
    mock_bbox_api: MagicMock,
) -> None:
    """Test device tracker when API fails."""
    mock_bbox_api.get_all_connected_devices.side_effect = Exception("API Error")

    assert await async_setup_component(
        hass, DEVICE_TRACKER_DOMAIN, device_tracker_config
    )
    await hass.async_block_till_done()

    # Verify device tracker entities are created but show as not_home on API failure
    states = hass.states.async_all(DEVICE_TRACKER_DOMAIN)
    assert len(states) == 2
    for state in states:
        assert state.state == STATE_NOT_HOME


async def test_device_tracker_filters_inactive_devices(
    hass: HomeAssistant,
    device_tracker_config: dict,
    mock_bbox_api: MagicMock,
) -> None:
    """Test that inactive devices are filtered out."""
    assert await async_setup_component(
        hass, DEVICE_TRACKER_DOMAIN, device_tracker_config
    )
    await hass.async_block_till_done()

    # Verify only active device tracker entities are created (inactive device filtered out)
    states = hass.states.async_all(DEVICE_TRACKER_DOMAIN)
    assert len(states) == 2

    active_device_names = {"test_device", "another_device"}
    for state in states:
        assert state.state == STATE_HOME
        assert "scanner" in state.attributes
        assert "source_type" in state.attributes
        assert state.attributes.get("friendly_name") in active_device_names


async def test_scan_devices(
    hass: HomeAssistant,
    device_tracker_config: ConfigType,
    mock_bbox_api: MagicMock,
) -> None:
    """Test scanning for devices."""
    scanner = get_scanner(hass, device_tracker_config)
    assert scanner is not None

    devices = scanner.scan_devices()
    assert devices == ["aa:bb:cc:dd:ee:ff", "ff:ee:dd:cc:bb:aa"]
    mock_bbox_api.get_all_connected_devices.assert_called_once()


async def test_get_device_name(
    hass: HomeAssistant,
    device_tracker_config: ConfigType,
    mock_bbox_api: MagicMock,
) -> None:
    """Test getting device name by MAC address."""
    scanner = get_scanner(hass, device_tracker_config)
    assert scanner is not None

    name = scanner.get_device_name("aa:bb:cc:dd:ee:ff")
    assert name == "test_device"
    name = scanner.get_device_name("ff:ee:dd:cc:bb:aa")
    assert name == "another_device"

    # Test non-existing device
    name = scanner.get_device_name("11:22:33:44:55:66")
    assert name is None


async def test_scan_devices_with_throttling(
    hass: HomeAssistant,
    device_tracker_config: ConfigType,
    mock_bbox_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test scan devices respects throttling."""
    scanner = get_scanner(hass, device_tracker_config)
    assert scanner is not None

    # First scan should call the API
    devices = scanner.scan_devices()
    assert devices == ["aa:bb:cc:dd:ee:ff", "ff:ee:dd:cc:bb:aa"]
    assert mock_bbox_api.get_all_connected_devices.call_count == 1

    # Second scan within throttle period should not call API again
    devices = scanner.scan_devices()
    assert devices == ["aa:bb:cc:dd:ee:ff", "ff:ee:dd:cc:bb:aa"]
    assert mock_bbox_api.get_all_connected_devices.call_count == 1

    # After throttle period, API should be called again
    freezer.tick(MIN_TIME_BETWEEN_SCANS + timedelta(seconds=1))
    devices = scanner.scan_devices()
    assert devices == ["aa:bb:cc:dd:ee:ff", "ff:ee:dd:cc:bb:aa"]
    assert mock_bbox_api.get_all_connected_devices.call_count == 2


async def test_scan_devices_failure_recovery(
    hass: HomeAssistant,
    device_tracker_config: ConfigType,
    mock_bbox_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device scanning failure and recovery."""
    scanner = get_scanner(hass, device_tracker_config)
    assert scanner is not None

    devices = scanner.scan_devices()
    assert devices == ["aa:bb:cc:dd:ee:ff", "ff:ee:dd:cc:bb:aa"]

    mock_bbox_api.get_all_connected_devices.side_effect = requests.exceptions.HTTPError(
        "API Error"
    )

    freezer.tick(MIN_TIME_BETWEEN_SCANS + timedelta(seconds=1))
    devices = scanner.scan_devices()
    assert devices == []

    # Recover from failure
    mock_bbox_api.get_all_connected_devices.side_effect = None

    freezer.tick(MIN_TIME_BETWEEN_SCANS + timedelta(seconds=1))
    devices = scanner.scan_devices()
    assert devices == ["aa:bb:cc:dd:ee:ff", "ff:ee:dd:cc:bb:aa"]


async def test_platform_schema() -> None:
    """Test platform schema validation."""
    # Test default host
    config = {"platform": "bbox"}
    validated = PLATFORM_SCHEMA(config)
    assert validated["host"] == "192.168.1.254"

    # Test custom host
    config = {"platform": "bbox", "host": "192.168.2.1"}
    validated = PLATFORM_SCHEMA(config)
    assert validated["host"] == config["host"]
