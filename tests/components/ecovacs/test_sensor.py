"""Tests for Ecovacs sensors."""

from unittest.mock import Mock

from deebot_client.event_bus import EventBus
from deebot_client.events import (
    BatteryEvent,
    ErrorEvent,
    LifeSpan,
    LifeSpanEvent,
    NetworkInfoEvent,
    StatsEvent,
    TotalStatsEvent,
    station,
)
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .util import block_till_done

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.SENSOR


async def notify_events(hass: HomeAssistant, event_bus: EventBus):
    """Notify events."""
    event_bus.notify(StatsEvent(10, 300, "spotArea"))
    event_bus.notify(TotalStatsEvent(60, 144000, 123))
    event_bus.notify(BatteryEvent(100))
    event_bus.notify(BatteryEvent(100))
    event_bus.notify(
        NetworkInfoEvent("192.168.0.10", "Testnetwork", -62, "AA:BB:CC:DD:EE:FF")
    )
    event_bus.notify(LifeSpanEvent(LifeSpan.BRUSH, 80, 60 * 60))
    event_bus.notify(LifeSpanEvent(LifeSpan.FILTER, 56, 40 * 60))
    event_bus.notify(LifeSpanEvent(LifeSpan.SIDE_BRUSH, 40, 20 * 60))
    event_bus.notify(ErrorEvent(0, "NoError: Robot is operational"))
    event_bus.notify(station.StationEvent(station.State.EMPTYING))
    await block_till_done(hass, event_bus)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "yna5x1",
            [
                "sensor.ozmo_950_area_cleaned",
                "sensor.ozmo_950_cleaning_duration",
                "sensor.ozmo_950_total_area_cleaned",
                "sensor.ozmo_950_total_cleaning_duration",
                "sensor.ozmo_950_total_cleanings",
                "sensor.ozmo_950_battery",
                "sensor.ozmo_950_ip_address",
                "sensor.ozmo_950_wi_fi_rssi",
                "sensor.ozmo_950_wi_fi_ssid",
                "sensor.ozmo_950_main_brush_lifespan",
                "sensor.ozmo_950_filter_lifespan",
                "sensor.ozmo_950_side_brush_lifespan",
                "sensor.ozmo_950_error",
            ],
        ),
        (
            "5xu9h3",
            [
                "sensor.goat_g1_area_cleaned",
                "sensor.goat_g1_cleaning_duration",
                "sensor.goat_g1_total_area_cleaned",
                "sensor.goat_g1_total_cleaning_duration",
                "sensor.goat_g1_total_cleanings",
                "sensor.goat_g1_battery",
                "sensor.goat_g1_ip_address",
                "sensor.goat_g1_wi_fi_rssi",
                "sensor.goat_g1_wi_fi_ssid",
                "sensor.goat_g1_blade_lifespan",
                "sensor.goat_g1_lens_brush_lifespan",
                "sensor.goat_g1_error",
            ],
        ),
        (
            "qhe2o2",
            [
                "sensor.dusty_area_cleaned",
                "sensor.dusty_cleaning_duration",
                "sensor.dusty_total_area_cleaned",
                "sensor.dusty_total_cleaning_duration",
                "sensor.dusty_total_cleanings",
                "sensor.dusty_battery",
                "sensor.dusty_ip_address",
                "sensor.dusty_wi_fi_rssi",
                "sensor.dusty_wi_fi_ssid",
                "sensor.dusty_station_state",
                "sensor.dusty_main_brush_lifespan",
                "sensor.dusty_filter_lifespan",
                "sensor.dusty_side_brush_lifespan",
                "sensor.dusty_unit_care_lifespan",
                "sensor.dusty_round_mop_lifespan",
                "sensor.dusty_error",
            ],
        ),
    ],
    ids=["yna5x1", "5xu9h3", "qhe2o2"],
)
async def test_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    controller: EcovacsController,
    entity_ids: list[str],
) -> None:
    """Test that sensor entity snapshots match."""
    assert hass.states.async_entity_ids() == entity_ids
    for entity_id in entity_ids:
        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert state.state == STATE_UNKNOWN

    device = controller.devices[0]
    await notify_events(hass, device.events)
    for entity_id in entity_ids:
        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert snapshot(name=f"{entity_id}:state") == state

        assert (entity_entry := entity_registry.async_get(state.entity_id))
        assert snapshot(name=f"{entity_id}:entity-registry") == entity_entry

        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert device_entry.identifiers == {(DOMAIN, device.device_info["did"])}


@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "yna5x1",
            [
                "sensor.ozmo_950_error",
                "sensor.ozmo_950_ip_address",
                "sensor.ozmo_950_wi_fi_rssi",
                "sensor.ozmo_950_wi_fi_ssid",
            ],
        ),
        (
            "5xu9h3",
            [
                "sensor.goat_g1_error",
                "sensor.goat_g1_ip_address",
                "sensor.goat_g1_wi_fi_rssi",
                "sensor.goat_g1_wi_fi_ssid",
            ],
        ),
    ],
    ids=["yna5x1", "5xu9h3"],
)
async def test_disabled_by_default_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_ids: list[str]
) -> None:
    """Test the disabled by default sensors."""
    for entity_id in entity_ids:
        assert not hass.states.get(entity_id)

        assert (entry := entity_registry.async_get(entity_id)), (
            f"Entity registry entry for {entity_id} is missing"
        )
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_vacbot", "init_integration"
)
@pytest.mark.parametrize(("device_fixture"), ["123"])
async def test_legacy_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_vacbot: Mock,
) -> None:
    """Test that sensor entity snapshots match."""
    mock_vacbot.components = {"main_brush": 0.8, "side_brush": 0.6, "filter": 0.4}
    mock_vacbot.lifespanEvents.notify("dummy_data")
    await hass.async_block_till_done(wait_background_tasks=True)

    states = hass.states.async_entity_ids()
    assert snapshot(name="states") == states

    for entity_id in hass.states.async_entity_ids():
        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert snapshot(name=f"{entity_id}:state") == state

        assert (entity_entry := entity_registry.async_get(state.entity_id))
        assert snapshot(name=f"{entity_id}:entity-registry") == entity_entry

        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert device_entry.identifiers == {(DOMAIN, "E1234567890000000003")}
