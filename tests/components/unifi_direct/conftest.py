"""Fixtures for UniFi AP Direct integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.unifi_direct.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.2"
MOCK_SECOND_HOST = "192.168.1.3"
MOCK_USERNAME = "admin"
MOCK_PASSWORD = "password"
MOCK_PORT = 22

MOCK_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_PORT: MOCK_PORT,
}

MOCK_SECOND_CONFIG = {
    CONF_HOST: MOCK_SECOND_HOST,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_PORT: MOCK_PORT,
}

MOCK_DEVICE_DATA = {
    "AA:BB:CC:DD:EE:FF": {"ip": "192.168.1.100", "hostname": "my-phone"},
    "11:22:33:44:55:66": {"ip": "192.168.1.101", "hostname": "my-laptop"},
}

MOCK_SECOND_DEVICE_DATA = {
    "AA:BB:CC:DD:EE:FF": {"ip": "192.168.1.100", "hostname": "my-phone"},
    "66:77:88:99:AA:BB": {"ip": "192.168.1.102", "hostname": "my-desktop"},
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.unifi_direct.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, title=f"UniFi AP ({MOCK_HOST})"
    )


@pytest.fixture
def mock_second_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_SECOND_CONFIG, title=f"UniFi AP ({MOCK_SECOND_HOST})"
    )


@pytest.fixture
def mock_unifiap() -> Generator[MagicMock]:
    """Mock UniFiAP to return known clients."""
    with (
        patch("homeassistant.components.unifi_direct.coordinator.UniFiAP") as mock,
        patch("homeassistant.components.unifi_direct.config_flow.UniFiAP", new=mock),
    ):

        def _build_ap_instance(target: str | None) -> MagicMock:
            ap_instance = MagicMock()
            if target == MOCK_SECOND_HOST:
                ap_instance.get_clients.return_value = MOCK_SECOND_DEVICE_DATA
            else:
                ap_instance.get_clients.return_value = MOCK_DEVICE_DATA
            return ap_instance

        default_ap_instance = _build_ap_instance(MOCK_HOST)
        mock.return_value = default_ap_instance

        def _mock_unifiap(*args: object, **kwargs: object) -> MagicMock:
            target = kwargs.get("target")
            if target is None and args:
                target = args[0]
            return _build_ap_instance(target if isinstance(target, str) else None)

        mock.side_effect = _mock_unifiap
        yield mock
