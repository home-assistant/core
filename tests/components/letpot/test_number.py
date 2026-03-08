"""Test number entities for the LetPot integration."""

from unittest.mock import MagicMock, patch

from letpot.exceptions import LetPotConnectionException, LetPotException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number entities."""
    with patch("homeassistant.components.letpot.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
    device_type: str,
) -> None:
    """Test number entity set to value."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.garden_light_brightness",
            ATTR_VALUE: 6,
        },
        blocking=True,
    )

    mock_device_client.set_light_brightness.assert_awaited_once_with(
        f"{device_type}ABCD", 750
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
async def test_number_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_device_client: MagicMock,
    exception: Exception,
    user_error: str,
) -> None:
    """Test number entity exception handling."""
    await setup_integration(hass, mock_config_entry)

    mock_device_client.set_plant_days.side_effect = exception

    with pytest.raises(HomeAssistantError, match=user_error):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.garden_plants_age",
                ATTR_VALUE: 7,
            },
            blocking=True,
        )
