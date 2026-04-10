"""Tests for the Forecast.Solar integration."""

from unittest.mock import MagicMock, patch

from forecast_solar import ForecastSolarConnectionError, Plane

from homeassistant.components.forecast_solar.const import (
    CONF_AZIMUTH,
    CONF_DAMPING,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    DOMAIN,
    SUBENTRY_TYPE_PLANE,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test the Forecast.Solar configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await async_setup_component(hass, "forecast_solar", {})

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)


@patch(
    "homeassistant.components.forecast_solar.coordinator.ForecastSolar.estimate",
    side_effect=ForecastSolarConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Forecast.Solar configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_migration_from_v1(
    hass: HomeAssistant,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test config entry migration from version 1."""
    mock_config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique",
        domain=DOMAIN,
        version=1,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options={
            CONF_API_KEY: "abcdef12345",
            CONF_DECLINATION: 30,
            CONF_AZIMUTH: 190,
            "modules power": 5100,
            CONF_DAMPING: 0.5,
            CONF_INVERTER_SIZE: 2000,
        },
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry.version == 3
    assert entry.options == {
        CONF_API_KEY: "abcdef12345",
        "damping_morning": 0.5,
        "damping_evening": 0.5,
        CONF_INVERTER_SIZE: 2000,
    }
    plane_subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)
    assert len(plane_subentries) == 1
    subentry = plane_subentries[0]
    assert subentry.subentry_type == SUBENTRY_TYPE_PLANE
    assert subentry.data == {
        CONF_DECLINATION: 30,
        CONF_AZIMUTH: 190,
        CONF_MODULES_POWER: 5100,
    }
    assert subentry.title == "30° / 190° / 5100W"


async def test_migration_from_v2(
    hass: HomeAssistant,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test config entry migration from version 2."""
    mock_config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique",
        domain=DOMAIN,
        version=2,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options={
            CONF_API_KEY: "abcdef12345",
            CONF_DECLINATION: 30,
            CONF_AZIMUTH: 190,
            CONF_MODULES_POWER: 5100,
            CONF_INVERTER_SIZE: 2000,
        },
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry.version == 3
    assert entry.options == {
        CONF_API_KEY: "abcdef12345",
        CONF_INVERTER_SIZE: 2000,
    }
    plane_subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)
    assert len(plane_subentries) == 1
    subentry = plane_subentries[0]
    assert subentry.subentry_type == SUBENTRY_TYPE_PLANE
    assert subentry.data == {
        CONF_DECLINATION: 30,
        CONF_AZIMUTH: 190,
        CONF_MODULES_POWER: 5100,
    }
    assert subentry.title == "30° / 190° / 5100W"


async def test_setup_entry_no_planes(
    hass: HomeAssistant,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test setup fails when all plane subentries have been removed."""
    mock_config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique",
        version=3,
        domain=DOMAIN,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options={
            CONF_API_KEY: "abcdef1234567890",
        },
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_multiple_planes_no_api_key(
    hass: HomeAssistant,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test setup fails when multiple planes are configured without an API key."""
    mock_config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique",
        version=3,
        domain=DOMAIN,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options={},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 30,
                    CONF_AZIMUTH: 190,
                    CONF_MODULES_POWER: 5100,
                },
                subentry_id="plane_1",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="30° / 190° / 5100W",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 45,
                    CONF_AZIMUTH: 90,
                    CONF_MODULES_POWER: 3000,
                },
                subentry_id="plane_2",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="45° / 90° / 3000W",
                unique_id=None,
            ),
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_multi_plane_initialization(
    hass: HomeAssistant,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test the Forecast.Solar coordinator multi-plane initialization."""
    options = {
        CONF_API_KEY: "abcdef1234567890",
        CONF_DAMPING_MORNING: 0.5,
        CONF_DAMPING_EVENING: 0.5,
        CONF_INVERTER_SIZE: 2000,
    }

    mock_config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique",
        version=3,
        domain=DOMAIN,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options=options,
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 30,
                    CONF_AZIMUTH: 190,
                    CONF_MODULES_POWER: 5100,
                },
                subentry_id="plane_1",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="30° / 190° / 5100W",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 45,
                    CONF_AZIMUTH: 270,
                    CONF_MODULES_POWER: 3000,
                },
                subentry_id="plane_2",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="45° / 270° / 3000W",
                unique_id=None,
            ),
        ],
    )

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.forecast_solar.coordinator.ForecastSolar",
        return_value=mock_forecast_solar,
    ) as forecast_solar_mock:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    forecast_solar_mock.assert_called_once()
    _, kwargs = forecast_solar_mock.call_args

    assert kwargs["latitude"] == 52.42
    assert kwargs["longitude"] == 4.42
    assert kwargs["api_key"] == "abcdef1234567890"

    # Main plane (plane_1)
    assert kwargs["declination"] == 30
    assert kwargs["azimuth"] == 10  # 190 - 180
    assert kwargs["kwp"] == 5.1  # 5100 / 1000

    # Additional planes (plane_2)
    planes = kwargs["planes"]
    assert len(planes) == 1
    assert isinstance(planes[0], Plane)
    assert planes[0].declination == 45
    assert planes[0].azimuth == 90  # 270 - 180
    assert planes[0].kwp == 3.0  # 3000 / 1000
