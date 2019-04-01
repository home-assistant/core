"""Configuration for Rainmachine tests."""
import pytest

from homeassistant.components.rainmachine.const import DOMAIN
from homeassistant.const import (
    CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL, CONF_SSL)

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock RainMachine config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title='192.168.1.101',
        data={
            CONF_IP_ADDRESS: '192.168.1.101',
            CONF_PASSWORD: '12345',
            CONF_PORT: 8080,
            CONF_SSL: True,
            CONF_SCAN_INTERVAL: 60,
        })
