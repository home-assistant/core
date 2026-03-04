"""Fixtures for System Nexa 2 integration tests."""

from collections.abc import Generator
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sn2 import InformationData, InformationUpdate, OnOffSetting, StateChange

from homeassistant.components.systemnexa2.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_MODEL, CONF_NAME
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry


@pytest.fixture(params=[False])
def dimmable(request: pytest.FixtureRequest) -> bool:
    """Return whether device is dimmable."""
    return request.param


@pytest.fixture
def device_info(dimmable: bool) -> dict[str, Any]:
    """Return device configuration based on type."""
    # Create mock settings (same for all devices)
    mock_setting_433mhz = MagicMock(spec=OnOffSetting)
    mock_setting_433mhz.name = "433Mhz"
    mock_setting_433mhz.enable = AsyncMock()
    mock_setting_433mhz.disable = AsyncMock()
    mock_setting_433mhz.is_enabled = MagicMock(return_value=True)

    mock_setting_cloud = MagicMock(spec=OnOffSetting)
    mock_setting_cloud.name = "Cloud Access"
    mock_setting_cloud.enable = AsyncMock()
    mock_setting_cloud.disable = AsyncMock()
    mock_setting_cloud.is_enabled = MagicMock(return_value=False)

    return {
        "name": "In-Wall Dimmer" if dimmable else "Outdoor Smart Plug",
        "model": "WBD-01" if dimmable else "WPO-01",
        "unique_id": "aabbccddee01" if dimmable else "aabbccddee02",
        "host": "10.0.0.101" if dimmable else "10.0.0.100",
        "initial_state": 0.5 if dimmable else 1.0,
        "settings": [mock_setting_433mhz, mock_setting_cloud],
        "dimmable": dimmable,
    }


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.systemnexa2.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_system_nexa_2_device(device_info: dict[str, Any]) -> Generator[MagicMock]:
    """Mock the System Nexa 2 API."""
    with (
        patch(
            "homeassistant.components.systemnexa2.coordinator.Device", autospec=True
        ) as mock_device,
        patch(
            "homeassistant.components.systemnexa2.config_flow.Device", new=mock_device
        ),
    ):
        device = mock_device.return_value
        device.info_data = InformationData(
            name=device_info["name"],
            model=device_info["model"],
            unique_id=device_info["unique_id"],
            sw_version="Test Model Version",
            hw_version="Test HW Version",
            wifi_dbm=-50,
            wifi_ssid="Test WiFi SSID",
            dimmable=device_info["dimmable"],
        )

        device.settings = device_info["settings"]
        device.get_info = AsyncMock()
        device.get_info.return_value = InformationUpdate(information=device.info_data)

        # Mock connect to also send initial state update
        async def mock_connect():
            """Mock connect that sends initial state."""
            # Get the callback that was registered
            if mock_device.initiate_device.call_args:
                on_update = mock_device.initiate_device.call_args.kwargs.get(
                    "on_update"
                )
                if on_update:
                    await on_update(StateChange(state=device_info["initial_state"]))

        device.connect = AsyncMock(side_effect=mock_connect)
        device.disconnect = AsyncMock()
        device.turn_on = AsyncMock()
        device.turn_off = AsyncMock()
        device.toggle = AsyncMock()
        device.set_brightness = AsyncMock()
        mock_device.is_device_supported = MagicMock(return_value=(True, ""))
        mock_device.initiate_device = AsyncMock(return_value=device)

        yield mock_device


@pytest.fixture
def mock_config_entry(device_info: dict[str, Any]) -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=device_info["unique_id"],
        data={
            CONF_HOST: device_info["host"],
            CONF_NAME: device_info["name"],
            CONF_DEVICE_ID: device_info["unique_id"],
            CONF_MODEL: device_info["model"],
        },
    )


@pytest.fixture
def mock_patch_get_host():
    """Mock call to socket gethostbyname function."""
    with patch(
        "homeassistant.components.systemnexa2.config_flow.socket.gethostbyname",
        return_value="192.168.1.1",
    ) as get_host_mock:
        yield get_host_mock


@pytest.fixture
def mock_zeroconf_discovery_info():
    """Return mock zeroconf discovery info."""

    return ZeroconfServiceInfo(
        ip_address=ip_address("10.0.0.131"),
        ip_addresses=[ip_address("10.0.0.131")],
        hostname="systemnexa2_test.local.",
        name="systemnexa2_test._systemnexa2._tcp.local.",
        port=80,
        type="_systemnexa2._tcp.local.",
        properties={"id": "aabbccddee02", "model": "WPO-01", "version": "1.0.0"},
    )
