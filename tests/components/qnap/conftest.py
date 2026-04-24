"""Setup the QNAP tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.qnap.const import (
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry, load_fixture

TEST_HOST = "1.2.3.4"
TEST_USERNAME = "admin"
TEST_PASSWORD = "password"
TEST_NAS_NAME = "Test NAS"
TEST_SERIAL = "QX1234567"
INSTALLED_VERSION = "5.1.0.2548"


def _get_fixture_data() -> dict[str, Any]:
    """Load the canonical QNAP coordinator fixture data."""
    import json

    return json.loads(load_fixture("qnap_data.json", DOMAIN))


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock QNAP config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SERIAL,
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: DEFAULT_SSL,
            CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
            CONF_PORT: DEFAULT_PORT,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
    )


@pytest.fixture
def mock_qnap_client() -> Generator[MagicMock]:
    """Mock a QNAP QNAPStats client.

    Patches QNAPStats in the coordinator module and pre-loads all API
    methods with data from the canonical JSON fixture file.
    """
    fixture = _get_fixture_data()
    with patch(
        "homeassistant.components.qnap.coordinator.QNAPStats",
        autospec=True,
    ) as mock_class:
        client = mock_class.return_value
        client.get_system_stats.return_value = fixture["system_stats"]
        client.get_system_health.return_value = fixture["system_health"]
        client.get_smart_disk_health.return_value = fixture["smart_drive_health"]
        client.get_volumes.return_value = fixture["volumes"]
        client.get_bandwidth.return_value = fixture["bandwidth"]
        client.get_firmware_update.return_value = fixture["firmware_update"]
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.qnap.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def qnap_connect() -> Generator[MagicMock]:
    """Mock qnap connection (config flow only)."""
    with patch(
        "homeassistant.components.qnap.config_flow.QNAPStats", autospec=True
    ) as host_mock_class:
        host_mock = host_mock_class.return_value
        host_mock.get_system_stats.return_value = {
            "system": {"serial_number": TEST_SERIAL, "name": TEST_NAS_NAME}
        }
        yield host_mock
