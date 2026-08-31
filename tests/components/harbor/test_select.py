"""Test the Harbor selects."""

from typing import Any
from unittest.mock import AsyncMock, patch

from harbor import HarborCommandError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import SETTINGS_TOPIC, emit_message

from tests.common import MockConfigEntry, snapshot_platform

NIGHT_MODE_ENTITY = "select.harbor_camera_1234567890_night_mode"

SELECT_SETTINGS_PAYLOAD: dict[str, Any] = {
    "settings": {"preference_video_night_mode": "auto"},
}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Harbor selects report their current option."""
    with patch("homeassistant.components.harbor.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await emit_message(mock_mqtt_client, SETTINGS_TOPIC, SELECT_SETTINGS_PAYLOAD)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "option",
    [
        pytest.param("auto", id="auto"),
        pytest.param("on", id="on"),
        pytest.param("off", id="off"),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
    option: str,
) -> None:
    """Test selecting an option passes the device value to the library."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: NIGHT_MODE_ENTITY, ATTR_OPTION: option},
        blocking=True,
    )

    mock_mqtt_client.return_value.set_night_mode.assert_awaited_once_with(option)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            HarborCommandError("command", {"error": "rejected"}), id="command"
        ),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(ConnectionError, id="connection"),
    ],
)
async def test_select_option_failure_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
    error: Exception | type[Exception],
) -> None:
    """Test a failed camera command surfaces as a HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    mock_mqtt_client.return_value.set_night_mode.side_effect = error

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: NIGHT_MODE_ENTITY, ATTR_OPTION: "off"},
            blocking=True,
        )


async def test_unexpected_option_stays_valid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test a night mode outside the declared options surfaces as unknown.

    The library maps unrecognized enum values onto its own "unknown" member;
    the select treats that as no selection rather than exposing "unknown" as a
    literal option.
    """
    await setup_integration(hass, mock_config_entry)

    await emit_message(mock_mqtt_client, SETTINGS_TOPIC, SELECT_SETTINGS_PAYLOAD)
    await hass.async_block_till_done()
    assert hass.states.get(NIGHT_MODE_ENTITY).state == "auto"

    await emit_message(
        mock_mqtt_client,
        SETTINGS_TOPIC,
        {"settings": {"preference_video_night_mode": "sunset"}},
    )
    await hass.async_block_till_done()
    assert hass.states.get(NIGHT_MODE_ENTITY).state == STATE_UNKNOWN
