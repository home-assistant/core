"""Test config entry migration for Nederlandse Spoorwegen integration."""

from homeassistant.components.nederlandse_spoorwegen import async_migrate_entry
from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_migrate_entry_version_1_minor_1(hass: HomeAssistant) -> None:
    """Test migration from version 1.0 to 1.1."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_key"},
        version=1,
        minor_version=0,
    )
    config_entry.add_to_hass(hass)

    # Test migration
    result = await async_migrate_entry(hass, config_entry)

    assert result is True
    assert config_entry.version == 1
    assert config_entry.minor_version == 1


async def test_migrate_entry_already_current_version(hass: HomeAssistant) -> None:
    """Test migration when already at current version."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_key"},
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    # Test migration
    result = await async_migrate_entry(hass, config_entry)

    assert result is True
    assert config_entry.version == 1
    assert config_entry.minor_version == 1


async def test_migrate_entry_future_version(hass: HomeAssistant) -> None:
    """Test migration fails for future versions (downgrade scenario)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_key"},
        version=2,
        minor_version=0,
    )
    config_entry.add_to_hass(hass)

    # Test migration fails for future version
    result = await async_migrate_entry(hass, config_entry)

    assert result is False
