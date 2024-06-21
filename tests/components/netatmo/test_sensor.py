"""The tests for the Netatmo sensor platform."""

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.netatmo import sensor
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import selected_platforms, snapshot_platform_entities

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(
        hass,
        config_entry,
        Platform.SENSOR,
        entity_registry,
        snapshot,
    )


async def test_indoor_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test indoor sensor setup."""
    with selected_platforms([Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    prefix = "sensor.parents_bedroom_"

    assert hass.states.get(f"{prefix}temperature").state == "20.3"
    assert hass.states.get(f"{prefix}humidity").state == "63"
    assert hass.states.get(f"{prefix}carbon_dioxide").state == "494"
    assert hass.states.get(f"{prefix}atmospheric_pressure").state == "1014.5"


async def test_weather_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test weather sensor unreachable."""
    with selected_platforms([Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    prefix = "sensor.villa_outdoor_"

    assert hass.states.get(f"{prefix}temperature").state == "unavailable"


async def test_public_weather_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test public weather sensor setup."""
    with selected_platforms([Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    assert len(hass.states.async_all()) > 0

    prefix = "sensor.home_max_"

    assert hass.states.get(f"{prefix}temperature").state == "27.4"
    assert hass.states.get(f"{prefix}humidity").state == "76"
    assert hass.states.get(f"{prefix}atmospheric_pressure").state == "1014.4"

    prefix = "sensor.home_avg_"

    assert hass.states.get(f"{prefix}temperature").state == "22.7"
    assert hass.states.get(f"{prefix}humidity").state == "63.2"
    assert hass.states.get(f"{prefix}atmospheric_pressure").state == "1010.4"

    entities_before_change = len(hass.states.async_all())

    valid_option = {
        "lat_ne": 32.91336,
        "lon_ne": -117.187429,
        "lat_sw": 32.83336,
        "lon_sw": -117.26743,
        "show_on_map": True,
        "area_name": "Home avg",
        "mode": "max",
    }

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"new_area": "Home avg"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=valid_option
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == entities_before_change
    assert hass.states.get(f"{prefix}temperature").state == "27.4"


@pytest.mark.parametrize(
    ("strength", "expected"),
    [(50, "Full"), (60, "High"), (80, "Medium"), (90, "Low")],
)
async def test_process_wifi(strength: int, expected: str) -> None:
    """Test wifi strength translation."""
    assert sensor.process_wifi(strength) == expected


@pytest.mark.parametrize(
    ("strength", "expected"),
    [(50, "Full"), (70, "High"), (80, "Medium"), (90, "Low")],
)
async def test_process_rf(strength: int, expected: str) -> None:
    """Test radio strength translation."""
    assert sensor.process_rf(strength) == expected


@pytest.mark.parametrize(
    ("health", "expected"),
    [(4, "unhealthy"), (3, "poor"), (2, "fair"), (1, "fine"), (0, "healthy")],
)
async def test_process_health(health: int, expected: str) -> None:
    """Test health index translation."""
    assert sensor.process_health(health) == expected


@pytest.mark.parametrize(
    ("uid", "name", "expected"),
    [
        ("12:34:56:03:1b:e4-reachable", "villa_garden_reachable", "True"),
        ("12:34:56:03:1b:e4-rf_status", "villa_garden_radio", "Full"),
        (
            "12:34:56:80:bb:26-wifi_status",
            "villa_wifi_strength",
            "High",
        ),
        (
            "12:34:56:80:bb:26-temp_trend",
            "villa_temperature_trend",
            "stable",
        ),
        (
            "12:34:56:80:bb:26-pressure_trend",
            "villa_pressure_trend",
            "up",
        ),
        ("12:34:56:80:c1:ea-sum_rain_1", "villa_rain_rain_last_hour", "0"),
        ("12:34:56:80:c1:ea-sum_rain_24", "villa_rain_rain_today", "6.9"),
        ("12:34:56:03:1b:e4-windangle", "netatmoindoor_garden_direction", "sw"),
        (
            "12:34:56:03:1b:e4-windangle_value",
            "netatmoindoor_garden_angle",
            "217",
        ),
        ("12:34:56:03:1b:e4-gustangle", "mystation_garden_gust_direction", "s"),
        (
            "12:34:56:03:1b:e4-gustangle",
            "netatmoindoor_garden_gust_direction",
            "s",
        ),
        (
            "12:34:56:03:1b:e4-gustangle_value",
            "netatmoindoor_garden_gust_angle",
            "206",
        ),
        (
            "12:34:56:03:1b:e4-guststrength",
            "netatmoindoor_garden_gust_strength",
            "9",
        ),
        (
            "12:34:56:03:1b:e4-rf_status",
            "netatmoindoor_garden_rf_strength",
            "Full",
        ),
        (
            "12:34:56:26:68:92-health_idx",
            "baby_bedroom_health",
            "fine",
        ),
        (
            "12:34:56:26:68:92-wifi_status",
            "baby_bedroom_wifi",
            "High",
        ),
        ("Home-max-windangle_value", "home_max_wind_angle", "17"),
        ("Home-max-gustangle_value", "home_max_gust_angle", "217"),
        ("Home-max-guststrength", "home_max_gust_strength", "31"),
        ("Home-max-sum_rain_1", "home_max_sum_rain_1", "0.2"),
    ],
)
async def test_weather_sensor_enabling(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    uid: str,
    name: str,
    expected: str,
    netatmo_auth: AsyncMock,
) -> None:
    """Test enabling of by default disabled sensors."""
    with selected_platforms([Platform.SENSOR]):
        states_before = len(hass.states.async_all())
        assert hass.states.get(f"sensor.{name}") is None

        entity_registry.async_get_or_create(
            "sensor",
            "netatmo",
            uid,
            suggested_object_id=name,
            disabled_by=None,
        )
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        assert len(hass.states.async_all()) > states_before
        assert hass.states.get(f"sensor.{name}").state == expected


async def test_climate_battery_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test climate device battery sensor."""
    with selected_platforms([Platform.CLIMATE, Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    prefix = "sensor.livingroom_"

    assert hass.states.get(f"{prefix}battery").state == "75"
