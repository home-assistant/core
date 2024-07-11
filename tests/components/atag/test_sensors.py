"""Tests for the Atag sensor platform."""

from homeassistant.components.atag.sensor import SENSORS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import UID, init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation of ATAG sensors."""
    entry = await init_integration(hass, aioclient_mock)

    for item in SENSORS:
        sensor_id = "_".join(f"sensor.{item}".lower().split())
        assert entity_registry.async_is_registered(sensor_id)
        entry = entity_registry.async_get(sensor_id)
        assert entry.unique_id in [f"{UID}-{v}" for v in SENSORS.values()]
