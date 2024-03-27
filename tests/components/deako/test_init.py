"""Tests for the deako component init."""
from unittest.mock import patch

from pydeako.deako import FindDevicesTimeout
import pytest

from homeassistant.components.deako import async_setup_entry
from homeassistant.components.deako.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_config_no_config(hass: HomeAssistant) -> None:
    """Component setup succeeds when there are no config entry for the domain."""
    assert await async_setup_component(hass, DOMAIN, {})


@pytest.mark.asyncio
async def test_deako_async_setup_entry(
    hass: HomeAssistant,
    mock_async_zeroconf: None,
    mock_config_entry: MockConfigEntry,
    pydeako_deako_mock,
    pydeako_discoverer_mock,
) -> None:
    """Test successful setup entry."""
    pydeako_deako_mock.return_value.get_devices.return_value = [1, 2]

    mock_config_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as async_forward_entry_setups_mock:
        ret = await async_setup_entry(hass, mock_config_entry)

        pydeako_deako_mock.assert_called_once_with(
            pydeako_discoverer_mock.return_value.get_address
        )
        pydeako_deako_mock.return_value.get_devices.assert_called_once()
        async_forward_entry_setups_mock.assert_called_once()

        assert (
            hass.data[DOMAIN][mock_config_entry.entry_id]
            == pydeako_deako_mock.return_value
        )

        assert ret


@pytest.mark.asyncio
async def test_deako_async_setup_entry_device_list_timeout(
    hass: HomeAssistant,
    mock_async_zeroconf: None,
    mock_config_entry: MockConfigEntry,
    pydeako_deako_mock,
    pydeako_discoverer_mock,
) -> None:
    """Test async_setup_entry raises ConfigEntryNotReady when pydeako raises FindDevicesTimeout."""

    mock_config_entry.add_to_hass(hass)

    pydeako_deako_mock.return_value.find_devices.side_effect = FindDevicesTimeout()

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, mock_config_entry)

        pydeako_deako_mock.assert_called_once_with(
            pydeako_discoverer_mock.return_value.get_address
        )
        pydeako_deako_mock.return_value.connect.assert_called_once()
        pydeako_deako_mock.return_value.find_devices.assert_called_once()
        pydeako_deako_mock.return_value.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_deako_async_setup_entry_device_list_empty(
    hass: HomeAssistant,
    mock_async_zeroconf: None,
    mock_config_entry: MockConfigEntry,
    pydeako_deako_mock,
    pydeako_discoverer_mock,
) -> None:
    """Test async_setup_entry raises ConfigEntryNotReady when pydeako raises returns zero devices after discovery."""

    mock_config_entry.add_to_hass(hass)

    pydeako_deako_mock.return_value.get_devices.return_value = []

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, mock_config_entry)

        pydeako_deako_mock.assert_called_once_with(
            pydeako_discoverer_mock.return_value.get_address
        )
        pydeako_deako_mock.return_value.connect.assert_called_once()
        pydeako_deako_mock.return_value.find_devices.assert_called_once()
        pydeako_deako_mock.return_value.get_devices.assert_called_once()
        pydeako_deako_mock.return_value.disconnect.assert_called_once()
