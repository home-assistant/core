"""Fixtures for Discovergy integration tests."""
from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.discovergy import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.discovergy import MockDiscovergy

ComponentSetup = Callable[[], Coroutine[Any, Any, MockDiscovergy]]


@pytest.fixture(name="config_entry")
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MockConfigEntry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="user@example.org",
        unique_id="user@example.org",
        data={CONF_EMAIL: "user@example.org", CONF_PASSWORD: "supersecretpassword"},
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> Callable[[], Coroutine[Any, Any, MockDiscovergy]]:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    async def func() -> MockDiscovergy:
        mock = MockDiscovergy()
        with patch(
            "homeassistant.components.discovergy.coordinator.Discovergy",
            return_value=mock,
        ), patch(
            "homeassistant.components.discovergy.pydiscovergy.Discovergy",
            return_value=mock,
        ):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()
        return mock

    return func
