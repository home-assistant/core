"""Tests for the OpenEVSE select platform."""

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
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
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
    """Test the select entities."""
    with patch("homeassistant.components.openevse.PLATFORMS", [Platform.SELECT]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("option", "method_name", "kwargs"),
    [
        pytest.param(
            "auto",
            "clear_override",
            {},
            id="override_state_auto",
        ),
        pytest.param(
            "active",
            "set_override",
            {"state": "active"},
            id="override_state_active",
        ),
        pytest.param(
            "disabled",
            "set_override",
            {"state": "disabled"},
            id="override_state_disabled",
        ),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
    option: str,
    method_name: str,
    kwargs: dict[str, str],
) -> None:
    """Test selecting an option on the select entities."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.openevse_mock_config_override_state",
            ATTR_OPTION: option,
        },
        blocking=True,
    )
    getattr(mock_charger, method_name).assert_called_once_with(**kwargs)
    state = hass.states.get("select.openevse_mock_config_override_state")
    assert state is not None
    assert state.state == option


@pytest.mark.parametrize(
    ("raised", "expected", "translation_key", "translation_placeholders"),
    [
        pytest.param(
            ValueError("invalid mode"),
            ServiceValidationError,
            "invalid_value",
            {"value": "active"},
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
async def test_select_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
    raised: Exception,
    expected: type[HomeAssistantError],
    translation_key: str,
    translation_placeholders: dict[str, str] | None,
) -> None:
    """Test that errors from the charger are translated to HA exceptions."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_charger.set_override.side_effect = raised

    with pytest.raises(expected) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.openevse_mock_config_override_state",
                ATTR_OPTION: "active",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_placeholders == translation_placeholders


async def test_select_unavailable_when_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test select entity is unavailable when override state is unsupported."""
    mock_charger.get_override_state.return_value = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.openevse_mock_config_override_state")
    assert state is not None
    assert state.state == "unavailable"
