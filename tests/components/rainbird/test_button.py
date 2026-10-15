"""Tests for rainbird button platform."""

from http import HTTPStatus
import json

from pyrainbird import encryption
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import (
    ACK_ECHO,
    CONFIG_ENTRY_DATA_OLD_FORMAT,
    PASSWORD,
    mock_response,
    mock_response_error,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse

PROGRAM_A_ENTITY_ID = "button.rain_bird_controller_run_pgm_a"


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BUTTON]


@pytest.fixture(autouse=True)
async def setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Fixture to setup the config entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("program", "unique_id"),
    [
        pytest.param("a", "4c:a1:61:00:11:22-program-0", id="program_a"),
        pytest.param("b", "4c:a1:61:00:11:22-program-1", id="program_b"),
        pytest.param("c", "4c:a1:61:00:11:22-program-2", id="program_c"),
    ],
)
async def test_program_buttons(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    program: str,
    unique_id: str,
) -> None:
    """Test a button is created for each program supported by the ESP-TM2."""
    entity_id = f"button.rain_bird_controller_run_pgm_{program}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert (
        state.attributes["friendly_name"]
        == f"Rain Bird Controller Run PGM {program.upper()}"
    )

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.unique_id == unique_id


async def test_program_count(hass: HomeAssistant) -> None:
    """Test no buttons exist beyond the model's program limit."""
    assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == 3


@pytest.mark.parametrize(
    ("program", "command"),
    [
        pytest.param("a", "3800", id="program_a"),
        pytest.param("b", "3801", id="program_b"),
        pytest.param("c", "3802", id="program_c"),
    ],
)
async def test_press(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
    program: str,
    command: str,
) -> None:
    """Test pressing a button starts its program."""
    aioclient_mock.mock_calls.clear()
    responses.append(mock_response(ACK_ECHO))

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: f"button.rain_bird_controller_run_pgm_{program}"},
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1
    payload = encryption.decrypt(aioclient_mock.mock_calls[0][2], PASSWORD)
    request = json.loads(payload.decode().rstrip("\x00"))
    assert request["params"]["data"] == command


@pytest.mark.parametrize(
    ("status", "expected_msg"),
    [
        pytest.param(
            HTTPStatus.SERVICE_UNAVAILABLE, "Rain Bird device is busy", id="busy"
        ),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR, "Rain Bird device failure", id="failure"
        ),
    ],
)
async def test_press_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    responses: list[AiohttpClientMockResponse],
    status: HTTPStatus,
    expected_msg: str,
) -> None:
    """Test an error while talking to the device."""
    aioclient_mock.mock_calls.clear()
    responses.append(mock_response_error(status=status))

    with pytest.raises(HomeAssistantError, match=expected_msg):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: PROGRAM_A_ENTITY_ID},
            blocking=True,
        )

    assert len(aioclient_mock.mock_calls) == 1


@pytest.mark.parametrize(
    ("config_entry_data", "config_entry_unique_id", "setup_config_entry"),
    [(CONFIG_ENTRY_DATA_OLD_FORMAT, None, None)],
)
async def test_no_unique_id(
    hass: HomeAssistant,
    responses: list[AiohttpClientMockResponse],
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test button platform with no unique id."""
    # Failure to migrate config entry to a unique id
    responses.insert(1, mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE))

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(PROGRAM_A_ENTITY_ID)
    assert state is not None
    assert state.attributes["friendly_name"] == "Rain Bird Controller Run PGM A"
    assert not entity_registry.async_get(PROGRAM_A_ENTITY_ID)
