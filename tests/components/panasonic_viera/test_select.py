"""Test the Panasonic Viera picture mode select."""

from datetime import timedelta
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from panasonic_viera import SOAPError

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
)
from homeassistant.components.panasonic_viera.const import (
    ATTR_DEVICE_INFO,
    ATTR_UDN,
    DOMAIN,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import (
    MOCK_CONFIG_DATA,
    MOCK_DEVICE_INFO,
    MOCK_INPUTS,
    MOCK_PICTURE_MODES,
)

from tests.common import MockConfigEntry, async_fire_time_changed

SELECT_ENTITY_ID = "select.panasonic_viera_tv_picture_mode"
MEDIA_PLAYER_ENTITY_ID = "media_player.panasonic_viera_tv"
REMOTE_ENTITY_ID = "remote.panasonic_viera_tv"


def _create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a config entry for an already known TV."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA, ATTR_DEVICE_INFO: MOCK_DEVICE_INFO},
    )
    entry.add_to_hass(hass)
    return entry


def _disable_other_entities(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Pre-register the media player and remote entities as disabled."""
    registry = er.async_get(hass)
    for domain in ("media_player", "remote"):
        registry.async_get_or_create(
            domain,
            DOMAIN,
            MOCK_DEVICE_INFO[ATTR_UDN],
            config_entry=entry,
            disabled_by=er.RegistryEntryDisabler.USER,
        )


async def _advance(hass: HomeAssistant, seconds: int = 30) -> None:
    """Let the coordinator poll the TV."""
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_picture_mode_select(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test the picture modes are exposed and can be selected."""
    state = hass.states.get(SELECT_ENTITY_ID)
    assert state.state == MOCK_PICTURE_MODES[1]
    assert state.attributes[ATTR_OPTIONS] == MOCK_PICTURE_MODES

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: "Cinema"},
        blocking=True,
    )

    mock_remote.set_picture_mode.assert_called_once_with("Cinema")
    assert hass.states.get(SELECT_ENTITY_ID).state == "Cinema"


