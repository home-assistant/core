"""Tests for the OpenEVSE switch platform."""

from unittest.mock import MagicMock, patch

from aiohttp import ContentTypeError, ServerTimeoutError
from openevsehttp.exceptions import (
    AuthenticationError,
    ParseJSONError,
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
        (
            ValueError("invalid mode"),
            ServiceValidationError,
            "invalid_value",
            {"value": "None"},
        ),
        (
            AuthenticationError("bad creds"),
            ConfigEntryAuthFailed,
            "authentication_error",
            None,
        ),
        (
            TimeoutError("timed out"),
            HomeAssistantError,
            "communication_error",
            None,
        ),
        (
            ServerTimeoutError("timed out"),
            HomeAssistantError,
            "communication_error",
            None,
        ),
        (
            ParseJSONError("bad json"),
            HomeAssistantError,
            "communication_error",
            None,
        ),
        (
            UnsupportedFeature("old firmware"),
            HomeAssistantError,
            "unsupported_feature",
            None,
        ),
        (
            ContentTypeError(MagicMock(), (), message="bad content"),
            HomeAssistantError,
            "communication_error",
            None,
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
    mock_charger.divert_active = None
    mock_charger.shaper_active = True

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.openevse_mock_config_solar_pv_divert")
    assert state is not None
    assert state.state == "unavailable"

    state = hass.states.get("switch.openevse_mock_config_current_shaper")
    assert state is not None
    assert state.state == "on"
