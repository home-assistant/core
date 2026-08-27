"""Test the Teslemetry cover platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.const import ClosureState
from tesla_fleet_api.exceptions import InvalidCommand
from teslemetry_stream import Signal

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import (
    COMMAND_ERRORS,
    COMMAND_OK,
    METADATA,
    METADATA_NOSCOPE,
    PRODUCTS,
    PRODUCTS_CYBERTRUCK,
    VEHICLE_DATA_ALT,
    VEHICLE_DATA_NONE,
)

VIN = PRODUCTS_CYBERTRUCK["response"][0]["vin"]


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
async def test_cover_none(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that polling covers report unknown when coordinator data is null."""

    mock_vehicle_data.return_value = VEHICLE_DATA_NONE
    entry = await setup_platform(hass, [Platform.COVER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cover_noscope(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_metadata: AsyncMock,
) -> None:
    """Tests that the cover entities are correct without scopes."""

    mock_metadata.return_value = METADATA_NOSCOPE
    entry = await setup_platform(hass, [Platform.COVER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    ("products", "expected"),
    [
        pytest.param(PRODUCTS, False, id="model3"),
        pytest.param(PRODUCTS_CYBERTRUCK, True, id="cybertruck"),
    ],
)
async def test_cover_tonneau_model_gate(
    hass: HomeAssistant,
    mock_products: AsyncMock,
    products: dict,
    expected: bool,
) -> None:
    """Tests that the tonneau cover is only created for a Cybertruck."""

    mock_products.return_value = products
    await setup_platform(hass, [Platform.COVER])
    assert (hass.states.get("cover.test_tonneau") is not None) == expected


@pytest.mark.parametrize(
    ("firmware", "expected"),
    [
        pytest.param("2024.44.24", False, id="below_threshold"),
        pytest.param("2024.44.25", True, id="at_threshold"),
    ],
)
async def test_cover_tonneau_firmware_gate(
    hass: HomeAssistant,
    mock_products: AsyncMock,
    mock_metadata: AsyncMock,
    firmware: str,
    expected: bool,
) -> None:
    """Tests that the tonneau cover is only created on firmware >= 2024.44.25."""

    mock_products.return_value = PRODUCTS_CYBERTRUCK
    metadata = deepcopy(METADATA)
    metadata["vehicles"][VIN]["firmware"] = firmware
    mock_metadata.return_value = metadata

    await setup_platform(hass, [Platform.COVER])
    assert (hass.states.get("cover.test_tonneau") is not None) == expected


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cover_cybertruck(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_products: AsyncMock,
) -> None:
    """Tests that the cover entities are correct for a Cybertruck."""

    mock_products.return_value = PRODUCTS_CYBERTRUCK
    entry = await setup_platform(hass, [Platform.COVER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cover_tonneau_services(
    hass: HomeAssistant,
    mock_products: AsyncMock,
) -> None:
    """Tests that the tonneau cover commands work for a Cybertruck."""

    mock_products.return_value = PRODUCTS_CYBERTRUCK
    await setup_platform(hass, [Platform.COVER])

    entity_id = "cover.test_tonneau"
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.closure",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        call.assert_called_once_with(tonneau=ClosureState.OPEN)
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
        call.assert_called_once_with(tonneau=ClosureState.STOP)
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
        call.assert_called_once_with(tonneau=ClosureState.CLOSE)
        state = hass.states.get(entity_id)
        assert state
        assert state.state == CoverState.CLOSED


async def test_cover_tonneau_streaming(
    hass: HomeAssistant,
    mock_products: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the tonneau cover reflects streamed position and percent."""

    mock_products.return_value = PRODUCTS_CYBERTRUCK
    await setup_platform(hass, [Platform.COVER])

    entity_id = "cover.test_tonneau"
    vin = PRODUCTS_CYBERTRUCK["response"][0]["vin"]

    mock_add_listener.send(
        {
            "vin": vin,
            "data": {
                Signal.TONNEAU_POSITION: "TonneauPositionStateClosed",
                Signal.TONNEAU_OPEN_PERCENT: 0,
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    mock_add_listener.send(
        {
            "vin": vin,
            "data": {
                Signal.TONNEAU_POSITION: "TonneauPositionStateFullyOpen",
                Signal.TONNEAU_OPEN_PERCENT: 100,
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cover_services(
    hass: HomeAssistant,
    mock_legacy: AsyncMock,
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_legacy")
@pytest.mark.parametrize("response", COMMAND_ERRORS)
async def test_cover_command_errors(hass: HomeAssistant, response: dict) -> None:
    """Tests that vehicle command failures raise HomeAssistantError."""

    await setup_platform(hass, [Platform.COVER])

    with (
        patch(
            "tesla_fleet_api.teslemetry.Vehicle.window_control",
            return_value=response,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: ["cover.test_windows"]},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_legacy")
async def test_cover_command_exception(hass: HomeAssistant) -> None:
    """Tests that a command SDK exception raises HomeAssistantError."""

    await setup_platform(hass, [Platform.COVER])

    with (
        patch(
            "tesla_fleet_api.teslemetry.Vehicle.window_control",
            side_effect=InvalidCommand,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: ["cover.test_windows"]},
            blocking=True,
        )


async def test_cover_streaming(
    hass: HomeAssistant,
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

    # Assert the entities restored their values with concrete assertions
    assert hass.states.get("cover.test_windows").state == CoverState.CLOSED
    assert hass.states.get("cover.test_charge_port_door").state == CoverState.CLOSED
    # Frunk and trunk don't get closed state from stream, they show unknown
    assert hass.states.get("cover.test_frunk").state == "unknown"
    assert hass.states.get("cover.test_trunk").state == "unknown"

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

    # Assert the entities get new values with concrete assertions
    assert hass.states.get("cover.test_windows").state == CoverState.OPEN
    # Charge port door doesn't change with CHARGE_PORT_DOOR_OPEN: False
    assert hass.states.get("cover.test_charge_port_door").state == CoverState.CLOSED
    # Frunk and trunk still show unknown (DOOR_STATE doesn't contain trunk state info)
    assert hass.states.get("cover.test_frunk").state == "unknown"
    assert hass.states.get("cover.test_trunk").state == "unknown"

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

    # Assert the entities get values with concrete assertions
    # Windows stay open when unknown because of previous state restoration
    assert hass.states.get("cover.test_windows").state == CoverState.OPEN
    assert hass.states.get("cover.test_charge_port_door").state == "unknown"
    assert hass.states.get("cover.test_frunk").state == "unknown"
    assert hass.states.get("cover.test_trunk").state == "unknown"
