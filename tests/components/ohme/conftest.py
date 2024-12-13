"""Provide common fixtures."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from ohme import ChargerStatus
import pytest

from homeassistant.components.ohme.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_value_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


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
            "homeassistant.components.ohme.coordinator.OhmeApiClient",
            new=client,
        ),
    ):
        client = client.return_value

        client.status = ChargerStatus.CHARGING
        client.serial = "chargerid"
        client.ct_connected = True
        client.energy = 1000
        client.device_info = {
            "name": "Ohme Home Pro",
            "model": "Home Pro",
            "sw_version": "v2.65",
        }
        yield client


@pytest.fixture(name="mock_session", autouse=True)
def mock_session():
    """Mock aiohttp.ClientSession."""
    mocker = AiohttpClientMocker()

    mocker.post(
        "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword",
        json={"idToken": "", "refreshToken": ""},
    )

    mocker.get(
        "/v1/users/me/account", json=load_json_value_fixture("account.json", DOMAIN)
    )

    mocker.get(
        "/v1/chargeSessions",
        json=load_json_value_fixture("charge_sessions.json", DOMAIN),
    )

    mocker.get(
        "/v1/chargeRules", json=load_json_value_fixture("charge_rules.json", DOMAIN)
    )

    mocker.get(
        "/v1/chargeDevices/chargerid/advancedSettings",
        json=load_json_value_fixture("advanced_settings.json", DOMAIN),
    )

    with patch(
        "aiohttp.ClientSession",
        side_effect=lambda *args, **kwargs: mocker.create_session(
            asyncio.get_event_loop()
        ),
    ):
        yield mocker
