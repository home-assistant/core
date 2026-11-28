"""Test ViCare sensor entity."""

from contextlib import ExitStack
from datetime import timedelta
import threading
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from PyViCare.PyViCareService import ViCareDeviceAccessor
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.vicare.const import DEFAULT_CACHE_DURATION, DOMAIN
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json"),
        Fixture({"type:heatpump"}, "vicare/Vitocal250A.json"),
        Fixture({"type:heatpump"}, "vicare/Vitocal222G_Vitovent300W.json"),
        Fixture({"type:ventilation"}, "vicare/ViAir300F.json"),
        Fixture({"type:ventilation"}, "vicare/VitoPure.json"),
        Fixture({"type:ess"}, "vicare/VitoChargeVX3.json"),
        Fixture({None}, "vicare/VitoValor.json"),
        Fixture({"type:climateSensor"}, "vicare/RoomSensor1.json"),
        Fixture({"type:climateSensor"}, "vicare/RoomSensor2.json"),
        Fixture({"type:radiator"}, "vicare/ZigbeeTRV.json"),
        Fixture({"type:repeater"}, "vicare/ZigbeeRepeater.json"),
        # FHT main and channel are the same physical zigbee node, so they share
        # a gateway; this lets the channel link to the main via via_device.
        Fixture({"type:fhtMain"}, "vicare/FHTMain.json", gateway_id="fht_gateway"),
        Fixture(
            {"type:fhtChannel"}, "vicare/FHTChannel.json", gateway_id="fht_gateway"
        ),
        Fixture({"type:boiler"}, "vicare/Vitoligno300C.json"),
        Fixture({"type:virtual;smartRoomControl"}, "vicare/RoomControl.json"),
        Fixture({"type:waterTreatment"}, "vicare/VitosetAqua.json"),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}.PyViCare", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_room_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that each room is a child device of its room control."""
    fixtures: list[Fixture] = [
        Fixture({"type:virtual;smartRoomControl"}, "vicare/RoomControl.json"),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}.PyViCare", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    room_control = device_registry.async_get_device_by_identifier(
        (DOMAIN, "gateway0_deviceId0"), mock_config_entry.entry_id
    )
    assert room_control is not None
    assert room_control.name == "model0"
    rooms = sorted(
        (room.name, room.parent_device_id)
        for room in dr.async_entries_for_parent_device(device_registry, room_control.id)
    )
    assert rooms == [("Room 0", room_control.id), ("Room 1", room_control.id)]


async def test_room_control_without_rooms(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that a room control without rooms adds no device."""
    fixtures: list[Fixture] = [
        Fixture(
            {"type:virtual;smartRoomControl"}, "vicare/RoomControlWithoutRooms.json"
        ),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}.PyViCare", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    assert not dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_api_read_on_event_loop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entity values must be read in the executor, never on the event loop.

    A PyViCare getter takes the library's cache lock and does blocking I/O when
    that cache is cold, so reading a value from a property freezes the loop for
    the length of an HTTP request.
    """
    fixtures: list[Fixture] = [
        Fixture({"type:heatpump"}, "vicare/Vitocal250A.json"),
        Fixture({"type:ventilation"}, "vicare/VitoPure.json"),
    ]
    mock_vicare = MockPyViCare(fixtures)
    services = {id(d.service): d.service for d in mock_vicare.devices}

    loop_thread_id = threading.get_ident()
    reads_on_loop: list[str] = []
    reads_in_executor: list[str] = []

    def guard(service):
        read_property = service.getProperty

        def guarded_get_property(
            accessor: ViCareDeviceAccessor, property_name: str
        ) -> Any:
            if threading.get_ident() == loop_thread_id:
                reads_on_loop.append(property_name)
            else:
                reads_in_executor.append(property_name)
            return read_property(accessor, property_name)

        return patch.object(service, "getProperty", guarded_get_property)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}.PyViCare", return_value=mock_vicare),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR, Platform.FAN]),
    ):
        await setup_integration(hass, mock_config_entry)

        entity_ids = hass.states.async_entity_ids(SENSOR_DOMAIN)
        fan_ids = hass.states.async_entity_ids(FAN_DOMAIN)
        assert entity_ids
        assert fan_ids

        with ExitStack() as stack:
            for service in services.values():
                stack.enter_context(guard(service))

            freezer.tick(timedelta(seconds=DEFAULT_CACHE_DURATION * 2))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

            for entity_id in (entity_ids[0], fan_ids[0]):
                await async_update_entity(hass, entity_id)

    assert not reads_on_loop
    # Without this the test would also pass if nothing read a value at all.
    assert reads_in_executor


