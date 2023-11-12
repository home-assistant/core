"""Test Kostal Plenticore helper."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pykoplenti import ApiClient, SettingsData
import pytest

from homeassistant.components.kostal_plenticore.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from tests.common import MockConfigEntry


@pytest.fixture
def mock_apiclient() -> Generator[ApiClient, None, None]:
    """Return a mocked ApiClient class."""
    with patch(
        "homeassistant.components.kostal_plenticore.helper.ApiClient",
        autospec=True,
    ) as mock_api_class:
        apiclient = MagicMock(spec=ApiClient)
        apiclient.__aenter__.return_value = apiclient
        apiclient.__aexit__ = AsyncMock()
        mock_api_class.return_value = apiclient
        yield apiclient


async def test_plenticore_async_setup_g1(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_apiclient: ApiClient,
) -> None:
    """Tests the async_setup() method of the Plenticore class for G1 models."""
    mock_apiclient.get_settings = AsyncMock(
        return_value={"scb:network": [SettingsData({"id": "Hostname"})]}
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
            },
            "scb:network": {"Hostname": "scb"},
        }
    )

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    plenticore = hass.data[DOMAIN][mock_config_entry.entry_id]

    assert plenticore.device_info == DeviceInfo(
        configuration_url="http://192.168.1.2",
        identifiers={(DOMAIN, "12345")},
        manufacturer="Kostal",
        model="PLENTICORE plus 10",
        name="scb",
        sw_version="IOC: 01.45 MC: 01.46",
    )


async def test_plenticore_async_setup_g2(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_apiclient: ApiClient,
) -> None:
    """Tests the async_setup() method of the Plenticore class for G2 models."""
    mock_apiclient.get_settings = AsyncMock(
        return_value={"scb:network": [SettingsData({"id": "Network:Hostname"})]}
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
            },
            "scb:network": {"Network:Hostname": "scb"},
        }
    )

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    plenticore = hass.data[DOMAIN][mock_config_entry.entry_id]

    assert plenticore.device_info == DeviceInfo(
        configuration_url="http://192.168.1.2",
        identifiers={(DOMAIN, "12345")},
        manufacturer="Kostal",
        model="PLENTICORE plus 10",
        name="scb",
        sw_version="IOC: 01.45 MC: 01.46",
    )
