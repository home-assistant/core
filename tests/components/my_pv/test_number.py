"""Test the my-PV number platform."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_my_pv_client")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of a water heater."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_number_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a number is unavailable when not connected."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.connected = False

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("number.my_pv_ac_elwa_2_temperature")
    assert state.state == STATE_UNAVAILABLE


async def test_number_unavailable_setup_value_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a number is unavailable when setup value is None."""

    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)

        mock_my_pv_client.get_setup_value = Mock(return_value=None)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("number.my_pv_ac_elwa_2_temperature")
    assert state.state == STATE_UNAVAILABLE
