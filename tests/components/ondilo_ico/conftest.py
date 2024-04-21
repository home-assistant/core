"""Provide basic Ondilo fixture."""

import pytest

from homeassistant.components.ondilo_ico.api import OndiloClient
from homeassistant.components.ondilo_ico.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="ondilo_client")
def ondilo_client(hass: HomeAssistant) -> OndiloClient:
    """Define Mock Ondilo client."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={"token": "mocktoken"})
    config_entry.add_to_hass(hass)

    return OndiloClient(hass, config_entry, None)
