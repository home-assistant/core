"""Tests for Victron GX MQTT sensors."""

from __future__ import annotations

import pytest
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.victron_gx.const import (
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_ROOT_TOPIC_PREFIX,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def basic_config():
    """Provide basic configuration."""
    return {
        CONF_HOST: "venus.local",
        CONF_PORT: 1883,
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
        CONF_SSL: False,
        CONF_INSTALLATION_ID: "123",
        CONF_MODEL: "Venus GX",
        CONF_SERIAL: "HQ12345678",
        CONF_ROOT_TOPIC_PREFIX: "N/",
    }


@pytest.fixture
def mock_config_entry(basic_config):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_unique_id",
        data=basic_config,
    )


async def test_victron_battery_sensor(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test SENSOR MetricKind - battery current sensor is created and updated."""
    victron_hub, mock_config_entry = init_integration

    # Inject a sensor metric (battery current)
    await inject_message(victron_hub, "N/123/battery/0/Dc/0/Current", '{"value": 10.5}')
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    # Verify entity was created by checking entity registry
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Exactly one entity is expected for this injected metric.
    assert len(entities) == 1
    entity = entities[0]
    assert entity.entity_id == "sensor.battery_dc_bus_current"
    assert entity.unique_id == "battery_0_battery_current"
    assert entity.original_device_class is SensorDeviceClass.CURRENT
    assert entity.unit_of_measurement == "A"
    assert entity.translation_key == "battery_current"

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "10.5"
    assert state.attributes["state_class"] is SensorStateClass.MEASUREMENT
    assert state.attributes["device_class"] == "current"
    assert state.attributes["unit_of_measurement"] == "A"

    # Update the same metric to exercise the entity update callback path.
    await inject_message(victron_hub, "N/123/battery/0/Dc/0/Current", '{"value": 11.2}')
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "11.2"


async def test_victron_enum_sensor(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test sensor with VictronEnum value normalizes to enum id."""
    victron_hub, _mock_config_entry = init_integration

    # SystemState/State produces a VictronEnum (State enum)
    await inject_message(
        victron_hub, "N/123/system/0/SystemState/State", '{"value": 1}'
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.victron_venus_system_state")
    assert state is not None
    # Value 1 maps to State.LOW_POWER with id="low_power"
    assert state.state == "low_power"
