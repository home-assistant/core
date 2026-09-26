"""Tests for the Forecast.Solar integration."""

import asyncio
from unittest.mock import MagicMock, patch

from forecast_solar import ForecastSolarConnectionError, Plane
import pytest

from homeassistant.components.forecast_solar.const import (
    CONF_AZIMUTH,
    CONF_AZIMUTH_SENSOR,
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
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test the Forecast.Solar configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {})

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
    mock_forecast_solar_class: MagicMock,
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
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_forecast_solar_class.assert_called_once()
    _, kwargs = mock_forecast_solar_class.call_args

    assert kwargs["latitude"] == 52.42
    assert kwargs["longitude"] == 4.42
    assert kwargs["api_key"] == "abcdef1234567890"

    # Main plane (plane_1), azimuth converted from 0-360 (0=North) to -180..180.
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


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_forecast_changes_reload_once_title_changes_do_not(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a title-only update doesn't reload, and one rename reloads once."""
    entity_registry.async_get_or_create(
        "sensor", "test", "azimuth", suggested_object_id="roof_azimuth"
    )
    hass.states.async_set(
        "sensor.roof_azimuth",
        "100",
        {"unit_of_measurement": "°", "friendly_name": "Roof angle"},
    )
    plane_data = {
        CONF_DECLINATION: 30,
        CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
        CONF_MODULES_POWER: 5100,
    }
    mock_config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique",
        version=3,
        domain=DOMAIN,
        data={CONF_LATITUDE: 52.42, CONF_LONGITUDE: 4.42},
        options={CONF_API_KEY: "abcdef1234567890"},
        subentries_data=[
            ConfigSubentryData(
                data=dict(plane_data),
                subentry_id=f"plane_{index}",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="30° / Roof angle (sensor) / 5100W",
                unique_id=None,
            )
            for index in range(2)
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async def _reload(entry_id: str) -> bool:
        # Suspends like a real reload, which unloads platforms before setting up again.
        await asyncio.sleep(0)
        return True

    # Patched so the listener stays registered, as it is until a reload unloads it.
    with patch.object(
        hass.config_entries, "async_reload", side_effect=_reload
    ) as mock_reload:
        # A friendly name is only a label; the forecast inputs are unchanged.
        hass.states.async_set(
            "sensor.roof_azimuth",
            "100",
            {"unit_of_measurement": "°", "friendly_name": "Camper angle"},
        )
        await hass.async_block_till_done()

        mock_reload.assert_not_called()

        # Both planes read the renamed sensor, but a single reload covers them.
        entity_registry.async_update_entity(
            "sensor.roof_azimuth", new_entity_id="sensor.camper_azimuth"
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_plane_follows_sensor_friendly_name(
    hass: HomeAssistant,
) -> None:
    """Test a plane's title follows the friendly name of the sensor it reads."""
    hass.states.async_set(
        "sensor.roof_azimuth",
        "100",
        {"unit_of_measurement": "°", "friendly_name": "Roof angle"},
    )
    mock_config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique",
        version=3,
        domain=DOMAIN,
        data={CONF_LATITUDE: 52.42, CONF_LONGITUDE: 4.42},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 30,
                    CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
                    CONF_MODULES_POWER: 5100,
                },
                subentry_id="plane_1",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="30° / Roof angle (sensor) / 5100W",
                unique_id=None,
            ),
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "sensor.roof_azimuth",
        "100",
        {"unit_of_measurement": "°", "friendly_name": "Camper angle"},
    )
    await hass.async_block_till_done()

    subentry = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)[0]
    assert subentry.title == "30° / Camper angle (sensor) / 5100W"


@pytest.mark.parametrize(
    "title",
    [
        pytest.param("30° / sensor.roof_azimuth (sensor) / 5100W", id="entity_id"),
        pytest.param("30° / roof azimuth (sensor) / 5100W", id="sensor_name"),
    ],
)
@pytest.mark.usefixtures("mock_forecast_solar")
async def test_plane_follows_renamed_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    title: str,
) -> None:
    """Test a plane's sensor reference follows the sensor when it is renamed."""
    entity_registry.async_get_or_create(
        "sensor", "test", "azimuth", suggested_object_id="roof_azimuth"
    )
    hass.states.async_set("sensor.roof_azimuth", "100", {"unit_of_measurement": "°"})

    mock_config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique",
        version=3,
        domain=DOMAIN,
        data={CONF_LATITUDE: 52.42, CONF_LONGITUDE: 4.42},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 30,
                    CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
                    CONF_MODULES_POWER: 5100,
                },
                subentry_id="plane_1",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title=title,
                unique_id=None,
            ),
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Changes that are not a rename leave the reference alone.
    entity_registry.async_update_entity("sensor.roof_azimuth", name="Roof angle")
    entity_registry.async_remove("sensor.roof_azimuth")
    hass.states.async_remove("sensor.roof_azimuth")
    await hass.async_block_till_done()

    subentry = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)[0]
    assert subentry.data[CONF_AZIMUTH_SENSOR] == "sensor.roof_azimuth"

    entity_registry.async_get_or_create(
        "sensor", "test", "azimuth", suggested_object_id="roof_azimuth"
    )
    entity_registry.async_update_entity(
        "sensor.roof_azimuth", new_entity_id="sensor.camper_azimuth"
    )
    await hass.async_block_till_done()

    subentry = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)[0]
    assert subentry.data[CONF_AZIMUTH_SENSOR] == "sensor.camper_azimuth"
    # A rename leaves no state behind, so the title falls back to the new entity ID.
    assert subentry.title == "30° / sensor.camper_azimuth (sensor) / 5100W"

    hass.states.async_set(
        "sensor.camper_azimuth",
        "100",
        {"unit_of_measurement": "°", "friendly_name": "Camper angle"},
    )
    # The reload the rename triggered failed while the new ID had no state; in
    # production the entry's setup retry runs this once the sensor is readable.
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    subentry = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)[0]
    assert subentry.title == "30° / Camper angle (sensor) / 5100W"


@pytest.mark.usefixtures("mock_forecast_solar")
async def test_plane_follows_renamed_sensor_during_setup_retry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a rename is followed while the entry is retrying on an unreadable sensor."""
    entity_registry.async_get_or_create(
        "sensor", "test", "azimuth", suggested_object_id="roof_azimuth"
    )

    mock_config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique",
        version=3,
        domain=DOMAIN,
        data={CONF_LATITUDE: 52.42, CONF_LONGITUDE: 4.42},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DECLINATION: 30,
                    CONF_AZIMUTH_SENSOR: "sensor.roof_azimuth",
                    CONF_MODULES_POWER: 5100,
                },
                subentry_id="plane_1",
                subentry_type=SUBENTRY_TYPE_PLANE,
                title="30° / sensor.roof_azimuth (sensor) / 5100W",
                unique_id=None,
            ),
        ],
    )
    mock_config_entry.add_to_hass(hass)
    # The sensor has no state, so the first refresh fails and the entry retries.
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    entity_registry.async_update_entity(
        "sensor.roof_azimuth", new_entity_id="sensor.camper_azimuth"
    )
    await hass.async_block_till_done()

    subentry = mock_config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)[0]
    assert subentry.data[CONF_AZIMUTH_SENSOR] == "sensor.camper_azimuth"
