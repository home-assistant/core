"""Tests for the HDFury button platform."""

from unittest.mock import AsyncMock

from hdfury import HDFuryError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_button_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test HDFury button entities."""

    await setup_integration(hass, mock_config_entry, [Platform.BUTTON])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("button.hdfury_vrroom_02_restart", "issue_reboot"),
        ("button.hdfury_vrroom_02_issue_hotplug", "issue_hotplug"),
    ],
)
async def test_button_presses(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    method: str,
) -> None:
    """Test pressing the device buttons."""

    await setup_integration(hass, mock_config_entry, [Platform.BUTTON])

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    getattr(mock_hdfury_client, method).assert_awaited_once()


async def test_button_press_error(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test button press raises HomeAssistantError on API failure."""

    mock_hdfury_client.issue_reboot.side_effect = HDFuryError()

    await setup_integration(hass, mock_config_entry, [Platform.BUTTON])

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with HDFury device",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.hdfury_vrroom_02_restart"},
            blocking=True,
        )
