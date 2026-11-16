"""Tests for the Cambridge Audio select platform."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.const import CommonServiceArgument, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.cambridge_audio.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_setting_value(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting value."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            CommonServiceArgument.ENTITY_ID: "select.cambridge_audio_cxnv2_display_brightness",
            SelectServiceArgument.OPTION: "dim",
        },
        blocking=True,
    )
    mock_stream_magic_client.set_display_brightness.assert_called_once_with("dim")

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            CommonServiceArgument.ENTITY_ID: "select.cambridge_audio_cxnv2_audio_output",
            SelectServiceArgument.OPTION: "Speaker A",
        },
        blocking=True,
    )
    mock_stream_magic_client.set_audio_output.assert_called_once_with("speaker_a")
