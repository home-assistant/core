"""Tests for Vodafone Station button platform."""

from unittest.mock import AsyncMock, patch

from aiovodafone.exceptions import (
    AlreadyLogged,
    CannotAuthenticate,
    CannotConnect,
    GenericLoginError,
)
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.vodafone_station.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.vodafone_station.PLATFORMS", [Platform.BUTTON]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_pressing_button(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device restart button."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.vodafone_station_m123456789_restart"},
        blocking=True,
    )
    mock_vodafone_station_router.restart_router.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "key", "error"),
    [
        (CannotConnect, "cannot_execute_action", "CannotConnect()"),
        (AlreadyLogged, "cannot_execute_action", "AlreadyLogged()"),
        (GenericLoginError, "cannot_execute_action", "GenericLoginError()"),
        (CannotAuthenticate, "cannot_authenticate", "CannotAuthenticate()"),
    ],
)
async def test_button_fails(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    key: str,
    error: str,
) -> None:
    """Test button action fails."""

    await setup_integration(hass, mock_config_entry)

    mock_vodafone_station_router.restart_router.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.vodafone_station_m123456789_restart"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == key
    assert exc_info.value.translation_placeholders == {"error": error}
