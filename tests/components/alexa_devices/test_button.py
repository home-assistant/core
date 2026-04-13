"""Test Alexa Devices button entities."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from . import setup_integration
from .const import TEST_USERNAME

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""

    mock_amazon_devices_client.routines = ["Test Routine"]

    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_pressing_routine_button(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test routine run button."""

    mock_amazon_devices_client.routines = ["Test Routine"]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: f"button.{slugify(TEST_USERNAME)}_test_routine"},
        blocking=True,
    )
    mock_amazon_devices_client.call_routine.assert_called_once()
