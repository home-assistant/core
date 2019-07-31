"""Configuration for HEOS tests."""
from typing import Dict, Sequence

from asynctest.mock import Mock, patch as patch
import pytest

from homeassistant.components.ring import (DOMAIN)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, \
    CONF_SCAN_INTERVAL

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock ring config entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_USERNAME: 'foo',
    CONF_PASSWORD: 'bar', CONF_SCAN_INTERVAL: 1000}, title='Ring')

@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {
        DOMAIN: {}
    }