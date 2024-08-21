"""Common fixtures for the Linear Garage Door tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.linear_garage_door import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.linear_garage_door.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_linear() -> Generator[AsyncMock]:
    """Mock a Linear Garage Door client."""
    with (
        patch(
            "homeassistant.components.linear_garage_door.coordinator.Linear",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.linear_garage_door.config_flow.Linear",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login.return_value = True
        client.get_devices.return_value = load_json_array_fixture(
            "get_devices.json", DOMAIN
        )
        client.get_sites.return_value = load_json_array_fixture(
            "get_sites.json", DOMAIN
        )
        device_states = load_json_object_fixture("get_device_state.json", DOMAIN)
        client.get_device_state.side_effect = lambda device_id: device_states[device_id]
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="acefdd4b3a4a0911067d1cf51414201e",
        title="test-site-name",
        data={
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "test-password",
            "site_id": "test-site-id",
            "device_id": "test-uuid",
        },
    )
