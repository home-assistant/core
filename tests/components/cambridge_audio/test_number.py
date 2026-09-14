"""Tests for the Cambridge Audio number platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.cambridge_audio.PLATFORMS", [Platform.NUMBER]):
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
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 13},
        target={
            ATTR_ENTITY_ID: "number.cambridge_audio_cxnv2_room_correction_intensity"
        },
        blocking=True,
    )

    mock_stream_magic_client.set_room_correction_intensity.assert_called_once_with(13)


async def test_setting_volume_limit(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting volume limit."""
    mock_stream_magic_client.state.pre_amp_mode = True

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 50},
        target={ATTR_ENTITY_ID: "number.cambridge_audio_cxnv2_volume_limit"},
        blocking=True,
    )

    mock_stream_magic_client.set_volume_limit.assert_called_once_with(50)


async def test_setting_volume_limit_unavailable_when_pre_amp_mode_off(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test volume limit is unavailable when pre-amp mode is off."""

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.cambridge_audio_cxnv2_volume_limit")

    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 50},
        target={ATTR_ENTITY_ID: "number.cambridge_audio_cxnv2_volume_limit"},
        blocking=True,
    )

    mock_stream_magic_client.set_volume_limit.assert_not_called()
