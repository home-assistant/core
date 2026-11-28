"""Test the Elexa Guardian sensors."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.guardian import CONF_UID, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

UPTIME_MINUTES = 41


@pytest.fixture(name="platforms")
def platforms_fixture() -> list[Platform]:
    """Exercise only the sensor platform."""
    return [Platform.SENSOR]


async def test_valve_controller_uptime_is_absolute(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    setup_guardian: None,
) -> None:
    """Uptime is the absolute time the valve controller booted.

    Diagnostics report whole minutes since boot. The sensor device class is
    uptime, which stores that instant as a UTC timestamp and suppresses poll
    jitter.
    """
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{config_entry.data[CONF_UID]}_uptime"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.UPTIME
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    booted = dt_util.utcnow() - timedelta(minutes=UPTIME_MINUTES)
    assert state.state == booted.isoformat(timespec="seconds")
