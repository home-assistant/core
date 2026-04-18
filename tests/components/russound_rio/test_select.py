"""Tests for the Russound RIO select platform."""

from unittest.mock import AsyncMock, patch

from aiorussound.rio.models import PartyMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.russound_rio.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_setting_value(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting value."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.backyard_party_mode",
            ATTR_OPTION: "master",
        },
        blocking=True,
    )
    mock_russound_client.controllers[1].zones[1].set_party_mode.assert_called_once_with(
        PartyMode.MASTER
    )
    mock_russound_client.controllers[1].zones[1].set_party_mode.reset_mock()
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.backyard_party_mode",
            ATTR_OPTION: "off",
        },
        blocking=True,
    )
    mock_russound_client.controllers[1].zones[1].set_party_mode.assert_called_once_with(
        PartyMode.OFF
    )
