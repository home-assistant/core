"""Test qBittorrent integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.qbittorrent.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


@pytest.mark.usefixtures("mock_qbittorrent")
@pytest.mark.parametrize(
    ("configured_url", "web_ui_url"),
    [
        ("http://localhost:8080", "http://localhost:8080"),
        (
            "https://test:test@[2001:db8::1]:9443/qbt/?key=test#fragment",
            "https://[2001:db8::1]:9443/qbt/",
        ),
        ("nas.test:9090/qbt", None),
    ],
)
async def test_configuration_url(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    configured_url: str,
    web_ui_url: str | None,
) -> None:
    """Set the Visit link on the existing service device."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_URL: configured_url}
    )
    identifier = (DOMAIN, mock_config_entry.entry_id)
    existing_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        configuration_url="https://old.example.com",
        entry_type=dr.DeviceEntryType.SERVICE,
        identifiers={identifier},
        manufacturer="QBittorrent",
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        identifier, mock_config_entry.entry_id
    )
    assert device is not None
    assert device.id == existing_device.id
    assert device.configuration_url == web_ui_url
