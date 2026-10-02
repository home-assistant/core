"""Tests for the Modern Forms sensor platform."""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.modern_forms.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration, init_integration_gen4

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the creation and values of the Modern Forms sensors."""

    entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        "AA:BB:CC:DD:EE:FF_light_sleep_timer_active",
        suggested_object_id="modernformsfan_light_sleep_timer_active",
        disabled_by=None,
    )
    entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        "AA:BB:CC:DD:EE:FF_fan_sleep_timer_active",
        suggested_object_id="modernformsfan_fan_sleep_timer_active",
        disabled_by=None,
    )

    await init_integration(hass, aioclient_mock)

    # Light timer remaining time
    state = hass.states.get("binary_sensor.modernformsfan_light_sleep_timer_active")
    assert state
    assert state.state == "off"

    # Fan timer remaining time
    state = hass.states.get("binary_sensor.modernformsfan_fan_sleep_timer_active")
    assert state
    assert state.state == "off"


async def test_no_sleep_timer_binary_sensors_on_gen4(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the sleep-timer binary sensors aren't created for Gen4 fans."""
    await init_integration_gen4(hass, aioclient_mock)

    # Both entities are disabled by default, so checking hass.states here
    # wouldn't distinguish "not created" from "created but disabled" --
    # check the entity registry instead.
    assert (
        entity_registry.async_get("binary_sensor.modernformsfan_fan_sleep_timer_active")
        is None
    )
    assert (
        entity_registry.async_get(
            "binary_sensor.modernformsfan_light_sleep_timer_active"
        )
        is None
    )
