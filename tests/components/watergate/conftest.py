"""Fixtures for watergate platform tests."""

from collections.abc import Generator
from copy import deepcopy

import pytest
from pytest_homeassistant.common import AsyncMock, MockConfigEntry, patch
from watergate_local_api.models import AutoShutOffState

from homeassistant.components.watergate.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS

from .const import (
    DEFAULT_DEVICE_STATE,
    DEFAULT_DEVICE_STATE_V2,
    DEFAULT_NETWORKING_STATE,
    DEFAULT_SERIAL_NUMBER,
    DEFAULT_TELEMETRY_STATE,
    MOCK_CONFIG,
    MOCK_WEBHOOK_ID,
)


@pytest.fixture
def mock_watergate_client() -> Generator[AsyncMock]:
    """Fixture to mock WatergateLocalApiClient."""
    with (
        patch(
            "homeassistant.components.watergate.WatergateLocalApiClient",
            autospec=True,
        ) as mock_client_main,
        patch(
            "homeassistant.components.watergate.config_flow.WatergateLocalApiClient",
            new=mock_client_main,
        ),
    ):
        mock_client_instance = mock_client_main.return_value

        # Copy the models per test: webhooks and the switch mutate the coordinator data
        # in place, so shared instances would leak state between tests.
        # The config flow reads device state v1, the coordinator prefers v2 and falls back
        # to v1 on firmware that does not implement it, so both are mocked.
        mock_client_instance.async_get_device_state = AsyncMock(
            return_value=deepcopy(DEFAULT_DEVICE_STATE)
        )
        mock_client_instance.async_get_device_state_v2 = AsyncMock(
            return_value=deepcopy(DEFAULT_DEVICE_STATE_V2)
        )
        mock_client_instance.async_get_networking = AsyncMock(
            return_value=deepcopy(DEFAULT_NETWORKING_STATE)
        )
        mock_client_instance.async_get_telemetry_data = AsyncMock(
            return_value=deepcopy(DEFAULT_TELEMETRY_STATE)
        )
        mock_client_instance.async_get_auto_shut_off = AsyncMock(
            return_value=AutoShutOffState(True, 1000, 60)
        )
        yield mock_client_instance


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.watergate.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_webhook_id_generation() -> Generator[None]:
    """Fixture to mock webhook_id generation."""
    with patch(
        "homeassistant.components.watergate.config_flow.webhook_generate_id",
        return_value=MOCK_WEBHOOK_ID,
    ):
        yield


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Create full mocked entry to be used in config_flow tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sonic",
        data=MOCK_CONFIG,
        entry_id="12345",
        unique_id=DEFAULT_SERIAL_NUMBER,
    )


@pytest.fixture
def user_input() -> dict[str, str]:
    """Create user input for config_flow tests."""
    return {
        CONF_IP_ADDRESS: "192.168.1.100",
    }
