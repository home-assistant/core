"""Tests for the Velbus component initialisation."""

from unittest.mock import patch

import pytest

from homeassistant.components.velbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("controller")
async def test_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Test being able to unload an entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.usefixtures("controller")
async def test_device_identifier_migration(
    hass: HomeAssistant, config_entry: ConfigEntry, device_registry: dr.DeviceRegistry
) -> None:
    """Test being able to unload an entry."""
    original_identifiers = {(DOMAIN, "module_address", "module_serial")}
    target_identifiers = {(DOMAIN, "module_address")}

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers=original_identifiers,  # type: ignore[arg-type]
        name="channel_name",
        manufacturer="Velleman",
        model="module_type_name",
        sw_version="module_sw_version",
    )
    assert device_registry.async_get_device(
        identifiers=original_identifiers  # type: ignore[arg-type]
    )
    assert not device_registry.async_get_device(identifiers=target_identifiers)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device(
        identifiers=original_identifiers  # type: ignore[arg-type]
    )
    device_entry = device_registry.async_get_device(identifiers=target_identifiers)
    assert device_entry
    assert device_entry.name == "channel_name"
    assert device_entry.manufacturer == "Velleman"
    assert device_entry.model == "module_type_name"
    assert device_entry.sw_version == "module_sw_version"


@pytest.mark.usefixtures("controller")
async def test_migrate_config_entry(hass: HomeAssistant) -> None:
    """Test successful migration of entry data."""
    legacy_config = {CONF_NAME: "fake_name", CONF_PORT: "1.2.3.4:5678"}
    entry = MockConfigEntry(domain=DOMAIN, unique_id="my own id", data=legacy_config)
    entry.add_to_hass(hass)

    assert dict(entry.data) == legacy_config
    assert entry.version == 1

    # test in case we do not have a cache
    with patch("os.path.isdir", return_value=True), patch("shutil.rmtree"):
        await hass.config_entries.async_setup(entry.entry_id)
        assert dict(entry.data) == legacy_config
        assert entry.version == 2
