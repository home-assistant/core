"""Test the Teslemetry cover platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import COMMAND_OK, METADATA_NOSCOPE, VEHICLE_DATA_ALT


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cover(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the cover entities are correct."""

    entry = await setup_platform(hass, [Platform.COVER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cover_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the cover entities are correct with alternate values."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    entry = await setup_platform(hass, [Platform.COVER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cover_noscope(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_metadata: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the cover entities are correct without scopes."""

    mock_metadata.return_value = METADATA_NOSCOPE
    entry = await setup_platform(hass, [Platform.COVER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cover_services(
    hass: HomeAssistant,
) -> None:
    """Tests that the cover entities are correct."""

    await setup_platform(hass, [Platform.COVER])

    # Vent Windows
    entity_id = "cover.test_windows"
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.window_control",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        call.assert_called_once()
        state = hass.states.get(entity_id)
        assert state
        assert state.state == CoverState.OPEN

        call.reset_mock()
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: ["cover.test_windows"]},
            blocking=True,
        )
        call.assert_called_once()
        state = hass.states.get(entity_id)
        assert state
        assert state.state == CoverState.CLOSED

    # Charge Port Door
    entity_id = "cover.test_charge_port_door"
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.charge_port_door_open",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        call.assert_called_once()
        state = hass.states.get(entity_id)
        assert state
        assert state.state == CoverState.OPEN

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.charge_port_door_close",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        call.assert_called_once()
        state = hass.states.get(entity_id)
        assert state
        assert state.state == CoverState.CLOSED

    # Frunk
    entity_id = "cover.test_frunk"
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.actuate_trunk",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        call.assert_called_once()
        state = hass.states.get(entity_id)
        assert state
        assert state.state == CoverState.OPEN

    # Trunk
    entity_id = "cover.test_trunk"
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.actuate_trunk",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        call.assert_called_once()
        state = hass.states.get(entity_id)
        assert state
        assert state.state == CoverState.OPEN

        call.reset_mock()
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        call.assert_called_once()
        state = hass.states.get(entity_id)
        assert state
        assert state.state == CoverState.CLOSED

    # Sunroof
    entity_id = "cover.test_sunroof"
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.sun_roof_control",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        call.assert_called_once()
        state = hass.states.get(entity_id)
        assert state
        assert state.state == CoverState.OPEN

        call.reset_mock()
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        call.assert_called_once()
        state = hass.states.get(entity_id)
        assert state
        assert state.state == CoverState.OPEN

        call.reset_mock()
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        call.assert_called_once()
        state = hass.states.get(entity_id)
        assert state
        assert state.state == CoverState.CLOSED


async def test_cover_streaming(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the binary sensor entities with streaming are correct."""

    entry = await setup_platform(hass, [Platform.COVER])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.FD_WINDOW: "WindowStateClosed",
                Signal.FP_WINDOW: "WindowStateClosed",
                Signal.RD_WINDOW: "WindowStateClosed",
                Signal.RP_WINDOW: "WindowStateClosed",
                Signal.CHARGE_PORT_DOOR_OPEN: False,
                Signal.DOOR_STATE: {
                    "DoorState": {
                        "DriverFront": False,
                        "DriverRear": False,
                        "PassengerFront": False,
                        "PassengerRear": False,
                        "TrunkFront": False,
                        "TrunkRear": False,
                    }
                },
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    # Reload the entry
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Assert the entities restored their values
    for entity_id in (
        "cover.test_windows",
        "cover.test_charge_port_door",
        "cover.test_frunk",
        "cover.test_trunk",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=f"{entity_id}-closed")

    # Send some alternative data with everything open
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.FD_WINDOW: "WindowStateOpened",
                Signal.FP_WINDOW: "WindowStateOpened",
                Signal.RD_WINDOW: "WindowStateOpened",
                Signal.RP_WINDOW: "WindowStateOpened",
                Signal.CHARGE_PORT_DOOR_OPEN: False,
                Signal.DOOR_STATE: {
                    "DoorState": {
                        "DriverFront": True,
                        "DriverRear": True,
                        "PassengerFront": True,
                        "PassengerRear": True,
                        "TrunkFront": True,
                        "TrunkRear": True,
                    }
                },
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    # Assert the entities get new values
    for entity_id in (
        "cover.test_windows",
        "cover.test_charge_port_door",
        "cover.test_frunk",
        "cover.test_trunk",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=f"{entity_id}-open")

    # Send some alternative data with everything unknown
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.FD_WINDOW: "WindowStateUnknown",
                Signal.FP_WINDOW: "WindowStateUnknown",
                Signal.RD_WINDOW: "WindowStateUnknown",
                Signal.RP_WINDOW: "WindowStateUnknown",
                Signal.CHARGE_PORT_DOOR_OPEN: None,
                Signal.DOOR_STATE: {
                    "DoorState": {
                        "DriverFront": None,
                        "DriverRear": None,
                        "PassengerFront": None,
                        "PassengerRear": None,
                        "TrunkFront": None,
                        "TrunkRear": None,
                    }
                },
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    # Assert the entities get UNKNOWN values
    for entity_id in (
        "cover.test_windows",
        "cover.test_charge_port_door",
        "cover.test_frunk",
        "cover.test_trunk",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=f"{entity_id}-unknown")
