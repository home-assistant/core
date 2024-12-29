"""Provide common fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from ohme import ChargerPower, ChargerStatus
import pytest

from homeassistant.components.ohme.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ohme.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="test@example.com",
        domain=DOMAIN,
        version=1,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "hunter2",
        },
    )


@pytest.fixture
def mock_client():
    """Fixture to mock the OhmeApiClient."""
    with (
        patch(
            "homeassistant.components.ohme.config_flow.OhmeApiClient",
            autospec=True,
        ) as client,
        patch(
            "homeassistant.components.ohme.OhmeApiClient",
            new=client,
        ),
    ):
        client = client.return_value
        client.async_login.return_value = True
        client.status = ChargerStatus.CHARGING
        client.power = ChargerPower(0, 0, 0, 0)

        client.serial = "chargerid"
        client.ct_connected = True
        client.energy = 1000
        client.device_info = {
            "name": "Ohme Home Pro",
            "model": "Home Pro",
            "sw_version": "v2.65",
        }
        yield client
