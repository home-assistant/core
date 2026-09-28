"""Tests for the OpenEVSE switch platform."""

from unittest.mock import MagicMock, patch

from aiohttp import ContentTypeError, ServerTimeoutError
from openevsehttp.exceptions import (
    AuthenticationError,
    ParseJSONError,
    UnknownError,
    UnsupportedFeature,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.openevse.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test the switch entities."""
    with patch("homeassistant.components.openevse.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "service", "method_name", "args"),
    [
        pytest.param(
            "switch.openevse_mock_config_solar_pv_divert",
            SERVICE_TURN_ON,
            "set_divert_mode",
            ("eco",),
            id="solar_pv_divert_on",
        ),
        pytest.param(
            "switch.openevse_mock_config_solar_pv_divert",
            SERVICE_TURN_OFF,
            "set_divert_mode",
            ("fast",),
            id="solar_pv_divert_off",
        ),
        pytest.param(
            "switch.openevse_mock_config_current_shaper",
            SERVICE_TURN_ON,
            "set_shaper",
            (True,),
            id="current_shaper_on",
        ),
        pytest.param(
            "switch.openevse_mock_config_current_shaper",
            SERVICE_TURN_OFF,
            "set_shaper",
            (False,),
            id="current_shaper_off",
        ),
        pytest.param(
            "switch.openevse_mock_config_manual_override",
            SERVICE_TURN_ON,
            "toggle_override",
            (),
            id="manual_override_on",
        ),
        pytest.param(
            "switch.openevse_mock_config_manual_override",
            SERVICE_TURN_OFF,
            "toggle_override",
            (),
            id="manual_override_off",
        ),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
    entity_id: str,
    service: str,
    method_name: str,
    args: tuple[object, ...],
) -> None:
    """Test turning on and off the switch entities."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    getattr(mock_charger, method_name).assert_called_once_with(*args)


@pytest.mark.parametrize(
    ("raised", "expected", "translation_key", "translation_placeholders"),
    [
        pytest.param(
            ValueError("invalid mode"),
            ServiceValidationError,
            "invalid_value",
            {"value": "None"},
            id="value_error",
        ),
        pytest.param(
            AuthenticationError("bad creds"),
            ConfigEntryAuthFailed,
            "authentication_error",
            None,
            id="auth_error",
        ),
        pytest.param(
            TimeoutError("timed out"),
            HomeAssistantError,
            "communication_error",
            None,
            id="timeout_error",
        ),
        pytest.param(
            ServerTimeoutError("timed out"),
            HomeAssistantError,
            "communication_error",
            None,
            id="server_timeout_error",
        ),
        pytest.param(
            ParseJSONError("bad json"),
            HomeAssistantError,
            "communication_error",
            None,
            id="parse_json_error",
        ),
        pytest.param(
            UnsupportedFeature("old firmware"),
            HomeAssistantError,
            "unsupported_feature",
            None,
            id="unsupported_feature",
        ),
        pytest.param(
            ContentTypeError(MagicMock(), (), message="bad content"),
            HomeAssistantError,
            "communication_error",
            None,
            id="content_type_error",
        ),
        pytest.param(
            UnknownError("unknown error"),
            HomeAssistantError,
            "communication_error",
            None,
            id="unknown_error",
        ),
        pytest.param(
            RuntimeError("runtime error"),
            HomeAssistantError,
            "communication_error",
            None,
            id="runtime_error",
        ),
    ],
)
async def test_switch_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
    raised: Exception,
    expected: type[Exception],
    translation_key: str,
    translation_placeholders: dict[str, str] | None,
) -> None:
    """Test that errors from the charger are translated to HA exceptions."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_charger.set_shaper.side_effect = raised

    with pytest.raises(expected) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "switch.openevse_mock_config_current_shaper",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_placeholders == translation_placeholders


async def test_switch_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test switch entity availability when is_on_fn returns None."""
    mock_charger.divertmode = None
    mock_charger.shaper_active = True

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.openevse_mock_config_solar_pv_divert")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("switch.openevse_mock_config_current_shaper")
    assert state is not None
    assert state.state == STATE_ON
