"""Configuration for the Imeon Inverter integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.imeon_inverter.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture, patch

# Sample test data
TEST_USER_INPUT = {
    CONF_ADDRESS: "192.168.200.1",
    CONF_USERNAME: "user@local",
    CONF_PASSWORD: "password",
}

TEST_SERIAL = "111111111111111"


@pytest.fixture
def mock_imeon_inverter() -> Generator[MagicMock]:
    """Mock data from the device."""
    with (
        patch(
            "homeassistant.components.imeon_inverter.coordinator.Inverter",
            autospec=True,
        ) as inverter_mock,
    ):
        inverter = inverter_mock.return_value
        inverter.storage = load_json_object_fixture("sensor_data.json", DOMAIN)
        yield inverter


@pytest.fixture
def mock_login() -> Generator[AsyncMock]:
    """Fixture for mocking login."""
    with (
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.login",
        ) as mock,
    ):
        yield mock


@pytest.fixture
def mock_serial() -> Generator[AsyncMock]:
    """Fixture for mocking serial."""
    with (
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter.get_serial",
        ) as mock,
    ):
        yield mock


@pytest.fixture
def mock_login_async_setup_entry() -> Generator[AsyncMock]:
    """Fixture for mocking login and async_setup_entry."""
    with (
        patch(
            "homeassistant.components.imeon_inverter.async_setup_entry",
            return_value=True,
        ) as mock,
    ):
        yield mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=TEST_USER_INPUT,
        unique_id=TEST_SERIAL,
    )
