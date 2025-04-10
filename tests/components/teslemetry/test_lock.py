"""Test the Teslemetry lock platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream.const import Signal

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import assert_entities, reload_platform, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA_ALT


async def test_lock(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the lock entities are correct."""

    entry = await setup_platform(hass, [Platform.LOCK])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_lock_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the lock entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    entry = await setup_platform(hass, [Platform.LOCK])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_lock_services(
    hass: HomeAssistant,
) -> None:
    """Tests that the lock services work."""

    await setup_platform(hass, [Platform.LOCK])

    entity_id = "lock.test_lock"

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.door_lock",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == LockState.LOCKED
        call.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.door_unlock",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == LockState.UNLOCKED
        call.assert_called_once()

    entity_id = "lock.test_charge_cable_lock"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.charge_port_door_open",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == LockState.UNLOCKED
        call.assert_called_once()


async def test_lock_streaming(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the lock entities with streaming are correct."""

    entry = await setup_platform(hass, [Platform.LOCK])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.LOCKED: True,
                Signal.CHARGE_PORT_LATCH: "ChargePortLatchEngaged",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    await reload_platform(hass, entry, [Platform.LOCK])

    # Assert the entities restored their values
    for entity_id in (
        "lock.test_lock",
        "lock.test_charge_cable_lock",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=f"{entity_id}-locked")

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.LOCKED: False,
                Signal.CHARGE_PORT_LATCH: "ChargePortLatchDisengaged",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    await reload_platform(hass, entry, [Platform.LOCK])

    # Assert the entities restored their values
    for entity_id in (
        "lock.test_lock",
        "lock.test_charge_cable_lock",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=f"{entity_id}-unlocked")
