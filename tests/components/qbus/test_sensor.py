"""Test Qbus sensors."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_mqtt_message, snapshot_platform

_TOPIC_WEATHER_STATE = "cloudapp/QBUSMQTTGW/UL1/UL60/state"


async def test_sensor(
    hass: HomeAssistant,
    setup_integration_deferred: Callable[[], Awaitable],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor."""

    with patch("homeassistant.components.qbus.PLATFORMS", [Platform.SENSOR]):
        await setup_integration_deferred()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_gauge_unit_applied(
    hass: HomeAssistant, setup_integration: None
) -> None:
    """Test gauge sensor uses reported unit."""

    entity = hass.states.get("sensor.garage_energie")
    assert entity
    assert entity.attributes[ATTR_UNIT_OF_MEASUREMENT] == "Wh"


async def test_sensor_gauge_unit_missing(
    hass: HomeAssistant, setup_integration: None
) -> None:
    """Test gauge sensor falls back to description default."""

    entity = hass.states.get("sensor.tuin_luchtkwaliteit")
    assert entity
    assert entity.attributes[ATTR_UNIT_OF_MEASUREMENT] == "ppm"


async def test_weather_lux_uses_scale_factor(
    hass: HomeAssistant, setup_integration: None
) -> None:
    """Test whether lux values are using the scale factor."""

    async_fire_mqtt_message(
        hass,
        _TOPIC_WEATHER_STATE,
        '{"id":"UL60","properties":{"lightSouth":21},"type":"state"}',
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.tuin_weersensor_illuminance_south").state == "21000"


async def test_weather_wind_skips_scale_factor(
    hass: HomeAssistant, setup_integration: None
) -> None:
    """Test whether wind value is not using the scale factor."""

    async_fire_mqtt_message(
        hass,
        _TOPIC_WEATHER_STATE,
        '{"id":"UL60","properties":{"wind":25},"type":"state"}',
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.tuin_weersensor_wind_speed").state == "25"
