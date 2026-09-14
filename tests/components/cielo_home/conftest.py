"""Common fixtures for the Cielo Home tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.cielo_home.const import DOMAIN
from homeassistant.components.climate import HVACMode
from homeassistant.const import CONF_API_KEY, CONF_TOKEN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry for the Cielo Home integration."""
    with patch(
        "homeassistant.components.cielo_home.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_cielo_client() -> Generator[MagicMock]:
    """Mock the CieloClient to prevent actual API calls during init."""
    with (
        patch(
            "homeassistant.components.cielo_home.coordinator.CieloClient", autospec=True
        ) as mock_client_cls,
        patch(
            "homeassistant.components.cielo_home.config_flow.CieloClient",
            autospec=True,
        ),
    ):
        client = mock_client_cls.return_value

        # Fake device
        dev = MagicMock()
        dev.id = "device_1"
        dev.name = "Living Room"
        dev.mac_address = "AA:BB:CC:DD:EE:FF"
        dev.device_status = True
        dev.preset_modes = ["sleep"]
        dev.humidity = 40

        mock_data = MagicMock()
        mock_data.raw = {}
        mock_data.parsed = {"device_1": dev}

        client.get_devices_data = AsyncMock(return_value=mock_data)

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for the Cielo Home integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-user-1",
        data={CONF_API_KEY: "test-api-key-", CONF_TOKEN: "valid-test-token"},
    )


@pytest.fixture
def mock_cielo_device_api() -> Generator[MagicMock]:
    """Mock the CieloDeviceAPI to prevent actual device API calls."""
    device_api = MagicMock()
    device_api.temperature_unit.return_value = "°C"
    device_api.min_temp.return_value = 10
    device_api.max_temp.return_value = 35
    device_api.target_temperature_step.return_value = 1
    device_api.hvac_mode.return_value = HVACMode.COOL
    device_api.hvac_modes.return_value = [HVACMode.OFF, HVACMode.COOL]
    device_api.mode_supports_temperature.return_value = True
    device_api.mode_caps.return_value = {"fan_levels": True, "swing": True}
    device_api.current_temperature.return_value = 22
    device_api.target_temperature.return_value = 24
    device_api.fan_modes.return_value = ["auto", "low", "high"]
    device_api.preset_modes.return_value = ["home", "away"]
    device_api.swing_modes.return_value = ["auto", "pos1", "pos2"]
    device_api.async_set_temperature = AsyncMock(
        return_value={"data": {"target_temperature": 25}}
    )

    with patch(
        "homeassistant.components.cielo_home.entity.CieloDeviceAPI",
        return_value=device_api,
    ):
        yield device_api
