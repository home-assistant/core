"""Test the SteamVR Base Station identify button."""

from unittest.mock import AsyncMock

from lighthouse_ble import LighthouseConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

IDENTIFY = "button.lhb_747a9bc5_identify"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the button platform."""
    return [Platform.BUTTON]


async def test_button_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the button entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_identify(hass: HomeAssistant, mock_identify: AsyncMock) -> None:
    """Test pressing the button blinks the LED."""
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: IDENTIFY}, blocking=True
    )
    mock_identify.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_identify_error(hass: HomeAssistant, mock_identify: AsyncMock) -> None:
    """Test a failed identify raises a translated error."""
    mock_identify.side_effect = LighthouseConnectionError("gone")
    with pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: IDENTIFY}, blocking=True
        )
    assert raised.value.translation_key == "cannot_connect"
