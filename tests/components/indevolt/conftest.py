"""Setup the Indevolt test environment."""

from collections.abc import Generator
from typing import Any
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
TEST_PORT = 8080
TEST_DEVICE_SN_GEN1 = "BK1600-12345678"
TEST_DEVICE_SN_GEN2 = "SolidFlex2000-87654321"
TEST_FW_VERSION = "1.2.3"

# Map device fixture names to generation and fixture files
DEVICE_MAPPING = {
    1: {
        "device": "BK1600",
        "generation": 1,
        "sn": TEST_DEVICE_SN_GEN1,
    },
    2: {
        "device": "CMS-SF2000",
        "generation": 2,
        "sn": TEST_DEVICE_SN_GEN2,
    },
}


@pytest.fixture
def generation(request: pytest.FixtureRequest) -> int:
    """Return the device generation."""
    return getattr(request, "param", 2)


@pytest.fixture
def entry_data(generation: int) -> dict[str, Any]:
    """Return the config entry data based on generation."""
    device_info = DEVICE_MAPPING[generation]
    return {
        CONF_HOST: TEST_HOST,
        CONF_SERIAL_NUMBER: device_info["sn"],
        CONF_MODEL: device_info["device"],
        CONF_GENERATION: device_info["generation"],
    }


@pytest.fixture
def mock_config_entry(generation: int, entry_data: dict[str, Any]) -> MockConfigEntry:
    """Return the default mocked config entry."""
    device_info = DEVICE_MAPPING[generation]
    return MockConfigEntry(
        domain=DOMAIN,
        title=device_info["device"],
        version=1,
        data=entry_data,
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
        client = mock_client.return_value
        client.fetch_data.return_value = fixture_data
        client.set_data.return_value = True
        client.get_config.return_value = {
            "device": {
                "sn": device_info["sn"],
                "type": device_info["device"],
                "generation": device_info["generation"],
                "fw": TEST_FW_VERSION,
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
