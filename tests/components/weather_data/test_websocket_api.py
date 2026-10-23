"""Test the Weather data websocket API."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockModule, MockUser, mock_integration
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.weather_data.const import DOMAIN
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

AIR_QUALITY_CATEGORY = "weather_alerts.air_quality_pollen"


@pytest.fixture(autouse=True)
async def setup_integration(hass: HomeAssistant) -> None:
    """Set up the integration."""
    assert await async_setup_component(hass, DOMAIN, {})


async def _send(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, msg: dict[str, Any]
) -> dict[str, Any]:
    """Send a websocket command and return the response."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(msg)
    return await client.receive_json()


def _add_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform: str,
    unique_id: str,
    attributes: dict[str, Any] | None = None,
    translation_key: str | None = None,
) -> str:
    """Register a sensor and set its state."""
    entry = entity_registry.async_get_or_create(
        "sensor",
        platform,
        unique_id,
        suggested_object_id=unique_id,
        translation_key=translation_key,
    )
    hass.states.async_set(entry.entity_id, "1", attributes or {})
    return entry.entity_id


async def test_get_default_prefs(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the preferences before anything is saved."""
    msg = await _send(hass, hass_ws_client, {"type": "weather_data/get_prefs"})

    assert msg["success"]
    assert msg["result"] == {"weather_entities": [], "excluded_weather_entities": []}


async def test_save_prefs(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test saving preferences keeps the keys that are not sent."""
    await _send(
        hass,
        hass_ws_client,
        {
            "type": "weather_data/save_prefs",
            "weather_entities": ["weather.met"],
            "rain_gauge_entity": None,
        },
    )
    msg = await _send(
        hass,
        hass_ws_client,
        {"type": "weather_data/save_prefs", "pollen_entities": ["sensor.pollen"]},
    )

    assert msg["success"]
    assert msg["result"] == {
        "weather_entities": ["weather.met"],
        "excluded_weather_entities": [],
        "rain_gauge_entity": None,
        "pollen_entities": ["sensor.pollen"],
    }


async def test_save_prefs_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test only admins can save preferences."""
    hass_admin_user.groups = []

    msg = await _send(
        hass,
        hass_ws_client,
        {"type": "weather_data/save_prefs", "weather_entities": ["weather.met"]},
    )

    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


async def test_load_stored_prefs(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test stored preferences are loaded."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "data": {
            "weather_entities": ["weather.met"],
            "excluded_weather_entities": ["weather.thermostat"],
        },
    }

    msg = await _send(hass, hass_ws_client, {"type": "weather_data/get_prefs"})

    assert msg["result"]["excluded_weather_entities"] == ["weather.thermostat"]


async def test_source_order(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the ordered sources come first, then new ones, without excluded."""
    for entity_id in (
        "weather.met",
        "weather.buienradar",
        "weather.openweathermap",
        "weather.thermostat",
    ):
        hass.states.async_set(entity_id, "sunny")
    hidden = entity_registry.async_get_or_create(
        "weather", "demo", "hidden", hidden_by=er.RegistryEntryHider.USER
    )
    hass.states.async_set(hidden.entity_id, "sunny")
    diagnostic = entity_registry.async_get_or_create(
        "weather", "demo", "diagnostic", entity_category=EntityCategory.DIAGNOSTIC
    )
    hass.states.async_set(diagnostic.entity_id, "sunny")

    await _send(
        hass,
        hass_ws_client,
        {
            "type": "weather_data/save_prefs",
            "weather_entities": ["weather.met", "weather.removed"],
            "excluded_weather_entities": ["weather.thermostat"],
        },
    )
    msg = await _send(hass, hass_ws_client, {"type": "weather_data/get_info"})

    assert msg["result"]["sources"] == [
        "weather.met",
        "weather.buienradar",
        "weather.openweathermap",
    ]


@pytest.mark.parametrize(
    ("prefs", "expected"),
    [
        pytest.param({}, "sensor.rain_total", id="detected"),
        pytest.param({"rain_gauge_entity": None}, None, id="turned_off"),
        pytest.param(
            {"rain_gauge_entity": "sensor.rain_rate"}, "sensor.rain_rate", id="selected"
        ),
        pytest.param(
            {"rain_gauge_entity": "sensor.removed"}, None, id="selected_missing"
        ),
    ],
)
async def test_rain_gauge(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    prefs: dict[str, Any],
    expected: str | None,
) -> None:
    """Test only a precipitation sensor that adds up rain is detected."""
    hass.states.async_set(
        "sensor.rain_rate",
        "0.4",
        {"device_class": "precipitation", "state_class": "measurement"},
    )
    hass.states.async_set(
        "sensor.rain_total",
        "12.4",
        {"device_class": "precipitation", "state_class": "total_increasing"},
    )

    await _send(hass, hass_ws_client, {"type": "weather_data/save_prefs", **prefs})
    msg = await _send(hass, hass_ws_client, {"type": "weather_data/get_info"})

    assert msg["result"]["rain_gauge"] == expected


async def test_air_quality_and_pollen(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors are only detected from air quality services."""
    mock_integration(
        hass,
        MockModule("airly", partial_manifest={"categories": [AIR_QUALITY_CATEGORY]}),
    )
    mock_integration(
        hass,
        MockModule(
            "accuweather",
            partial_manifest={
                "categories": ["weather_alerts.forecasts", AIR_QUALITY_CATEGORY]
            },
        ),
    )
    mock_integration(
        hass,
        MockModule(
            "xiaomi_miio", partial_manifest={"categories": ["climate.air_purifiers"]}
        ),
    )
    pm25 = _add_sensor(
        hass, entity_registry, "airly", "outside_pm25", {"device_class": "pm25"}
    )
    aqi = _add_sensor(
        hass, entity_registry, "airly", "outside_aqi", {"device_class": "aqi"}
    )
    _add_sensor(hass, entity_registry, "airly", "second_pm25", {"device_class": "pm25"})
    _add_sensor(
        hass, entity_registry, "xiaomi_miio", "purifier_pm25", {"device_class": "pm25"}
    )
    grass_pollen = _add_sensor(
        hass,
        entity_registry,
        "accuweather",
        "home_grass",
        translation_key="grass_pollen",
    )
    _add_sensor(
        hass,
        entity_registry,
        "accuweather",
        "home_cloud_ceiling",
        translation_key="cloud_ceiling",
    )

    msg = await _send(hass, hass_ws_client, {"type": "weather_data/get_info"})

    assert msg["result"]["air_quality"] == [aqi, pm25]
    assert msg["result"]["pollen"] == [grass_pollen]


async def test_selected_sensors(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test selected sensors are used, without the ones that no longer exist."""
    hass.states.async_set("sensor.indoor_pm25", "8", {"device_class": "pm25"})
    hass.states.async_set("sensor.tree_pollen", "2")

    await _send(
        hass,
        hass_ws_client,
        {
            "type": "weather_data/save_prefs",
            "air_quality_entities": ["sensor.indoor_pm25", "sensor.removed"],
            "pollen_entities": ["sensor.tree_pollen"],
        },
    )
    msg = await _send(hass, hass_ws_client, {"type": "weather_data/get_info"})

    assert msg["result"]["air_quality"] == ["sensor.indoor_pm25"]
    assert msg["result"]["pollen"] == ["sensor.tree_pollen"]
