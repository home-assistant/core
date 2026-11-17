"""Test the myStrom sensors."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.mystrom.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import DEVICE_MAC
from .test_init import init_integration


async def test_pir_sensors_are_polled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the motion sensor readings are refreshed while polling."""
    await init_integration(hass, config_entry, 110)

    device = config_entry.runtime_data.device
    assert hass.states.get("sensor.mystrom_device_temperature").state == "24.87"
    assert hass.states.get("sensor.mystrom_device_illuminance").state == "16.0"

    # The mock only reports readings once they have been fetched, and nothing
    # else talks to a motion sensor, so this stays cleared unless the sensors
    # fetch them themselves.
    device._requested_state = False
    device._state["temperature_compensated"] = 21.5
    device._state["intensity"] = 42

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device._requested_state is True
    assert hass.states.get("sensor.mystrom_device_temperature").state == "21.5"
    assert hass.states.get("sensor.mystrom_device_illuminance").state == "42.0"


@pytest.mark.parametrize(
    "light_disabled_by",
    [
        pytest.param(None, id="light_enabled"),
        pytest.param(er.RegistryEntryDisabler.USER, id="light_disabled"),
    ],
)
async def test_bulb_power_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    light_disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """Test a bulb reports the power it draws, with or without its light."""
    entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        DEVICE_MAC,
        config_entry=config_entry,
        disabled_by=light_disabled_by,
    )
    await init_integration(hass, config_entry, 102)

    device = config_entry.runtime_data.device
    assert hass.states.get("sensor.mystrom_device_power").state == "0.45"

    device._requested_state = False
    device._state["power"] = 5.1

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device._requested_state is True
    assert hass.states.get("sensor.mystrom_device_power").state == "5.1"
