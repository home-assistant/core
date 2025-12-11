"""pytest tests for initial configuration/loading of powersensor component in Home Assistant.

This module contains unit tests to verify the functionality of the power sensor
component, including setup, migration, and entry management.
"""

import pytest

from homeassistant.components.powersensor import (
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.powersensor.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.loader import (
    DATA_COMPONENTS,
    DATA_INTEGRATIONS,
    DATA_MISSING_PLATFORMS,
    DATA_PRELOAD_PLATFORMS,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

### Fixtures  ###############################################


@pytest.fixture
def hass_data(hass: HomeAssistant):
    """Fixture to provide mock data for the Home Assistant environment."""
    hass.data = {
        DATA_COMPONENTS: {},
        DATA_INTEGRATIONS: {},
        DATA_MISSING_PLATFORMS: {},
        DATA_PRELOAD_PLATFORMS: [],
    }


### Tests ###############################################


async def test_async_setup(hass: HomeAssistant, hass_data) -> None:
    """Test the async setup function for the power sensor component."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


async def test_migrate_entry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the migration of config entries for the power sensor component."""
    updated = False

    def verify_new_entry(config_entry, data, version, minor_version) -> None:
        nonlocal updated
        updated = True
        assert version == PowersensorConfigFlow.VERSION
        assert minor_version == 2
        assert "devices" in data
        assert "roles" in data

    monkeypatch.setattr(hass.config_entries, "async_update_entry", verify_new_entry)

    # Verify old config entry migration
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "0123456789ab": {},  # nothing looks inside this, so cheap out
        },
        entry_id="test",
        version=1,
        minor_version=1,
    )
    assert await async_migrate_entry(hass, old_entry) is True
    assert updated

    # Verify new config entry doesn't migrate
    new_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "0123456789ab": {},  # nothing looks inside this, so cheap out
        },
        entry_id="test",
        version=PowersensorConfigFlow.VERSION + 1,
        minor_version=1,
    )
    updated = False
    assert await async_migrate_entry(hass, new_entry) is False
    assert not updated


async def test_setup_unload_and_reload_entry(
    hass: HomeAssistant, hass_data, def_config_entry
) -> None:
    """Test entry setup and unload."""

    assert await async_setup_entry(hass, def_config_entry)
    assert DOMAIN in hass.data and def_config_entry.entry_id in hass.data[DOMAIN]

    # Unload the entry and verify that the data has been removed
    assert await async_unload_entry(hass, def_config_entry)
    assert def_config_entry.entry_id not in hass.data[DOMAIN]
