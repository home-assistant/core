"""Test the RKI Covide numbers integration sensor."""
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp.client_exceptions import ClientError

from homeassistant.components.rki_covid.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_registry


async def test_sensor_without_data_coordinator(hass: HomeAssistant) -> None:
    """Test sensor when data coordinator could not be initialized."""
    async_mock = AsyncMock(return_value=None)
    with patch("custom_components.rki_covid.get_coordinator", side_effect=async_mock):
        entry = MockConfigEntry(domain=DOMAIN, data={"county": "SK Amberg"})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_sensor_with_mock_data(hass: HomeAssistant, aioclient_mock) -> None:
    """Test sensor setup with mock data."""
    entry = MockConfigEntry(domain=DOMAIN, data={"county": "SK Amberg"})
    entry.add_to_hass(hass)

    mock_registry(
        hass,
        {
            "sensor.sk_amberg": entity_registry.RegistryEntry(
                entity_id="sk_amberg_casesper100k",
                unique_id="34-confirmed",
                platform="rki_covid",
                config_entry_id=entry.entry_id,
            )
        },
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.sk_amberg_count").state == "1337"
    assert entry.unique_id == "SK Amberg"


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


@patch(
    "rki_covid_parser.districts",
    side_effect=ClientError,
)
async def test_sensor_with_invalid_config_entry(
    hass: HomeAssistant, mock_parser: MagicMock
) -> None:
    """Test sensor with an invalid config entry should fail with exception."""
    entry = MockConfigEntry(domain=DOMAIN, data={"county": "SK Invalid"})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
