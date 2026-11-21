"""Fixtures for Synology SRM."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.synology_srm.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

CONFIG = {
    CONF_HOST: "192.168.1.1",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "password",
    CONF_PORT: 8001,
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
}
MAC = "aa:bb:cc:dd:ee:ff"
CLIENT = {
    "mac": MAC,
    "hostname": "Phone",
    "ip_addr": "192.168.1.2",
    "is_online": True,
    "is_wireless": True,
    "signalstrength": -50,
}


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the router API."""
    with patch(
        "homeassistant.components.synology_srm.coordinator.Client", autospec=True
    ) as mock:
        mock.return_value.core = MagicMock()
        mock.return_value.http = MagicMock()
        mock.return_value.core.get_network_nsm_device.return_value = [CLIENT.copy()]
        yield mock.return_value


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry."""
    return MockConfigEntry(domain=DOMAIN, title=CONFIG[CONF_HOST], data=CONFIG)
