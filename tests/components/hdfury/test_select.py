"""Tests for the HDFury select platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from hdfury import HDFuryError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_select_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test HDFury select entities."""

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_operation_mode(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting operation mode."""

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.hdfury_vrroom_02_operation_mode",
            ATTR_OPTION: "1",
        },
        blocking=True,
    )

    mock_hdfury_client.set_operation_mode.assert_awaited_once_with("1")


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("select.hdfury_vrroom_02_port_select_tx0"),
        ("select.hdfury_vrroom_02_port_select_tx1"),
    ],
)
async def test_select_tx_ports(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test selecting TX ports."""

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: "1",
        },
        blocking=True,
    )

    mock_hdfury_client.set_port_selection.assert_awaited()


async def test_select_operation_mode_error(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test operation mode select raises HomeAssistantError."""

    mock_hdfury_client.set_operation_mode.side_effect = HDFuryError()

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with HDFury device",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.hdfury_vrroom_02_operation_mode",
                ATTR_OPTION: "1",
            },
            blocking=True,
        )


async def test_select_ports_missing_state(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test TX port selection fails when TX state is incomplete."""

    mock_hdfury_client.get_info.return_value = {
        "portseltx0": "0",
        "portseltx1": None,
        "opmode": "0",
    }

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while validating TX states",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.hdfury_vrroom_02_port_select_tx0",
                ATTR_OPTION: "0",
            },
            blocking=True,
        )


async def test_select_entities_unavailable_on_error(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test API error causes entities to become unavailable."""

    await setup_integration(hass, mock_config_entry, [Platform.SELECT])

    mock_hdfury_client.get_info.side_effect = HDFuryError()

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("select.hdfury_vrroom_02_port_select_tx0").state
        == STATE_UNAVAILABLE
    )
