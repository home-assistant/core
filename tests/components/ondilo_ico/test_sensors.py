"""Test Ondilo ICO integration sensors."""

from unittest.mock import MagicMock

from ondilo import OndiloError

from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType, JsonObjectType

from . import setup_integration

from tests.common import MockConfigEntry


async def test_can_get_pools_when_no_error(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    config_entry: MockConfigEntry,
    two_pools: JsonArrayType,
    ico_details1: JsonObjectType,
    ico_details2: JsonObjectType,
    last_measures: JsonArrayType,
) -> None:
    """Test that I can get all pools data when no error."""
    await setup_integration(hass, config_entry, mock_ondilo_client)

    # All sensors were created
    assert len(hass.states.async_all()) == 14

    # Check 2 of the sensors.
    assert hass.states.get("sensor.pool_1_temperature").state == "19"
    assert hass.states.get("sensor.pool_2_rssi").state == "60"


async def test_no_ico_attached(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    config_entry: MockConfigEntry,
    two_pools: JsonArrayType,
    pool1: JsonObjectType,
    ico_details2: JsonObjectType,
    last_measures: JsonArrayType,
) -> None:
    """Test if an ICO is not attached to a pool, then no sensor is created."""
    # Only one pool, but no ICO attached
    mock_ondilo_client.get_pools.return_value = pool1
    mock_ondilo_client.get_ICO_details.side_effect = None
    mock_ondilo_client.get_ICO_details.return_value = None
    await setup_integration(hass, config_entry, mock_ondilo_client)

    # No sensor should be created
    assert len(hass.states.async_all()) == 0
    # We should not have tried to retrieve pool measures
    mock_ondilo_client.get_last_pool_measures.assert_not_called()

    # Some test with 2 pools, one of them has no ICO
    mock_ondilo_client.get_pools.return_value = two_pools
    mock_ondilo_client.get_ICO_details.side_effect = [None, ico_details2]

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    # Only the second pool is created
    assert len(hass.states.async_all()) == 7
    assert hass.states.get("sensor.pool_1_temperature") is None
    assert hass.states.get("sensor.pool_2_rssi").state == next(
        str(item["value"]) for item in last_measures if item["data_type"] == "rssi"
    )


async def test_error_retrieving_ico(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    config_entry: MockConfigEntry,
    pool1: JsonObjectType,
) -> None:
    """Test if there's an error retrieving ICO data, then no sensor is created."""
    mock_ondilo_client.get_pools.return_value = pool1
    mock_ondilo_client.get_ICO_details.side_effect = OndiloError(400, "error")

    await setup_integration(hass, config_entry, mock_ondilo_client)

    # No sensor should be created
    assert len(hass.states.async_all()) == 0


async def test_error_retrieving_measures(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    config_entry: MockConfigEntry,
    pool1: JsonObjectType,
    ico_details1: JsonObjectType,
) -> None:
    """Test if there's an error retrieving measures of ICO, then no sensor is created."""
    mock_ondilo_client.get_pools.return_value = pool1
    mock_ondilo_client.get_ICO_details.return_value = ico_details1
    mock_ondilo_client.get_last_pool_measures.side_effect = OndiloError(400, "error")

    await setup_integration(hass, config_entry, mock_ondilo_client)

    # No sensor should be created
    assert len(hass.states.async_all()) == 0
