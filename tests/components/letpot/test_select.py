"""Test select entities for the LetPot integration."""

from unittest.mock import MagicMock, patch

from letpot.exceptions import LetPotConnectionException, LetPotException
from letpot.models import LightMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("device_type", ["LPH62", "LPH31"])
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_type: str,
) -> None:
    """Test switch entities."""
    with patch("homeassistant.components.letpot.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("device_type", ["LPH31"])
async def test_set_select(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
    device_type: str,
) -> None:
    """Test select entity set to value."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.garden_light_brightness",
            ATTR_OPTION: "high",
        },
        blocking=True,
    )

    mock_device_client.set_light_brightness.assert_awaited_once_with(
        f"{device_type}ABCD", 1000
    )


@pytest.mark.parametrize(
    ("exception", "user_error"),
    [
        (
            LetPotConnectionException("Connection failed"),
            "An error occurred while communicating with the LetPot device: Connection failed",
        ),
        (
            LetPotException("Random thing failed"),
            "An unknown error occurred while communicating with the LetPot device: Random thing failed",
        ),
    ],
)
async def test_select_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
    exception: Exception,
    user_error: str,
) -> None:
    """Test select entity exception handling."""
    await setup_integration(hass, mock_config_entry)

    mock_device_client.set_light_mode.side_effect = exception

    with pytest.raises(HomeAssistantError, match=user_error):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.garden_light_mode",
                ATTR_OPTION: LightMode.FLOWER.name.lower(),
            },
            blocking=True,
        )
