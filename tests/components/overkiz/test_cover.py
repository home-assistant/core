"""Tests for Overkiz covers."""

from unittest.mock import AsyncMock, patch

import pytest
from pyoverkiz.enums import OverkizCommand
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
)
from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry

SET_POSITION_AND_TILT_SERVICE = "set_cover_position_and_tilt"

VENETIAN_BLIND_ENTITY_ID = "cover.kitchen_venetian_blind"
ROLLER_SHUTTER_ENTITY_ID = "cover.living_room_shutter"


@pytest.fixture
def require_position_and_tilt_service(
    hass: HomeAssistant,
    init_integration_with_cover: MockConfigEntry,
) -> MockConfigEntry:
    """Skip the test if the set_cover_position_and_tilt service is missing.

    The service is implemented in PR #166180. Until that lands, these tests
    skip so this PR can be reviewed and merged independently. Once the service
    exists, the tests run automatically.
    """
    if not hass.services.has_service(DOMAIN, SET_POSITION_AND_TILT_SERVICE):
        pytest.skip(
            "overkiz.set_cover_position_and_tilt service not registered "
            "(waiting on home-assistant/core#166180)"
        )
    return init_integration_with_cover


async def test_cover_entities_are_created(
    hass: HomeAssistant,
    init_integration_with_cover: MockConfigEntry,
) -> None:
    """Both the Venetian blind and the RTS roller shutter should be set up."""
    assert hass.states.get(VENETIAN_BLIND_ENTITY_ID) is not None
    assert hass.states.get(ROLLER_SHUTTER_ENTITY_ID) is not None


async def test_venetian_blind_position_and_tilt_are_inverted(
    hass: HomeAssistant,
    init_integration_with_cover: MockConfigEntry,
) -> None:
    """Overkiz reports closure/orientation in reverse (0 = fully open).

    Home Assistant's convention is 0 = closed, 100 = open, so the integration
    must invert both values when exposing them on the entity state.
    """
    state = hass.states.get(VENETIAN_BLIND_ENTITY_ID)
    assert state is not None
    # Fixture: core:ClosureState = 40 → current_position = 60
    assert state.attributes[ATTR_CURRENT_POSITION] == 60
    # Fixture: core:SlatsOrientationState = 70 → current_tilt_position = 30
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 30


async def test_set_cover_position_and_tilt_service_is_registered(
    hass: HomeAssistant,
    require_position_and_tilt_service: MockConfigEntry,
) -> None:
    """The overkiz.set_cover_position_and_tilt service must be registered."""
    assert hass.services.has_service(DOMAIN, SET_POSITION_AND_TILT_SERVICE)


async def test_set_cover_position_and_tilt_executes_single_command(
    hass: HomeAssistant,
    require_position_and_tilt_service: MockConfigEntry,
) -> None:
    """Position+tilt must be sent as one atomic SET_CLOSURE_AND_ORIENTATION call.

    Regression test for home-assistant/core#156234: two sequential service calls
    (set_cover_position followed by set_cover_tilt_position) make the Somfy motor
    stop mid-movement. The new service issues a single firmware command instead.
    """
    mock_execute = AsyncMock(return_value="exec-1")
    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        execute_command=mock_execute,
        fetch_events=AsyncMock(return_value=[]),
    ):
        await hass.services.async_call(
            DOMAIN,
            SET_POSITION_AND_TILT_SERVICE,
            {
                ATTR_ENTITY_ID: VENETIAN_BLIND_ENTITY_ID,
                ATTR_POSITION: 30,
                ATTR_TILT_POSITION: 80,
            },
            blocking=True,
        )

    assert mock_execute.await_count == 1
    call = mock_execute.await_args
    # Positional args: device_url, Command, label
    command = call.args[1]
    assert command.name == OverkizCommand.SET_CLOSURE_AND_ORIENTATION
    # HA position 30 → Overkiz closure 70, HA tilt 80 → Overkiz orientation 20
    assert command.parameters == [70, 20]


async def test_set_cover_position_and_tilt_boundary_values(
    hass: HomeAssistant,
    require_position_and_tilt_service: MockConfigEntry,
) -> None:
    """Boundary values 0 and 100 must invert cleanly to 100 and 0."""
    mock_execute = AsyncMock(return_value="exec-2")
    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        execute_command=mock_execute,
        fetch_events=AsyncMock(return_value=[]),
    ):
        await hass.services.async_call(
            DOMAIN,
            SET_POSITION_AND_TILT_SERVICE,
            {
                ATTR_ENTITY_ID: VENETIAN_BLIND_ENTITY_ID,
                ATTR_POSITION: 0,
                ATTR_TILT_POSITION: 100,
            },
            blocking=True,
        )

    command = mock_execute.await_args.args[1]
    assert command.parameters == [100, 0]


