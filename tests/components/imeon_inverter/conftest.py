"""Configuration for the Imeon Inverter integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.imeon_inverter.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_DEVICE_TYPE,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from tests.common import MockConfigEntry, load_json_object_fixture, patch

# Sample test data
TEST_USER_INPUT = {
    CONF_HOST: "192.168.200.1",
    CONF_USERNAME: "user@local",
    CONF_PASSWORD: "password",
}

TEST_SERIAL = "111111111111111"

TEST_DISCOVER = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=f"http://{TEST_USER_INPUT[CONF_HOST]}:8088/imeon.xml",
    upnp={
        ATTR_UPNP_MANUFACTURER: "IMEON",
        ATTR_UPNP_MODEL_NAME: "IMEON",
        ATTR_UPNP_FRIENDLY_NAME: f"IMEON-{TEST_SERIAL}",
        ATTR_UPNP_SERIAL: TEST_SERIAL,
        ATTR_UPNP_UDN: "uuid:01234567-89ab-cdef-0123-456789abcdef",
        ATTR_UPNP_DEVICE_TYPE: "urn:schemas-upnp-org:device:Basic:1",
    },
)


@pytest.fixture(autouse=True)
def mock_imeon_inverter() -> Generator[MagicMock]:
    """Mock data from the device."""
    with (
        patch(
            "homeassistant.components.imeon_inverter.coordinator.Inverter",
            autospec=True,
        ) as inverter_mock,
        patch(
            "homeassistant.components.imeon_inverter.config_flow.Inverter",
            new=inverter_mock,
        ),
    ):
        inverter = inverter_mock.return_value
        inverter.__aenter__.return_value = inverter
        inverter.login.return_value = True
        inverter.get_serial.return_value = TEST_SERIAL
        inverter.storage = load_json_object_fixture("sensor_data.json", DOMAIN)
        yield inverter


@pytest.fixture
def mock_async_setup_entry() -> Generator[AsyncMock]:
    """Fixture for mocking async_setup_entry."""
    with patch(
        "homeassistant.components.imeon_inverter.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        title="Imeon inverter",
        domain=DOMAIN,
        data=TEST_USER_INPUT,
        unique_id=TEST_SERIAL,
    )
