"""Setup the Indevolt test environment."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.indevolt.const import (
    CONF_GENERATION,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_MODEL

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_HOST = "192.168.1.100"
TEST_HOST_ALT = "192.168.1.101"
TEST_PORT = 8080

TEST_DEVICE_SN_GEN1 = "BK1600-12345678"
TEST_DEVICE_SN_GEN2 = "SolidFlex2000-87654321"
TEST_MODEL_GEN1 = "BK1600"
TEST_MODEL_GEN2 = "CMS-SF2000"

# Create DeviceInfo per generation
DEVICE_MAPPING = {
    1: {
        "device": TEST_MODEL_GEN1,
        "generation": 1,
        "sn": TEST_DEVICE_SN_GEN1,
        "host": TEST_HOST_ALT,
        "mac": "aa:bb:cc:11:22:33",
        "fw": "1.2.3",
    },
    2: {
        "device": TEST_MODEL_GEN2,
        "generation": 2,
        "sn": TEST_DEVICE_SN_GEN2,
        "host": TEST_HOST,
        "mac": "aa:bb:cc:44:55:66",
        "fw": "1.2.3",
    },
}


@pytest.fixture
def generation(request: pytest.FixtureRequest) -> int:
    """Return the device generation."""
    return getattr(request, "param", 2)


@pytest.fixture
def alt_generation(request: pytest.FixtureRequest) -> int:
    """Return the alternative device generation."""
    return getattr(request, "param", 1)


@pytest.fixture
def mock_config_entry(generation: int) -> MockConfigEntry:
    """Return the default mocked config entry."""
    device_info = DEVICE_MAPPING[generation]
    return MockConfigEntry(
        domain=DOMAIN,
        title=device_info["device"],
        version=1,
        minor_version=2,
        data={
            CONF_HOST: device_info["host"],
            CONF_SERIAL_NUMBER: device_info["sn"],
            CONF_MODEL: device_info["device"],
            CONF_GENERATION: device_info["generation"],
        },
        unique_id=device_info["sn"],
    )


@pytest.fixture
def mock_config_entry_v1_1(generation: int) -> MockConfigEntry:
    """Return a mocked config entry with version 1.1 for migration testing."""
    device_info = DEVICE_MAPPING[generation]
    return MockConfigEntry(
        domain=DOMAIN,
        title=device_info["device"],
        version=1,
        minor_version=1,
        data={
            CONF_HOST: device_info["host"],
            CONF_SERIAL_NUMBER: device_info["sn"],
            CONF_MODEL: device_info["device"],
            CONF_GENERATION: device_info["generation"],
        },
        unique_id=device_info["sn"],
    )


@pytest.fixture
def alt_mock_config_entry(alt_generation: int) -> MockConfigEntry:
    """Return a second mocked config entry for multi-device tests."""
    device_info = DEVICE_MAPPING[alt_generation]
    return MockConfigEntry(
        domain=DOMAIN,
        title=device_info["device"],
        version=1,
        minor_version=2,
        data={
            CONF_HOST: device_info["host"],
            CONF_SERIAL_NUMBER: device_info["sn"],
            CONF_MODEL: device_info["device"],
            CONF_GENERATION: device_info["generation"],
        },
        unique_id=device_info["sn"],
    )


@pytest.fixture
def mock_indevolt(generation: int) -> Generator[AsyncMock]:
    """Mock an IndevoltAPI client."""
    device_info = DEVICE_MAPPING[generation]
    fixture_data = load_json_object_fixture(f"gen_{generation}.json", DOMAIN)

    with (
        patch(
            "homeassistant.components.indevolt.coordinator.IndevoltAPI",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.indevolt.config_flow.IndevoltAPI",
            new=mock_client,
        ),
    ):
        # Mock coordinator API (get_data)
        # fetch_data filters by requested keys so that SENSOR_KEYS omissions
        # cause test failures instead of silently returning extra fixture data.
        # Tests that mutate fetch_data.return_value[key] to simulate state
        # changes will still work because side_effect reads from return_value.
        client = mock_client.return_value
        client.fetch_data.return_value = dict(fixture_data)
        client.fetch_data.side_effect = lambda keys: {
            k: v for k, v in client.fetch_data.return_value.items() if k in keys
        }
        client.set_data.return_value = True
        client.stop.return_value = True
        client.charge.return_value = True
        client.discharge.return_value = True
        client.get_config.return_value = {
            "device": {
                "sn": device_info["sn"],
                "type": device_info["device"],
                "generation": device_info["generation"],
                "fw": device_info["fw"],
                "mac": device_info["mac"],
            }
        }

        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock the async_setup_entry function."""
    with patch(
        "homeassistant.components.indevolt.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
