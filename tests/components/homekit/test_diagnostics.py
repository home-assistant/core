"""Test homekit diagnostics."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.homekit.const import (
    CONF_DEVICES,
    CONF_HOMEKIT_MODE,
    DOMAIN,
    HOMEKIT_MODE_ACCESSORY,
)
from homeassistant.const import CONF_NAME, CONF_PORT, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .util import async_init_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_config_entry_not_running(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hk_driver,
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = await async_init_integration(hass)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == {
        "config-entry": {
            "data": {"name": "mock_name", "port": 12345},
            "options": {},
            "title": "Mock Title",
            "version": 1,
        },
        "status": 0,
    }


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_config_entry_running(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    hk_driver,
) -> None:
    """Test generating diagnostics for a bridge config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == snapshot

    with (
        patch("pyhap.accessory_driver.AccessoryDriver.async_start"),
        patch("homeassistant.components.homekit.HomeKit.async_stop"),
        patch("homeassistant.components.homekit.async_port_is_available"),
    ):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_config_entry_accessory(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    hk_driver,
) -> None:
    """Test generating diagnostics for an accessory config entry."""
    hass.states.async_set("light.demo", "on")

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "mock_name",
            CONF_PORT: 12345,
            CONF_HOMEKIT_MODE: HOMEKIT_MODE_ACCESSORY,
            "filter": {
                "exclude_domains": [],
                "exclude_entities": [],
                "include_domains": [],
                "include_entities": ["light.demo"],
            },
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == snapshot
    with (
        patch("pyhap.accessory_driver.AccessoryDriver.async_start"),
        patch("homeassistant.components.homekit.HomeKit.async_stop"),
        patch("homeassistant.components.homekit.async_port_is_available"),
    ):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_config_entry_with_trigger_accessory(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    hk_driver,
    demo_cleanup,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test generating diagnostics for a bridge config entry with a trigger accessory."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "demo", {"demo": {}})
    hk_driver.publish = MagicMock()

    demo_config_entry = MockConfigEntry(domain="domain")
    demo_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, "demo", {"demo": {}})
    await hass.async_block_till_done()

    entry = entity_registry.async_get("light.ceiling_lights")
    assert entry is not None
    device_id = entry.device_id

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "mock_name",
            CONF_PORT: 12345,
            CONF_DEVICES: [device_id],
            "filter": {
                "exclude_domains": [],
                "exclude_entities": [],
                "include_domains": [],
                "include_entities": ["light.none"],
            },
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    diag.pop("iid_storage")
    diag.pop("bridge")
    assert diag == snapshot
    with (
        patch("pyhap.accessory_driver.AccessoryDriver.async_start"),
        patch("homeassistant.components.homekit.HomeKit.async_stop"),
        patch("homeassistant.components.homekit.async_port_is_available"),
    ):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
