"""Define test fixtures for Blue Current."""
from asyncio import Future

import pytest

from homeassistant.components.blue_current.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture() -> MockConfigEntry:
    """Define a config entry fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="uuid",
        unique_id="1234",
        data={"api_token": "123"},
    )


@pytest.fixture(name="future")
def future_fixture(hass: HomeAssistant) -> Future:
    """Create a future."""
    return hass.loop.create_future()
