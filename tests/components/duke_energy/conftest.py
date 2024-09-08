"""Common fixtures for the Duke Energy tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.duke_energy.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> Generator[AsyncMock]:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="test_api")
def mock_controller():
    """Mock a successful Duke Energy API."""
    api = Mock()
    api.authenticate = AsyncMock(
        return_value={
            "email": "TEST@EXAMPLE.COM",
            "cdp_internal_user_id": "test-username",
        }
    )
    api.get_meters = AsyncMock(return_value={})
    with patch(
        "homeassistant.components.duke_energy.config_flow.DukeEnergy",
        return_value=api,
    ):
        yield api
