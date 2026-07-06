"""Tests for the Fumis button entities."""

from unittest.mock import MagicMock

from fumis import FumisConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.fumis.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.parametrize(
    "init_integration", [Platform.BUTTON], indirect=True
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_buttons(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Fumis button entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_sync_clock(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test pressing the sync clock button."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.clou_duo_sync_clock"},
        blocking=True,
    )

    mock_fumis.set_clock.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_sync_clock_error_handling(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test error handling for button press."""
    mock_fumis.set_clock.side_effect = FumisConnectionError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.clou_duo_sync_clock"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "communication_error"