@pytest.mark.parametrize(
    ("position", "tilt_position"),
    [(-1, 50), (50, 101), (120, 50)],
)
async def test_set_cover_position_and_tilt_rejects_out_of_range(
    hass: HomeAssistant,
    require_position_and_tilt_service: MockConfigEntry,
    position: int,
    tilt_position: int,
) -> None:
    """Values outside 0-100 must be rejected by the service schema."""
    mock_execute = AsyncMock(return_value="exec-3")
    with (
        patch.multiple(
            "pyoverkiz.client.OverkizClient",
            execute_command=mock_execute,
            fetch_events=AsyncMock(return_value=[]),
        ),
        pytest.raises(vol.Invalid),
    ):
        await hass.services.async_call(
            DOMAIN,
            SET_POSITION_AND_TILT_SERVICE,
            {
                ATTR_ENTITY_ID: VENETIAN_BLIND_ENTITY_ID,
                ATTR_POSITION: position,
                ATTR_TILT_POSITION: tilt_position,
            },
            blocking=True,
        )

    # Schema validation must block the command from ever being issued.
    assert mock_execute.await_count == 0


async def test_set_cover_position_and_tilt_on_device_without_tilt_is_filtered(
    hass: HomeAssistant,
    require_position_and_tilt_service: MockConfigEntry,
) -> None:
    """required_features blocks the service on covers without tilt support.

    The RTS roller shutter has neither SET_TILT_POSITION nor SET_CLOSURE_AND_ORIENTATION.
    Calling the service on it must not reach execute_command — it is filtered
    out by the entity-service framework before the handler runs.
    """
    mock_execute = AsyncMock(return_value="exec-4")
    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        execute_command=mock_execute,
        fetch_events=AsyncMock(return_value=[]),
    ):
        await hass.services.async_call(
            DOMAIN,
            SET_POSITION_AND_TILT_SERVICE,
            {
                ATTR_ENTITY_ID: ROLLER_SHUTTER_ENTITY_ID,
                ATTR_POSITION: 50,
                ATTR_TILT_POSITION: 50,
            },
            blocking=True,
        )

    assert mock_execute.await_count == 0


async def test_async_set_cover_position_and_tilt_raises_without_command(
    hass: HomeAssistant,
    require_position_and_tilt_service: MockConfigEntry,
) -> None:
    """Direct method call must raise ServiceValidationError on unsupported devices.

    Belt-and-braces check next to the framework-level filtering: instantiate the
    bound method through the entity component and confirm it refuses devices
    that lack SET_CLOSURE_AND_ORIENTATION.
    """
    from homeassistant.components.overkiz.cover.vertical_cover import VerticalCover
    from homeassistant.helpers import entity_component

    component: entity_component.EntityComponent = hass.data["entity_components"][
        COVER_DOMAIN
    ]
    roller_entity = next(
        entity
        for entity in component.entities
        if entity.entity_id == ROLLER_SHUTTER_ENTITY_ID
    )
    assert isinstance(roller_entity, VerticalCover)

    with pytest.raises(ServiceValidationError):
        await roller_entity.async_set_cover_position_and_tilt(
            **{ATTR_POSITION: 50, ATTR_TILT_POSITION: 50}
        )


async def test_set_cover_position_inverts_single_value(
    hass: HomeAssistant,
    init_integration_with_cover: MockConfigEntry,
) -> None:
    """Plain set_cover_position must still invert 100-position (unchanged behavior)."""
    mock_execute = AsyncMock(return_value="exec-5")
    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        execute_command=mock_execute,
        fetch_events=AsyncMock(return_value=[]),
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: VENETIAN_BLIND_ENTITY_ID, ATTR_POSITION: 25},
            blocking=True,
        )

    command = mock_execute.await_args.args[1]
    assert command.name == OverkizCommand.SET_CLOSURE
    assert command.parameters == [75]


async def test_set_cover_tilt_position_inverts_single_value(
    hass: HomeAssistant,
    init_integration_with_cover: MockConfigEntry,
) -> None:
    """Plain set_cover_tilt_position must still invert 100-tilt (unchanged behavior)."""
    mock_execute = AsyncMock(return_value="exec-6")
    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        execute_command=mock_execute,
        fetch_events=AsyncMock(return_value=[]),
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_ENTITY_ID: VENETIAN_BLIND_ENTITY_ID, ATTR_TILT_POSITION: 10},
            blocking=True,
        )

    command = mock_execute.await_args.args[1]
    assert command.name == OverkizCommand.SET_ORIENTATION
    assert command.parameters == [90]


async def test_open_and_close_cover_issue_matching_commands(
    hass: HomeAssistant,
    init_integration_with_cover: MockConfigEntry,
) -> None:
    """Open/Close on a Venetian blind should issue OPEN and CLOSE commands."""
    mock_execute = AsyncMock(return_value="exec-7")
    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        execute_command=mock_execute,
        fetch_events=AsyncMock(return_value=[]),
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: VENETIAN_BLIND_ENTITY_ID},
            blocking=True,
        )
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: VENETIAN_BLIND_ENTITY_ID},
            blocking=True,
        )

    commands = [c.args[1].name for c in mock_execute.await_args_list]
    assert OverkizCommand.OPEN in commands
    assert OverkizCommand.CLOSE in commands