# Burner stops per reason as PyViCare's Vitodens 200-W test data reports them,
# with abnormal stops added. "timeAllStops" is the burner runtime in seconds.
BURNER_STOPS: dict[str, int] = {
    "flameLossDuringOperationAllStops": 1,
    "flameLossDuringOperationLastStops": 0,
    "flueGasTemperatureSensorAllStops": 0,
    "flueGasTemperatureSensorLastStops": 0,
    "ionizationAlignmentAllStops": 0,
    "ionizationAlignmentLastStops": 0,
    "noGasAtStartAllStops": 0,
    "noGasAtStartLastStops": 0,
    "noIgnitionAtStartAllStops": 3,
    "noIgnitionAtStartLastStops": 1,
    "noIonizationAtStartAllStops": 0,
    "noIonizationAtStartLastStops": 0,
    "normalStopAllStops": 23,
    "normalStopLastStops": 23,
    "safetyShutdownAllStops": 0,
    "safetyShutdownErrorShutdownAllStops": 0,
    "safetyShutdownErrorShutdownLastStops": 0,
    "safetyShutdownLastStops": 0,
    "safetyTimeAllStops": 0,
    "safetyTimeLastStops": 0,
    "stabilisationProcessAllStops": 0,
    "stabilisationProcessLastStops": 0,
    "temperatureMonitorAllStops": 0,
    "temperatureMonitorIonizationComparisonAllStops": 0,
    "temperatureMonitorIonizationComparisonLastStops": 0,
    "temperatureMonitorLastStops": 0,
    "timeAllStops": 116572,
    "timeLastStops": 116572,
    "undervoltageAllStops": 0,
    "undervoltageLastStops": 0,
}


async def _setup_with_burner_stops(
    hass: HomeAssistant, config_entry: MockConfigEntry, fixture: Fixture
) -> None:
    """Set up the sensors of a device that reports burner stops."""
    vicare = MockPyViCare([fixture])
    # The mock serves the fixture's device 0 as deviceId0.
    vicare.services["gateway0"]._features["deviceId0"].append(
        {
            "apiVersion": 1,
            "commands": {},
            "components": [],
            "deviceId": "0",
            "feature": "device.timeseries.burner.stops",
            "gatewayId": "################",
            "isEnabled": True,
            "isReady": True,
            "properties": {
                name: {"type": "number", "unit": "", "value": value}
                for name, value in BURNER_STOPS.items()
            },
            "timestamp": "2025-09-24T07:43:23.186Z",
            "uri": "https://api.viessmann-platform.io/iot/v1/equipment/installations/######/gateways/################/devices/deviceId0/features/device.timeseries.burner.stops",
        }
    )
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}.PyViCare", return_value=vicare),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, config_entry)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        ("sensor.model0_normal_burner_stops", "23"),
        ("sensor.model0_burner_stops_without_ignition_at_start", "3"),
        ("sensor.model0_burner_stops_by_flame_loss", "1"),
        ("sensor.model0_burner_stops_by_undervoltage", "0"),
    ],
)
async def test_burner_stops(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test the burner stops of a gas boiler per stop reason."""
    await _setup_with_burner_stops(
        hass, mock_config_entry, Fixture({"type:boiler"}, "vicare/Vitodens300W.json")
    )

    assert hass.states.get(entity_id).state == expected_state


async def test_burner_stops_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the burner stops are diagnostic entities disabled by default."""
    await _setup_with_burner_stops(
        hass, mock_config_entry, Fixture({"type:boiler"}, "vicare/Vitodens300W.json")
    )

    entries = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "-burner_stops_" in entry.unique_id
    ]
    assert len(entries) == 14
    for entry in entries:
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_no_burner_stops_on_heat_pump(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a heat pump gets no burner stops, even if the API reported them."""
    await _setup_with_burner_stops(
        hass, mock_config_entry, Fixture({"type:heatpump"}, "vicare/Vitocal250A.json")
    )

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entries
    assert not [entry for entry in entries if "-burner_stops_" in entry.unique_id]
