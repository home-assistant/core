"""Tests for the HDFury number platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from hdfury import HDFuryError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_number_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test HDFury number entities."""

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("number.hdfury_vrroom_02_oled_fade_timer", "set_oled_fade"),
        ("number.hdfury_vrroom_02_restart_timer", "set_reboot_timer"),
    ],
)
async def test_number_set_value(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    method: str,
) -> None:
    """Test setting a device number value."""

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 50},
        blocking=True,
    )

    getattr(mock_hdfury_client, method).assert_awaited_once_with("50")


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("number.hdfury_vrroom_02_oled_fade_timer", "set_oled_fade"),
        ("number.hdfury_vrroom_02_restart_timer", "set_reboot_timer"),
    ],
)
async def test_number_error(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    method: str,
) -> None:
    """Test set number value raises HomeAssistantError on API failure."""

    getattr(mock_hdfury_client, method).side_effect = HDFuryError()

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with HDFury device",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 50},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("number.hdfury_vrroom_02_oled_fade_timer"),
        ("number.hdfury_vrroom_02_restart_timer"),
    ],
)
async def test_number_entities_unavailable_on_error(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
) -> None:
    """Test API error causes entities to become unavailable."""

    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])

    mock_hdfury_client.get_info.side_effect = HDFuryError()

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
