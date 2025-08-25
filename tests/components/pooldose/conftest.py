"""Test fixtures for the Seko PoolDose integration."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

from pooldose.request_status import RequestStatus
import pytest

from homeassistant.components.pooldose.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


def _get_serial_number() -> str:
    """Get serial number from deviceinfo.json fixture."""
    device_info_raw = load_fixture("deviceinfo.json", DOMAIN)
    device_info = json.loads(device_info_raw)
    return device_info["SERIAL_NUMBER"]


@pytest.fixture(autouse=True)
def mock_pooldose_client() -> Generator[MagicMock]:
    """Mock a PooldoseClient for end-to-end testing."""
    with (
        patch("pooldose.client.PooldoseClient", autospec=True) as mock_client_class,
        patch(
            "homeassistant.components.pooldose.PooldoseClient", new=mock_client_class
        ),
    ):
        client = mock_client_class.return_value

        # Load device info from fixture
        device_info_raw = load_fixture("deviceinfo.json", DOMAIN)
        device_info = json.loads(device_info_raw)
        client.device_info = device_info

        # Setup client methods with realistic responses
        client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
        client.check_apiversion_supported = MagicMock(
            return_value=(RequestStatus.SUCCESS, {})
        )

        # Load instant values from fixture
        instant_values_raw = load_fixture("instantvalues.json", DOMAIN)
        instant_values_data = json.loads(instant_values_raw)
        client.instant_values_structured = AsyncMock(
            return_value=(RequestStatus.SUCCESS, instant_values_data)
        )

        client.is_connected = True
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Pool Device",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id=_get_serial_number(),
        entry_id="01JG00V55WEVTJ0CJHM0GAD7PC",
    )


async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
