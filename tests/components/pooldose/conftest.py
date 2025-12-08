"""Test fixtures for the Seko PoolDose integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pooldose.request_status import RequestStatus
import pytest

from homeassistant.components.pooldose.const import DOMAIN
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    load_json_object_fixture,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pooldose.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def device_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return the device info from the fixture."""
    return await async_load_json_object_fixture(hass, "deviceinfo.json", DOMAIN)


@pytest.fixture(autouse=True)
def mock_pooldose_client(device_info: dict[str, Any]) -> Generator[MagicMock]:
    """Mock a PooldoseClient for end-to-end testing."""
    with (
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.pooldose.PooldoseClient", new=mock_client_class
        ),
    ):
        client = mock_client_class.return_value
        client.device_info = device_info

        # Setup client methods with realistic responses
        client.connect.return_value = RequestStatus.SUCCESS
        client.check_apiversion_supported.return_value = (RequestStatus.SUCCESS, {})

        # Load instant values from fixture
        instant_values_data = load_json_object_fixture("instantvalues.json", DOMAIN)
        client.instant_values_structured.return_value = (
            RequestStatus.SUCCESS,
            instant_values_data,
        )

        client.set_switch = AsyncMock(return_value=RequestStatus.SUCCESS)
        client.is_connected = True
        yield client


@pytest.fixture
def mock_config_entry(device_info: dict[str, Any]) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Pool Device",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id=device_info["SERIAL_NUMBER"],
        entry_id="01JG00V55WEVTJ0CJHM0GAD7PC",
    )


@pytest.fixture
def mock_config_entry_v1_1(device_info: dict[str, Any]) -> MockConfigEntry:
    """Return a mocked config entry for migration testing with version 1.1."""
    return MockConfigEntry(
        title="Pool Device",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id=device_info["SERIAL_NUMBER"],
        version=1,
        minor_version=1,
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
