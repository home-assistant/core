"""Tests for the Homevolt switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homevolt import HomevoltAuthenticationError, HomevoltConnectionError, HomevoltError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms to load only the switch platform."""
    return [Platform.SWITCH]


@pytest.fixture
def switch_entity_id(
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> str:
    """Return the switch entity id for the config entry."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )
    assert len(entity_entries) == 1, "Expected exactly one switch entity"
    return entity_entries[0].entity_id


async def test_switch_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch entity and state when local mode is disabled."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("service", "client_method_name"),
    [
        (SERVICE_TURN_ON, "enable_local_mode"),
        (SERVICE_TURN_OFF, "disable_local_mode"),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
    snapshot: SnapshotAssertion,
    switch_entity_id: str,
    service: str,
    client_method_name: str,
) -> None:
    """Test turning the switch on or off calls client, refreshes coordinator, and updates state."""
    client_method = getattr(mock_homevolt_client, client_method_name)

    async def update_local_mode(*args: object, **kwargs: object) -> None:
        mock_homevolt_client.local_mode_enabled = service == SERVICE_TURN_ON

    client_method.side_effect = update_local_mode

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: switch_entity_id},
        blocking=True,
    )

    client_method.assert_called_once()
    state = hass.states.get(switch_entity_id)
    assert state is not None
    assert state == snapshot(name=f"state-after-{service}")


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
    mock_homevolt_client: MagicMock,
    switch_entity_id: str,
    service: str,
    client_method_name: str,
    exception: Exception,
    expected_exception: type[Exception],
) -> None:
    """Test homevolt_exception_handler raises correct exception on turn_on/turn_off."""
    getattr(mock_homevolt_client, client_method_name).side_effect = exception

    with pytest.raises(expected_exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: switch_entity_id},
            blocking=True,
        )
