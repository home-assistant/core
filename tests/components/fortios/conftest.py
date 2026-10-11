"""Fixtures for FortiOS tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.fortios.client import FortiOSDevice
from homeassistant.components.fortios.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_VERIFY_SSL

from tests.common import MockConfigEntry

USER_INPUT = {CONF_HOST: "192.168.1.1", CONF_TOKEN: "test-token", CONF_VERIFY_SSL: True}
MAC = "AA:BB:CC:DD:EE:FF"
SERIAL = "FGT123456"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Provide a configured device."""
    return MockConfigEntry(domain=DOMAIN, data=USER_INPUT, unique_id=SERIAL)


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the library boundary for both setup and config flow."""
    with (
        patch(
            "homeassistant.components.fortios.FortiOSClient", autospec=True
        ) as factory,
        patch(
            "homeassistant.components.fortios.config_flow.FortiOSClient", new=factory
        ),
    ):
        client = factory.return_value
        client.serial = SERIAL
        client.connect.return_value = SERIAL
        client.update.return_value = {MAC: FortiOSDevice(MAC, "phone", True)}
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Avoid loading the platform in config-flow tests."""
    with patch(
        "homeassistant.components.fortios.async_setup_entry", return_value=True
    ) as mock:
        yield mock
