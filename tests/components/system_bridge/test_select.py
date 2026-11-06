"""Tests for the System Bridge select platform."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.audio_control import AudioControl
from systembridgeconnector.models.fixtures.modules.audio import FIXTURE_AUDIO
from systembridgeconnector.models.modules import Module
from systembridgeconnector.models.response import Response
from systembridgeconnector.models.system_control import PowerProfileRequest

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_REQUEST_ID

ENTITY_ID = "select.hostname_audio_input"
POWER_PROFILE_ENTITY_ID = "select.hostname_power_profile"


@pytest.fixture(autouse=True)
def select_only() -> Generator[None]:
    """Enable only the select platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.SELECT],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_select_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the select platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_power_profile(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
) -> None:
    """Test picking a power profile switches to it."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: POWER_PROFILE_ENTITY_ID, ATTR_OPTION: "performance"},
        blocking=True,
    )

    mock_websocket_client.set_power_profile.assert_awaited_once_with(
        PowerProfileRequest(profile="performance")
    )


@pytest.mark.usefixtures("mock_version")
async def test_power_profile_added_later(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test the select is added once the system reports a power profile."""
    modules_data = mock_websocket_client.get_data.return_value
    system = modules_data.system
    mock_websocket_client.get_data.return_value = replace(
        modules_data, system=replace(system, power_profile=None, power_profiles=[])
    )
    mock_websocket_client.listen.side_effect = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(POWER_PROFILE_ENTITY_ID) is None

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_handle_module(Module.SYSTEM, system)
    await hass.async_block_till_done()

    assert (state := hass.states.get(POWER_PROFILE_ENTITY_ID))
    assert state.state == "balanced"

    await coordinator.async_handle_module(
        Module.SYSTEM, replace(system, power_profile=None)
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(POWER_PROFILE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("response", "message"),
    [
        pytest.param(
            Response(
                id=FIXTURE_REQUEST_ID,
                type=EventType.ERROR,
                message="power-profiles-daemon is not running",
                data={},
            ),
            "System Bridge couldn't make the change: power-profiles-daemon is not running",
            id="error",
        ),
        pytest.param(
            ConnectionClosedException,
            "A connection error occurred",
            id="connection_closed",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_power_profile_error(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    response: Response | type[Exception],
    message: str,
) -> None:
    """Test a failed switch raises."""
    mock_websocket_client.set_power_profile.side_effect = [response]

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: POWER_PROFILE_ENTITY_ID, ATTR_OPTION: "performance"},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_select_default_input(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test picking an input makes it the default."""
    coordinator = mock_config_entry.runtime_data
    microphone = FIXTURE_AUDIO.inputs[0]
    headset = replace(microphone, id="headset", name="Headset", default=False)

    await coordinator.async_handle_module(
        Module.AUDIO, replace(FIXTURE_AUDIO, inputs=[microphone, headset])
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "Headset"},
        blocking=True,
    )

    mock_websocket_client.audio_control.assert_awaited_once_with(
        AudioControl(id="headset", default=True)
    )


@pytest.mark.usefixtures("init_integration")
async def test_select_duplicate_names(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test inputs with the same name get their ID added, and can each be picked."""
    coordinator = mock_config_entry.runtime_data
    microphone = FIXTURE_AUDIO.inputs[0]
    twin = replace(microphone, id="twin", default=False)

    await coordinator.async_handle_module(
        Module.AUDIO, replace(FIXTURE_AUDIO, inputs=[microphone, twin])
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_OPTIONS] == [
        f"{microphone.name} ({microphone.id})",
        f"{microphone.name} (twin)",
    ]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: f"{microphone.name} (twin)"},
        blocking=True,
    )

    mock_websocket_client.audio_control.assert_awaited_once_with(
        AudioControl(id="twin", default=True)
    )


@pytest.mark.parametrize(
    "others",
    [
        pytest.param([("twin", ""), ("lookalike", " (twin)")], id="added_id"),
        pytest.param(
            [("b", ""), ("c", " (a)"), ("d", " (a) (a)")],
            id="added_id_twice",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_name_matching_added_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    others: list[tuple[str, str]],
) -> None:
    """Test a name matching another input's name with its ID added stays unique."""
    coordinator = mock_config_entry.runtime_data
    microphone = replace(FIXTURE_AUDIO.inputs[0], id="a")
    inputs = [
        microphone,
        *(
            replace(
                microphone, id=item_id, name=f"{microphone.name}{suffix}", default=False
            )
            for item_id, suffix in others
        ),
    ]

    await coordinator.async_handle_module(
        Module.AUDIO, replace(FIXTURE_AUDIO, inputs=inputs)
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert len(set(state.attributes[ATTR_OPTIONS])) == len(inputs)


@pytest.mark.usefixtures("init_integration")
async def test_select_available_without_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a new default can be picked when no input is the default."""
    coordinator = mock_config_entry.runtime_data

    await coordinator.async_handle_module(
        Module.AUDIO,
        replace(
            FIXTURE_AUDIO,
            inputs=[replace(device, default=False) for device in FIXTURE_AUDIO.inputs],
        ),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    await coordinator.async_handle_module(
        Module.AUDIO, replace(FIXTURE_AUDIO, inputs=[])
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