async def test_picture_mode_select_follows_tv_state(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test the select tracks the TV and is unavailable while it is off."""
    mock_remote.get_picture_mode.return_value = "Dynamic"
    await _advance(hass)
    assert hass.states.get(SELECT_ENTITY_ID).state == "Dynamic"

    mock_remote.get_mute = Mock(side_effect=HTTPError(None, 400, None, None, None))
    await _advance(hass, 60)
    assert hass.states.get(MEDIA_PLAYER_ENTITY_ID).state == STATE_OFF
    assert hass.states.get(SELECT_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_picture_mode_unsupported(hass: HomeAssistant, mock_remote: Mock) -> None:
    """Test a TV without picture mode support gets no select and is probed once."""
    mock_remote.get_picture_mode = Mock(side_effect=SOAPError)
    entry = _create_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(SELECT_ENTITY_ID) is None
    assert hass.states.get(MEDIA_PLAYER_ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]
    mock_remote.get_picture_mode.assert_called_once()
    await _advance(hass)
    mock_remote.get_picture_mode.assert_called_once()
    mock_remote.list_picture_modes.assert_not_called()


async def test_picture_mode_and_input_unsupported(
    hass: HomeAssistant, mock_remote: Mock
) -> None:
    """Test a TV without any PAC support keeps the basic controls."""
    mock_remote.get_picture_mode = Mock(side_effect=SOAPError)
    mock_remote.list_inputs = Mock(side_effect=SOAPError)
    entry = _create_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(SELECT_ENTITY_ID) is None
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE
    assert ATTR_INPUT_SOURCE_LIST not in state.attributes


async def test_picture_mode_failure_keeps_inputs(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test a failing picture mode query does not affect the inputs."""
    mock_remote.get_picture_mode = Mock(side_effect=SOAPError)
    await _advance(hass)

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == MOCK_INPUTS
    assert state.attributes[ATTR_INPUT_SOURCE] == MOCK_INPUTS[0]
    assert hass.states.get(SELECT_ENTITY_ID).state == "unknown"


async def test_input_failure_keeps_picture_mode(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test a failing input query does not prevent the picture mode update."""
    mock_remote.get_input = Mock(side_effect=SOAPError)
    mock_remote.get_picture_mode.return_value = "Dynamic"
    await _advance(hass)

    assert hass.states.get(SELECT_ENTITY_ID).state == "Dynamic"


async def test_picture_mode_discovered_after_offline_startup(
    hass: HomeAssistant, mock_remote: Mock
) -> None:
    """Test the select is added once a TV that was off during setup answers."""
    entry = _create_entry(hass)

    with patch(
        "homeassistant.components.panasonic_viera.RemoteControl",
        side_effect=URLError("offline"),
    ) as mock_control:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert hass.states.get(SELECT_ENTITY_ID) is None
        assert hass.states.get(MEDIA_PLAYER_ENTITY_ID).state == STATE_UNAVAILABLE

        await _advance(hass)
        assert hass.states.get(SELECT_ENTITY_ID) is None

        mock_control.side_effect = None
        mock_control.return_value = mock_remote
        await _advance(hass, 60)
        await _advance(hass, 120)

    state = hass.states.get(SELECT_ENTITY_ID)
    assert state.state == MOCK_PICTURE_MODES[1]
    assert state.attributes[ATTR_OPTIONS] == MOCK_PICTURE_MODES
    assert hass.states.get(MEDIA_PLAYER_ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]


async def test_picture_mode_discovered_with_disabled_entities(
    hass: HomeAssistant, mock_remote: Mock
) -> None:
    """Test discovery does not depend on the media player or remote entities."""
    entry = _create_entry(hass)
    _disable_other_entities(hass, entry)

    with patch(
        "homeassistant.components.panasonic_viera.RemoteControl",
        side_effect=URLError("offline"),
    ) as mock_control:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get(MEDIA_PLAYER_ENTITY_ID) is None
        assert hass.states.get(REMOTE_ENTITY_ID) is None
        assert hass.states.get(SELECT_ENTITY_ID) is None

        mock_control.side_effect = None
        mock_control.return_value = mock_remote
        await _advance(hass, 60)
        await _advance(hass, 120)

    assert hass.states.get(SELECT_ENTITY_ID).state == MOCK_PICTURE_MODES[1]

    mock_remote.get_picture_mode.return_value = "Dynamic"
    await _advance(hass, 180)
    assert hass.states.get(SELECT_ENTITY_ID).state == "Dynamic"


async def test_polling_stops_once_unsupported_and_nothing_listens(
    hass: HomeAssistant, mock_remote: Mock
) -> None:
    """Test the discovery listener stops polling when there is nothing to expose."""
    mock_remote.get_picture_mode = Mock(side_effect=SOAPError)
    entry = _create_entry(hass)
    _disable_other_entities(hass, entry)

    with patch(
        "homeassistant.components.panasonic_viera.RemoteControl",
        side_effect=URLError("offline"),
    ) as mock_control:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_control.side_effect = None
        mock_control.return_value = mock_remote
        await _advance(hass, 60)
        await _advance(hass, 120)
        mock_remote.get_picture_mode.assert_called_once()

        calls = mock_control.call_count
        mock_remote.get_mute.reset_mock()
        await _advance(hass, 180)
        await _advance(hass, 240)

    assert hass.states.get(SELECT_ENTITY_ID) is None
    mock_remote.get_mute.assert_not_called()
    assert mock_control.call_count == calls


async def test_unload_stops_discovery(hass: HomeAssistant, mock_remote: Mock) -> None:
    """Test unloading while the TV is still offline leaves nothing polling."""
    entry = _create_entry(hass)

    with patch(
        "homeassistant.components.panasonic_viera.RemoteControl",
        side_effect=URLError("offline"),
    ) as mock_control:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _advance(hass)
        calls = mock_control.call_count
        assert calls > 1

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED

        await _advance(hass, 60)
        await _advance(hass, 120)
        assert mock_control.call_count == calls


async def test_unload_with_select(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test unloading removes the entities and stops polling the TV."""
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(SELECT_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_remote.get_picture_mode.reset_mock()
    await _advance(hass, 60)
    mock_remote.get_picture_mode.assert_not_called()


async def test_no_select_without_device_info(
    hass: HomeAssistant, mock_remote: Mock
) -> None:
    """Test no select is created for a TV that has no unique identifier."""
    mock_remote.get_device_info = Mock(return_value=None)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG_DATA, ATTR_DEVICE_INFO: None},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids(SELECT_DOMAIN) == []
