"""Tests for the Instructure integration."""
import pytest

from homeassistant.components.instructure.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_integration")


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful unload of entry."""
    # print_hass(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


# def print_hass(hass: HomeAssistant):
#     """Print HASS object."""
#     print_dict_separately(hass.data)

#     print("\n state")
#     print(hass.state)

#     print("\n states")
#     print(hass.states)

#     print("\n data instructure")
#     print(hass.data["instructure"])

#     print("\n data entity_registry")
#     print(hass.data["entity_registry"])

#     print("\n data component")
#     print(hass.data["components"]["instructure"])


# def print_entry(mock_config_entry: MockConfigEntry):
#     """Print Entry object."""
#     print(f"\n Domain: {mock_config_entry.domain}")
#     print(f"\n Entry ID: {mock_config_entry.entry_id}")
#     print(f"\n State: {mock_config_entry.state}")
#     print("\n Entry data:")
#     print(mock_config_entry.data)
#     print("\n Entry options:")
#     print(mock_config_entry.options)


# def print_dict_separately(data_dict):
#     """Print hass data ."""
#     for key, value in data_dict.items():
#         print(f"{key}: {value}")
