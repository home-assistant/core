"""Tests for the Homevolt switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homevolt import HomevoltAuthenticationError, HomevoltConnectionError, HomevoltError
import pytest

from homeassistant.components.homevolt.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "init_integration"
)

SWITCH_UNIQUE_ID = "40580137858664_local_mode"


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms to load only the switch platform."""
    return [Platform.SWITCH]


def _switch_entity_id(entity_registry: er.EntityRegistry) -> str:
    """Return the switch entity id."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, SWITCH_UNIQUE_ID
    )
    assert entity_id is not None
    return entity_id


async def test_switch_state_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test switch state when local mode is disabled."""
    mock_homevolt_client.local_mode_enabled = False
    entity_id = _switch_entity_id(entity_registry)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF


async def test_switch_state_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test switch state when local mode is enabled."""
    mock_homevolt_client.local_mode_enabled = True
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    entity_id = _switch_entity_id(entity_registry)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("service", "client_method_name", "expected_state"),
    [
        (SERVICE_TURN_ON, "enable_local_mode", STATE_ON),
        (SERVICE_TURN_OFF, "disable_local_mode", STATE_OFF),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_homevolt_client: MagicMock,
    service: str,
    client_method_name: str,
    expected_state: str,
) -> None:
    """Test turning the switch on or off calls client, refreshes coordinator, and updates state."""
    client_method = getattr(mock_homevolt_client, client_method_name)

    async def update_local_mode(*args: object, **kwargs: object) -> None:
        mock_homevolt_client.local_mode_enabled = service == SERVICE_TURN_ON

    client_method.side_effect = update_local_mode

    entity_id = _switch_entity_id(entity_registry)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    client_method.assert_called_once()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "client_method_name", "exception", "expected_exception"),
    [
        (
            SERVICE_TURN_ON,
            "enable_local_mode",
            HomevoltAuthenticationError("auth failed"),
            ConfigEntryAuthFailed,
        ),
        (
            SERVICE_TURN_ON,
            "enable_local_mode",
            HomevoltConnectionError("connection failed"),
            HomeAssistantError,
        ),
        (
            SERVICE_TURN_ON,
            "enable_local_mode",
            HomevoltError("unknown error"),
            HomeAssistantError,
        ),
        (
            SERVICE_TURN_OFF,
            "disable_local_mode",
            HomevoltAuthenticationError("auth failed"),
            ConfigEntryAuthFailed,
        ),
        (
            SERVICE_TURN_OFF,
            "disable_local_mode",
            HomevoltConnectionError("connection failed"),
            HomeAssistantError,
        ),
        (
            SERVICE_TURN_OFF,
            "disable_local_mode",
            HomevoltError("unknown error"),
            HomeAssistantError,
        ),
    ],
)
async def test_switch_turn_on_off_exception_handler(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_homevolt_client: MagicMock,
    service: str,
    client_method_name: str,
    exception: Exception,
    expected_exception: type[Exception],
) -> None:
    """Test homevolt_exception_handler raises correct exception on turn_on/turn_off."""
    getattr(mock_homevolt_client, client_method_name).side_effect = exception
    entity_id = _switch_entity_id(entity_registry)

    with pytest.raises(expected_exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
