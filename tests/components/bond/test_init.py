"""Tests for the Bond module."""
from aiohttp import ClientConnectionError
from bond_api import DeviceType

from homeassistant.components.bond.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .common import (
    patch_bond_device,
    patch_bond_device_ids,
    patch_bond_device_properties,
    patch_bond_device_state,
    patch_bond_version,
    patch_setup_entry,
    setup_bond_entity,
)

from tests.common import MockConfigEntry


async def test_async_setup_no_domain_config(hass: HomeAssistant):
    """Test setup without configuration is noop."""
    result = await async_setup_component(hass, DOMAIN, {})

    assert result is True


async def test_async_setup_raises_entry_not_ready(hass: HomeAssistant):
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "some host", CONF_ACCESS_TOKEN: "test-token"},
    )
    config_entry.add_to_hass(hass)

    with patch_bond_version(side_effect=ClientConnectionError()):
        await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state == ENTRY_STATE_SETUP_RETRY


async def test_async_setup_entry_sets_up_hub_and_supported_domains(hass: HomeAssistant):
    """Test that configuring entry sets up cover domain."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "some host", CONF_ACCESS_TOKEN: "test-token"},
    )

    with patch_bond_version(
        return_value={
            "bondid": "test-bond-id",
            "target": "test-model",
            "fw_ver": "test-version",
        }
    ):
        with patch_setup_entry(
            "cover"
        ) as mock_cover_async_setup_entry, patch_setup_entry(
            "fan"
        ) as mock_fan_async_setup_entry, patch_setup_entry(
            "light"
        ) as mock_light_async_setup_entry, patch_setup_entry(
            "switch"
        ) as mock_switch_async_setup_entry:
            result = await setup_bond_entity(hass, config_entry, patch_device_ids=True)
            assert result is True
            await hass.async_block_till_done()

    assert config_entry.entry_id in hass.data[DOMAIN]
    assert config_entry.state == ENTRY_STATE_LOADED
    assert config_entry.unique_id == "test-bond-id"

    # verify hub device is registered correctly
    device_registry = await dr.async_get_registry(hass)
    hub = device_registry.async_get_device(identifiers={(DOMAIN, "test-bond-id")})
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
        domain=DOMAIN,
        data={CONF_HOST: "some host", CONF_ACCESS_TOKEN: "test-token"},
    )

    result = await setup_bond_entity(
        hass,
        config_entry,
        patch_version=True,
        patch_device_ids=True,
        patch_platforms=True,
    )
    assert result is True
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.entry_id not in hass.data[DOMAIN]
    assert config_entry.state == ENTRY_STATE_NOT_LOADED


async def test_old_identifiers_are_removed(hass: HomeAssistant):
    """Test we remove the old non-unique identifiers."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "some host", CONF_ACCESS_TOKEN: "test-token"},
    )

    old_identifers = (DOMAIN, "device_id")
    new_identifiers = (DOMAIN, "test-bond-id", "device_id")
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={old_identifers},
        manufacturer="any",
        name="old",
    )

    config_entry.add_to_hass(hass)

    with patch_bond_version(
        return_value={
            "bondid": "test-bond-id",
            "target": "test-model",
            "fw_ver": "test-version",
        }
    ), patch_bond_device_ids(
        return_value=["bond-device-id", "device_id"]
    ), patch_bond_device(
        return_value={
            "name": "test1",
            "type": DeviceType.GENERIC_DEVICE,
        }
    ), patch_bond_device_properties(
        return_value={}
    ), patch_bond_device_state(
        return_value={}
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
        await hass.async_block_till_done()

    assert config_entry.entry_id in hass.data[DOMAIN]
    assert config_entry.state == ENTRY_STATE_LOADED
    assert config_entry.unique_id == "test-bond-id"

    # verify the device info is cleaned up
    assert device_registry.async_get_device(identifiers={old_identifers}) is None
    assert device_registry.async_get_device(identifiers={new_identifiers}) is not None
