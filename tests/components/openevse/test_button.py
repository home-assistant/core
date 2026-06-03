"""Tests for the OpenEVSE button platform."""

from unittest.mock import MagicMock, patch

from aiohttp import ContentTypeError, ServerTimeoutError
from openevsehttp.exceptions import (
    AuthenticationError,
    ParseJSONError,
    UnsupportedFeature,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.openevse.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
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
    """Test the button entities."""
    with patch("homeassistant.components.openevse.PLATFORMS", [Platform.BUTTON]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method_name"),
    [
        pytest.param(
            "button.openevse_mock_config_restart_wi_fi",
            "restart_wifi",
            id="restart_wifi",
        ),
        pytest.param(
            "button.openevse_mock_config_restart_evse",
            "restart_evse",
            id="restart_evse",
        ),
    ],
)
async def test_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
    entity_id: str,
    method_name: str,
) -> None:
    """Test pressing the button."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    getattr(mock_charger, method_name).assert_called_once()


@pytest.mark.parametrize(
    ("raised", "expected", "translation_key", "translation_placeholders"),
    [
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
async def test_press_raises(
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

    mock_charger.restart_wifi.side_effect = raised

    with pytest.raises(expected) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.openevse_mock_config_restart_wi_fi",
            },
            blocking=True,
        )

    assert isinstance(exc_info.value, HomeAssistantError)
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_placeholders == translation_placeholders
