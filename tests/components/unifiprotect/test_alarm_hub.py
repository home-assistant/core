"""Tests for the UniFi Protect Alarm Hub (Public API) entities."""

from unittest.mock import Mock

import pytest
from syrupy.assertion import SnapshotAssertion
from uiprotect.data import LinkStation, PublicBootstrap
from uiprotect.websocket import WebsocketState

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .utils import MockUFPFixture, init_entry

from tests.common import load_json_object_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

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


async def test_alarm_hub_tamper_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_alarm_hub: MockUFPFixture,
) -> None:
    """Tamper cover binary sensor reflects the cover status."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    entity_id = "binary_sensor.alarm_hub_tamper"
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.unique_id == f"{ALARM_HUB_MAC}_tamper"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["device_class"] == "tamper"
    assert state.state == "off"  # cover closed


async def test_alarm_hub_battery_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_alarm_hub: MockUFPFixture,
) -> None:
    """Battery problem binary sensor is off when battery_status is ok."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    entity_id = "binary_sensor.alarm_hub_battery"
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.unique_id == f"{ALARM_HUB_MAC}_battery"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["device_class"] == "battery"
    assert state.state == "off"


async def test_alarm_hub_zone_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_alarm_hub: MockUFPFixture,
) -> None:
    """One binary sensor per configured input, with mapped device classes."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    # Named motion zone.
    hallway = hass.states.get("binary_sensor.alarm_hub_hallway")
    assert hallway is not None
    assert hallway.attributes["device_class"] == "motion"
    assert hallway.state == "off"  # status normal

    # Named emergency button -> safety.
    tamper_btn = entity_registry.async_get("binary_sensor.alarm_hub_24_hour_tamper")
    assert tamper_btn is not None
    assert tamper_btn.unique_id == f"{ALARM_HUB_MAC}_input_16"
    assert (
        hass.states.get("binary_sensor.alarm_hub_24_hour_tamper").attributes[
            "device_class"
        ]
        == "safety"
    )

    # Unnamed entry zone -> opening, fallback name "Zone 25".
    entry = hass.states.get("binary_sensor.alarm_hub_zone_25")
    assert entry is not None
    assert entry.attributes["device_class"] == "opening"


async def test_alarm_hub_zone_triggered_state(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """A zone in the ALARM status reports on."""
    # Mark the Hallway motion zone (input 24) as triggered.
    alarm_hub.alarm_hub["input"]["24"]["status"] = "alarm"
    await init_entry(hass, ufp_with_alarm_hub, [])

    state = hass.states.get("binary_sensor.alarm_hub_hallway")
    assert state is not None
    assert state.state == "on"


async def test_alarm_hub_zone_unknown_status_unavailable(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """A zone with an unreadable (UNKNOWN) status is unavailable, not 'off'."""
    alarm_hub.alarm_hub["input"]["24"]["status"] = "unknown"
    await init_entry(hass, ufp_with_alarm_hub, [])

    state = hass.states.get("binary_sensor.alarm_hub_hallway")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_alarm_hub_disabled_zone_not_created(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """A disabled input is not surfaced as a zone entity."""
    alarm_hub.alarm_hub["input"]["24"]["enable"] = "off"
    await init_entry(hass, ufp_with_alarm_hub, [])

    assert hass.states.get("binary_sensor.alarm_hub_hallway") is None


async def test_alarm_hub_in_diagnostics(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    hass_client: ClientSessionGenerator,
) -> None:
    """Alarm hubs are included (anonymized) in config entry diagnostics."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, ufp_with_alarm_hub.entry
    )

    assert "alarm_hubs" in diag
    assert len(diag["alarm_hubs"]) == 1
    hub = diag["alarm_hubs"][0]
    # Anonymized: the real MAC must not leak.
    assert hub["mac"] != ALARM_HUB_MAC
    assert "alarmHub" in hub


async def test_alarm_hub_device_and_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    ufp_with_alarm_hub: MockUFPFixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the alarm hub device and all of its entities."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    device = device_registry.async_get_device(identifiers={(DOMAIN, ALARM_HUB_MAC)})
    assert device is not None
    assert device == snapshot(name="device")

    entries = er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    )
    assert entries
    for entry in sorted(entries, key=lambda e: e.entity_id):
        assert entry == snapshot(name=entry.entity_id)
        assert hass.states.get(entry.entity_id) == snapshot(
            name=f"{entry.entity_id}-state"
        )


async def test_alarm_hub_availability_follows_public_ws(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
) -> None:
    """Availability tracks the public websocket health, not the private one."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    entity_id = "sensor.alarm_hub_battery_voltage"
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    # Private connection drops: the public-only alarm hub stays available.
    assert ufp_with_alarm_hub.ws_state_subscription is not None
    ufp_with_alarm_hub.ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    # Public connection drops: now the alarm hub is unavailable.
    assert ufp_with_alarm_hub.devices_ws_state_subscription is not None
    ufp_with_alarm_hub.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Public connection restored while the private one is still down: available.
    ufp_with_alarm_hub.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


async def test_alarm_hub_state_updates_from_public_ws(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """A public devices WS update for the hub refreshes its entities."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    entity_id = "binary_sensor.alarm_hub_hallway"
    assert hass.states.get(entity_id).state == "off"

    # Trigger the Hallway motion zone (input 24) on the cached hub object.
    alarm_hub.alarm_hub["input"]["24"]["status"] = "alarm"

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = alarm_hub
    mock_msg.new_obj = alarm_hub
    assert ufp_with_alarm_hub.devices_ws_subscription is not None
    ufp_with_alarm_hub.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "on"


async def test_alarm_hub_becomes_unavailable_when_removed(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """A delete WS frame (new_obj=None) marks the hub's entities unavailable."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    entity_id = "sensor.alarm_hub_battery_voltage"
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    # Drop the hub from the public bootstrap, then send a delete frame.
    ufp_with_alarm_hub.api.public_bootstrap.alarm_hubs = {}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = alarm_hub
    mock_msg.new_obj = None
    assert ufp_with_alarm_hub.devices_ws_subscription is not None
    ufp_with_alarm_hub.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_alarm_hub_disconnected_battery(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """A disconnected backup battery degrades gracefully.

    Real hardware reports a disconnected, removed or fully flat backup battery
    identically: ``connection: disconnected`` with ``voltage: 0`` and no
    ``batteryStatus``. The battery is an optional add-on, so this is also the
    steady state for a hub with no battery fitted and must not read as a problem.
    """
    assert alarm_hub.alarm_hub is not None
    alarm_hub.alarm_hub["battery"] = {"connection": "disconnected", "voltage": 0}
    await init_entry(hass, ufp_with_alarm_hub, [])

    # An absent batteryStatus must not read as a problem (optional battery).
    battery = hass.states.get("binary_sensor.alarm_hub_battery")
    assert battery is not None
    assert battery.state == "off"

    # Voltage reads unknown rather than a misleading 0.0 V.
    voltage = hass.states.get("sensor.alarm_hub_battery_voltage")
    assert voltage is not None
    assert voltage.state == "unknown"
