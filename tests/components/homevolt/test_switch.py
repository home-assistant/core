"""Tests for the Homevolt switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homevolt import HomevoltAuthenticationError, HomevoltConnectionError, HomevoltError
import pytest

from homeassistant.components.homevolt.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "init_integration"
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms to load only the switch platform."""
    return [Platform.SWITCH]


def _switch_entity_id(entity_registry: er.EntityRegistry) -> str:
    """Return the switch entity id."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, "40580137858664_local_mode"
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
    assert state.state == "off"


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
    assert state.state == "on"


@pytest.mark.parametrize(
    ("service", "client_method_name"),
    [
        ("turn_on", "enable_local_mode"),
        ("turn_off", "disable_local_mode"),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_homevolt_client: MagicMock,
    service: str,
    client_method_name: str,
) -> None:
    """Test turning the switch on or off calls client and refreshes coordinator."""
    entity_id = _switch_entity_id(entity_registry)
    with patch(
        "homeassistant.components.homevolt.switch.HomevoltDataUpdateCoordinator.async_request_refresh",
        return_value=None,
    ) as mock_refresh:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    getattr(mock_homevolt_client, client_method_name).assert_called_once()
    mock_refresh.assert_called_once()


@pytest.mark.parametrize(
    ("service", "client_method_name", "exception", "expected_exception"),
    [
        (
            "turn_on",
            "enable_local_mode",
            HomevoltAuthenticationError("auth failed"),
            ConfigEntryAuthFailed,
        ),
        (
            "turn_on",
            "enable_local_mode",
            HomevoltConnectionError("connection failed"),
            HomeAssistantError,
        ),
        (
            "turn_on",
            "enable_local_mode",
            HomevoltError("unknown error"),
            HomeAssistantError,
        ),
        (
            "turn_off",
            "disable_local_mode",
            HomevoltAuthenticationError("auth failed"),
            ConfigEntryAuthFailed,
        ),
        (
            "turn_off",
            "disable_local_mode",
            HomevoltConnectionError("connection failed"),
            HomeAssistantError,
        ),
        (
            "turn_off",
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
