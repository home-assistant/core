"""Tests for the UniFi Protect Alarm Hub (Public API) entities."""

from unittest.mock import Mock

import pytest
from uiprotect.data import LinkStation, PublicBootstrap

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import MockUFPFixture, init_entry

from tests.common import load_json_object_fixture

DOMAIN = "unifiprotect"

ALARM_HUB_MAC = "AABBCCDDEEFF"


def _make_alarm_hub() -> LinkStation:
    """Build a real LinkStation alarm hub from the sample fixture."""
    data = load_json_object_fixture("sample_alarm_hub.json", DOMAIN)
    return LinkStation.from_unifi_dict(**data)


def _make_public_bootstrap(hub: LinkStation | None) -> Mock:
    """Build a public bootstrap mock holding the given alarm hub."""
    pb = Mock(spec=PublicBootstrap)
    pb.alarm_hubs = {hub.id: hub} if hub is not None else {}
    pb.sirens = {}
    pb.relays = {}
    pb.arm_mode = None
    pb.arm_profiles = {}
    return pb


@pytest.fixture(name="alarm_hub")
def _alarm_hub_fixture() -> LinkStation:
    return _make_alarm_hub()


@pytest.fixture(name="ufp_with_alarm_hub")
def _ufp_with_alarm_hub(ufp: MockUFPFixture, alarm_hub: LinkStation) -> MockUFPFixture:
    """Configure the ufp fixture with one alarm hub via the public API."""
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(alarm_hub)
    return ufp


async def test_sensors_not_created_without_public_bootstrap(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """No alarm hub sensors when the public bootstrap is unavailable."""
    ufp.api.has_public_bootstrap = False
    await init_entry(hass, ufp, [])
    assert hass.states.get("sensor.alarm_hub_battery_voltage") is None


async def test_alarm_hub_battery_voltage_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_alarm_hub: MockUFPFixture,
) -> None:
    """Battery voltage sensor is created with the reported voltage."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    entity_id = "sensor.alarm_hub_battery_voltage"
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.unique_id == f"{ALARM_HUB_MAC}_battery_voltage"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "12.108427"
    assert state.attributes["device_class"] == "voltage"
    assert state.attributes["unit_of_measurement"] == "V"


async def test_alarm_hub_last_event_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_alarm_hub: MockUFPFixture,
) -> None:
    """Last-event timestamp sensor is created."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    entity_id = "sensor.alarm_hub_last_event"
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.unique_id == f"{ALARM_HUB_MAC}_last_event"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["device_class"] == "timestamp"
