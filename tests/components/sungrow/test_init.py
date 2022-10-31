"""Test the Sungrow Solar Energy sensor."""
from unittest.mock import patch

from homeassistant.components.sungrow.config_flow import CannotConnect
from homeassistant.components.sungrow.const import DAILY_POWER_YIELDS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MockClient, create_entry, inverter_data


async def test_setup(hass: HomeAssistant) -> None:
    """Test unload."""
    entry = create_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_device_info(hass: HomeAssistant) -> None:
    """Test device info."""
    entry = create_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    device_registry = dr.async_get(hass)
    await hass.async_block_till_done()
    device = device_registry.async_get_device({(DOMAIN, entry.entry_id)})
    await hass.async_block_till_done()

    assert device is not None
    assert device.configuration_url == "http://1.1.1.1"
    assert device.entry_type is None
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.manufacturer == "Sungrow"
    assert device.name == "Mock Title"


async def test_device_data(hass: HomeAssistant) -> None:
    """Test device data."""
    with patch(
        "homeassistant.components.sungrow.SungrowData.update",
        return_value=inverter_data,
    ) as mock_client:
        entry = create_entry(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.data[DOMAIN][entry.entry_id].async_refresh()

        sensor = hass.states.get("sensor.mock_title_yield_day")

        assert sensor.state == str(inverter_data[DAILY_POWER_YIELDS])

        mock_client.assert_called_once()


async def test_device_data_not_available(hass: HomeAssistant) -> None:
    """Test device data not available."""
    with patch(
        "homeassistant.components.sungrow.SungrowData.update",
        side_effect=CannotConnect,
    ) as mock_client:
        entry = create_entry(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.data[DOMAIN][entry.entry_id].async_refresh()

        assert hass.data[DOMAIN][entry.entry_id].data is None

        mock_client.assert_called_once()


async def test_data_update(hass: HomeAssistant) -> None:
    """Test the update call."""
    with patch(
        "homeassistant.components.sungrow.Client", return_value=MockClient
    ) as mock_client:
        entry = create_entry(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.data[DOMAIN][entry.entry_id].data is None

        await hass.data[DOMAIN][entry.entry_id].async_refresh()

        assert hass.data[DOMAIN][entry.entry_id].last_update_success is True

        sensor = hass.states.get("sensor.mock_title_yield_day")

        assert sensor.state == str(inverter_data[DAILY_POWER_YIELDS])

        mock_client.assert_called_once()
