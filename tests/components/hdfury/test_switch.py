"""Tests for the HDFury switch platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from hdfury import HDFuryError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test HDFury switch entities."""

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method", "service"),
    [
        ("switch.hdfury_vrroom_02_cec", "set_cec", SERVICE_TURN_ON),
        ("switch.hdfury_vrroom_02_cec", "set_cec", SERVICE_TURN_OFF),
        (
            "switch.hdfury_vrroom_02_auto_switch_inputs",
            "set_auto_switch_inputs",
            SERVICE_TURN_ON,
        ),
        (
            "switch.hdfury_vrroom_02_auto_switch_inputs",
            "set_auto_switch_inputs",
            SERVICE_TURN_OFF,
        ),
        ("switch.hdfury_vrroom_02_oled_display", "set_oled", SERVICE_TURN_ON),
        ("switch.hdfury_vrroom_02_oled_display", "set_oled", SERVICE_TURN_OFF),
        ("switch.hdfury_vrroom_02_tx0_force_5v", "set_tx0_force_5v", SERVICE_TURN_ON),
        ("switch.hdfury_vrroom_02_tx0_force_5v", "set_tx0_force_5v", SERVICE_TURN_OFF),
        ("switch.hdfury_vrroom_02_tx1_force_5v", "set_tx1_force_5v", SERVICE_TURN_ON),
        ("switch.hdfury_vrroom_02_tx1_force_5v", "set_tx1_force_5v", SERVICE_TURN_OFF),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    method: str,
    service: str,
) -> None:
    """Test turning device switches on and off."""

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    getattr(mock_hdfury_client, method).assert_awaited_once()


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_TURN_ON, "set_auto_switch_inputs"),
        (SERVICE_TURN_OFF, "set_auto_switch_inputs"),
    ],
)
async def test_switch_turn_error(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Test switch turn on/off raises HomeAssistantError on API failure."""

    getattr(mock_hdfury_client, method).side_effect = HDFuryError()

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with HDFury device",
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "switch.hdfury_vrroom_02_auto_switch_inputs"},
            blocking=True,
        )


async def test_switch_entities_unavailable_on_error(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test API error causes entities to become unavailable."""

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])

    mock_hdfury_client.get_info.side_effect = HDFuryError()

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("switch.hdfury_vrroom_02_auto_switch_inputs").state
        == STATE_UNAVAILABLE
    )
