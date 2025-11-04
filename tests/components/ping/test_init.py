"""Test init of ping component."""

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("patch_setup")
async def test_config_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test for setup success."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


async def test_device_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test for device migration."""
    config_entry.add_to_hass(hass)

    old_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(HOMEASSISTANT_DOMAIN, config_entry.entry_id)},
    )

    assert config_entry.minor_version == 1

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(config_entry.domain, config_entry.entry_id)},
    )

    assert device is not None
    assert device.id == old_device.id
    assert device.config_entries == {config_entry.entry_id}
    assert config_entry.minor_version == 2
