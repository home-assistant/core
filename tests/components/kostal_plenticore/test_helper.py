"""Test Kostal Plenticore helper."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pykoplenti import ApiClient, ExtendedApiClient, VersionData
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.kostal_plenticore.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo


@pytest.fixture
def mock_apiclient() -> Generator[ApiClient]:
    """Return a mocked ApiClient class."""
    with patch(
        "homeassistant.components.kostal_plenticore.coordinator.ExtendedApiClient",
        autospec=True,
    ) as mock_api_class:
        apiclient = MagicMock(spec=ExtendedApiClient)
        apiclient.__aenter__.return_value = apiclient
        apiclient.__aexit__ = AsyncMock()
        mock_api_class.return_value = apiclient
        yield apiclient


async def test_plenticore_async_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_apiclient: ApiClient,
) -> None:
    """Tests the async_setup() method of the Plenticore."""
    mock_apiclient.get_version = AsyncMock(
        return_value=VersionData(hostname="scb", api_version="", name="", sw_version="")
    )
    mock_apiclient.get_setting_values = AsyncMock(
        # G1 model has the entry id "Hostname"
        return_value={
            "devices:local": {
                "Properties:SerialNo": "12345",
                "Branding:ProductName1": "PLENTICORE",
                "Branding:ProductName2": "plus 10",
                "Properties:VersionIOC": "01.45",
                "Properties:VersionMC": "01.46",
            }
        }
    )

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    plenticore = mock_config_entry.runtime_data

    assert plenticore.device_info == DeviceInfo(
        configuration_url="http://192.168.1.2",
        identifiers={(DOMAIN, "12345")},
        manufacturer="Kostal",
        model="PLENTICORE plus 10",
        name="scb",
        sw_version="IOC: 01.45 MC: 01.46",
    )
