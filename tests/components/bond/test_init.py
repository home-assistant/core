"""Tests for the Bond module."""
from homeassistant.components.bond.const import DOMAIN
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .common import setup_bond_entity

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_async_setup_no_domain_config(hass: HomeAssistant):
    """Test setup without configuration is noop."""
    result = await async_setup_component(hass, DOMAIN, {})

    assert result is True


async def test_async_setup_entry_sets_up_hub_and_supported_domains(hass: HomeAssistant):
    """Test that configuring entry sets up cover domain."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "1.1.1.1", CONF_ACCESS_TOKEN: "test-token"},
    )

    with patch(
        "homeassistant.components.bond.cover.async_setup_entry"
    ) as mock_cover_async_setup_entry, patch(
        "homeassistant.components.bond.fan.async_setup_entry"
    ) as mock_fan_async_setup_entry, patch(
        "homeassistant.components.bond.light.async_setup_entry"
    ) as mock_light_async_setup_entry, patch(
        "homeassistant.components.bond.switch.async_setup_entry"
    ) as mock_switch_async_setup_entry:
        result = await setup_bond_entity(
            hass,
            config_entry,
            hub_version={
                "bondid": "test-bond-id",
                "target": "test-model",
                "fw_ver": "test-version",
            },
        )
        assert result is True
        await hass.async_block_till_done()

    assert config_entry.entry_id in hass.data[DOMAIN]
    assert config_entry.state == ENTRY_STATE_LOADED

    # verify hub device is registered correctly
    device_registry = await dr.async_get_registry(hass)
    hub = device_registry.async_get_device(
        identifiers={(DOMAIN, "test-bond-id")}, connections=set()
    )
    assert hub.name == "test-bond-id"
    assert hub.manufacturer == "Olibra"
    assert hub.model == "test-model"
    assert hub.sw_version == "test-version"

    # verify supported domains are setup
    assert len(mock_cover_async_setup_entry.mock_calls) == 1
    assert len(mock_fan_async_setup_entry.mock_calls) == 1
    assert len(mock_light_async_setup_entry.mock_calls) == 1
    assert len(mock_switch_async_setup_entry.mock_calls) == 1


async def test_unload_config_entry(hass: HomeAssistant):
    """Test that configuration entry supports unloading."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "1.1.1.1", CONF_ACCESS_TOKEN: "test-token"},
    )

    with patch("homeassistant.components.bond.cover.async_setup_entry"), patch(
        "homeassistant.components.bond.fan.async_setup_entry"
    ):
        result = await setup_bond_entity(hass, config_entry)
        assert result is True
        await hass.async_block_till_done()

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.entry_id not in hass.data[DOMAIN]
    assert config_entry.state == ENTRY_STATE_NOT_LOADED
