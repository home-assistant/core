"""Test the Eve Online sensor platform."""

from unittest.mock import AsyncMock

import aiohttp
from eveonline import EveOnlineError
from eveonline.models import WalletBalance
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("init_integration")
async def test_sensor_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor states match snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
) -> None:
    """Test that sensors become unavailable when the coordinator fails."""
    mock_eveonline_client.async_get_wallet_balance.side_effect = EveOnlineError(
        "API unavailable"
    )

    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_capsuleer_wallet_balance")
    assert state is not None
    assert state.state == "unavailable"


async def test_sensor_wallet_updated(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that wallet balance updates on coordinator refresh."""

    mock_eveonline_client.async_get_wallet_balance.return_value = WalletBalance(
        balance=9999999.99
    )

    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_capsuleer_wallet_balance")
    assert state is not None
    assert float(state.state) == 9999999.99


async def test_sensor_location_unavailable_when_endpoint_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that the location sensor shows unknown when its endpoint fails."""
    mock_eveonline_client.async_get_character_location.side_effect = (
        aiohttp.ClientError("Connection lost")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_capsuleer_location")
    assert state is not None
    assert state.state == "unknown"


async def test_sensor_ship_unavailable_when_endpoint_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that the ship sensor shows unknown when its endpoint fails."""
    mock_eveonline_client.async_get_character_ship.side_effect = aiohttp.ClientError(
        "Connection lost"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_capsuleer_ship")
    assert state is not None
    assert state.state == "unknown"
