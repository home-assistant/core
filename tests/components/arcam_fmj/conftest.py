"""Tests for the arcam_fmj component."""

from collections.abc import AsyncGenerator
from unittest.mock import Mock, patch

from arcam.fmj.client import Client
from arcam.fmj.state import State
import pytest

from homeassistant.components.arcam_fmj.const import DEFAULT_NAME
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_HOST = "127.0.0.1"
MOCK_PORT = 50000
MOCK_TURN_ON = {
    "service": "switch.turn_on",
    "data": {"entity_id": "switch.test"},
}
MOCK_ENTITY_ID = "media_player.arcam_fmj_127_0_0_1"
MOCK_UUID = "456789abcdef"
MOCK_UDN = f"uuid:01234567-89ab-cdef-0123-{MOCK_UUID}"
MOCK_NAME = f"{DEFAULT_NAME} ({MOCK_HOST})"
MOCK_CONFIG_ENTRY = {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT}


@pytest.fixture(name="client")
def client_fixture() -> Mock:
    """Get a mocked client."""
    client = Mock(Client)
    client.host = MOCK_HOST
    client.port = MOCK_PORT
    return client


@pytest.fixture(name="state_1")
def state_1_fixture(client: Mock) -> State:
    """Get a mocked state."""
    state = Mock(State)
    state.client = client
    state.zn = 1
    state.get_power.return_value = True
    state.get_volume.return_value = 0.0
    state.get_source.return_value = None
    state.get_source_list.return_value = []
    state.get_incoming_audio_format.return_value = (None, None)
    state.get_incoming_video_parameters.return_value = None
    state.get_incoming_audio_sample_rate.return_value = 0
    state.get_mute.return_value = None
    state.get_decode_modes.return_value = []
    state.get_decode_mode.return_value = None
    return state


@pytest.fixture(name="state_2")
def state_2_fixture(client: Mock) -> State:
    """Get a mocked state."""
    state = Mock(State)
    state.client = client
    state.zn = 2
    state.get_power.return_value = True
    state.get_volume.return_value = 0.0
    state.get_source.return_value = None
    state.get_source_list.return_value = []
    state.get_incoming_audio_format.return_value = (None, None)
    state.get_incoming_video_parameters.return_value = None
    state.get_incoming_audio_sample_rate.return_value = 0
    state.get_mute.return_value = None
    state.get_decode_modes.return_value = []
    state.get_decode_mode.return_value = None
    return state


@pytest.fixture(name="mock_config_entry")
def mock_config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Get a mock config entry."""
    config_entry = MockConfigEntry(
        domain="arcam_fmj",
        data=MOCK_CONFIG_ENTRY,
        title=MOCK_NAME,
        unique_id=MOCK_UUID,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="player_setup")
async def player_setup_fixture(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state_1: State,
    state_2: State,
    client: Mock,
) -> AsyncGenerator[None]:
    """Get standard player."""

    def state_mock(cli, zone):
        if zone == 1:
            return state_1
        if zone == 2:
            return state_2
        raise ValueError(f"Unknown player zone: {zone}")

    async def _mock_run_client(hass: HomeAssistant, runtime_data, interval):
        coordinators = runtime_data.coordinators

        def _notify_data_updated() -> None:
            for coordinator in coordinators.values():
                coordinator.async_notify_data_updated()

        client.notify_data_updated = _notify_data_updated

        for coordinator in coordinators.values():
            coordinator.async_notify_connected()

    await async_setup_component(hass, "homeassistant", {})

    with (
        patch("homeassistant.components.arcam_fmj.Client", return_value=client),
        patch(
            "homeassistant.components.arcam_fmj.coordinator.State",
            side_effect=state_mock,
        ),
        patch(
            "homeassistant.components.arcam_fmj._run_client",
            side_effect=_mock_run_client,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield
