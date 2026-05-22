"""Test Qbus sensors."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_mqtt_message, snapshot_platform

_PAYLOAD_WEATHER_STATE_LUX = (
    '{"id":"UL60","properties":{"lightSouth":21},"type":"state"}'
)
_PAYLOAD_WEATHER_STATE_WIND = '{"id":"UL60","properties":{"wind":25},"type":"state"}'

_TOPIC_WEATHER_STATE = "cloudapp/QBUSMQTTGW/UL1/UL60/state"

_ILLUMINANCE_ENTITY_ID = "sensor.tuin_weersensor_illuminance_south"
_WIND_ENTITY_ID = "sensor.tuin_weersensor_wind_speed"


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


async def test_weather_lux_uses_scale_factor(
    hass: HomeAssistant, setup_integration: None
) -> None:
    """Test whether lux values are using the scale factor."""

    async_fire_mqtt_message(hass, _TOPIC_WEATHER_STATE, _PAYLOAD_WEATHER_STATE_LUX)
    await hass.async_block_till_done()

    assert hass.states.get(_ILLUMINANCE_ENTITY_ID).state == "21000"


async def test_weather_wind_skips_scale_factor(
    hass: HomeAssistant, setup_integration: None
) -> None:
    """Test whether wind value is not using the scale factor."""

    async_fire_mqtt_message(hass, _TOPIC_WEATHER_STATE, _PAYLOAD_WEATHER_STATE_WIND)
    await hass.async_block_till_done()

    assert hass.states.get(_WIND_ENTITY_ID).state == "25"
