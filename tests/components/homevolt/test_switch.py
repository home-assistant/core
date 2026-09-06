"""Tests for the Homevolt switch platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from homevolt import (
    HomevoltAuthenticationError,
    HomevoltCommandOutcomeUnknownError,
    HomevoltCommandRejectedError,
    HomevoltCommandVerificationError,
    HomevoltConnectionError,
    HomevoltError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homevolt.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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
    """Test switch on/off calls client and updates state."""
    client_method = getattr(mock_homevolt_client, client_method_name)

    async def update_local_mode(*args: object, **kwargs: object) -> None:
        mock_homevolt_client.local_mode_enabled = service == SERVICE_TURN_ON

    client_method.side_effect = update_local_mode
    mock_homevolt_client.update_info.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: switch_entity_id},
        blocking=True,
    )

    client_method.assert_called_once()
    mock_homevolt_client.update_info.assert_not_awaited()
    state = hass.states.get(switch_entity_id)
    assert state is not None
    assert state == snapshot(name=f"state-after-{service}")


@pytest.mark.parametrize(
    (
        "exception",
        "expected_exception",
        "translation_key",
        "placeholders",
        "refresh_count",
    ),
    [
        pytest.param(
            HomevoltAuthenticationError("auth failed"),
            ConfigEntryAuthFailed,
            "auth_failed",
            None,
            0,
            id="authentication",
        ),
        pytest.param(
            HomevoltConnectionError("connection failed"),
            HomeAssistantError,
            "communication_error",
            {"error": "connection failed"},
            0,
            id="connection",
        ),
        pytest.param(
            HomevoltCommandRejectedError("invalid command"),
            HomeAssistantError,
            "command_rejected",
            {"error": "invalid command"},
            0,
            id="rejected",
        ),
        pytest.param(
            HomevoltCommandVerificationError("state mismatch"),
            HomeAssistantError,
            "command_verification_failed",
            {"error": "state mismatch"},
            1,
            id="verification",
        ),
        pytest.param(
            HomevoltCommandOutcomeUnknownError("read-back failed"),
            HomeAssistantError,
            "command_outcome_unknown",
            {"error": "read-back failed"},
            1,
            id="outcome-unknown",
        ),
        pytest.param(
            HomevoltError("unknown error"),
            HomeAssistantError,
            "unknown_error",
            {"error": "unknown error"},
            0,
            id="homevolt",
        ),
    ],
)
@pytest.mark.parametrize(
    ("service", "client_method_name"),
    [
        pytest.param(SERVICE_TURN_ON, "enable_local_mode", id="turn-on"),
        pytest.param(SERVICE_TURN_OFF, "disable_local_mode", id="turn-off"),
    ],
)
async def test_switch_turn_on_off_exception_handler(
    hass: HomeAssistant,
    switch_entity_id: str,
    service: str,
    client_method_name: str,
    mock_homevolt_client: MagicMock,
    exception: HomevoltError,
    expected_exception: type[HomeAssistantError],
    translation_key: str,
    placeholders: dict[str, str] | None,
    refresh_count: int,
) -> None:
    """Test translated command errors and refreshes through switch actions."""
    getattr(mock_homevolt_client, client_method_name).side_effect = exception
    mock_homevolt_client.update_info.reset_mock()

    with pytest.raises(expected_exception) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: switch_entity_id},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == placeholders
    assert mock_homevolt_client.update_info.await_count == refresh_count


async def test_commands_preserve_telemetry_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_homevolt_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test repeated schedule writes do not postpone the regular telemetry poll."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.homevolt.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_homevolt_client.update_info.assert_awaited_once()
    mock_homevolt_client.update_info.reset_mock()
    command_interval = SCAN_INTERVAL / 3

    for _ in range(2):
        freezer.tick(command_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "switch.homevolt_ems_local_mode",
            },
            blocking=True,
        )
        mock_homevolt_client.update_info.assert_not_awaited()

    freezer.tick(command_interval.total_seconds() + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_homevolt_client.update_info.assert_awaited_once()
