"""Tests for init methods."""

from homeassistant.components.kulersky.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_migrate_entry(
    hass: HomeAssistant,
) -> None:
    """Test migrate config entry from v1 to v2."""

    mock_config_entry_v1 = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="KulerSky",
    )

    mock_config_entry_v1.add_to_hass(hass)

    dev_reg = dr.async_get(hass)
    # Create device registry entries for old integration
    dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry_v1.entry_id,
        identifiers={(DOMAIN, "AA:BB:CC:11:22:33")},
        name="KuLight 1",
    )
    dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry_v1.entry_id,
        identifiers={(DOMAIN, "AA:BB:CC:44:55:66")},
        name="KuLight 2",
    )
    await hass.config_entries.async_setup(mock_config_entry_v1.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_v1.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry_v1.version == 2
    assert mock_config_entry_v1.unique_id == "AA:BB:CC:11:22:33"
    assert mock_config_entry_v1.data == {
        CONF_ADDRESS: "AA:BB:CC:11:22:33",
    }


async def test_migrate_entry_no_devices_found(
    hass: HomeAssistant,
) -> None:
    """Test migrate config entry from v1 to v2."""

    mock_config_entry_v1 = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="KulerSky",
    )

    mock_config_entry_v1.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_v1.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_v1.state is ConfigEntryState.MIGRATION_ERROR
    assert mock_config_entry_v1.version == 1
