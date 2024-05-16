"""Tests for the wemo component."""

import asyncio
from datetime import timedelta
from unittest.mock import create_autospec, patch

import pywemo

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.wemo import (
    CONF_DISCOVERY,
    CONF_STATIC,
    WemoDiscovery,
    async_wemo_dispatcher_connect,
)
from homeassistant.components.wemo.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import entity_test_helpers
from .conftest import (
    MOCK_FIRMWARE_VERSION,
    MOCK_HOST,
    MOCK_NAME,
    MOCK_PORT,
    MOCK_SERIAL_NUMBER,
)

from tests.common import async_fire_time_changed


async def test_config_no_config(hass: HomeAssistant) -> None:
    """Component setup succeeds when there are no config entry for the domain."""
    assert await async_setup_component(hass, DOMAIN, {})


async def test_config_no_static(hass: HomeAssistant) -> None:
    """Component setup succeeds when there are no static config entries."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_DISCOVERY: False}})


async def test_static_duplicate_static_entry(
    hass: HomeAssistant, pywemo_device
) -> None:
    """Duplicate static entries are merged into a single entity."""
    static_config_entry = f"{MOCK_HOST}:{MOCK_PORT}"
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_STATIC: [
                    static_config_entry,
                    static_config_entry,
                ],
            },
        },
    )
    await hass.async_block_till_done()
    entity_reg = er.async_get(hass)
    entity_entries = list(entity_reg.entities.values())
    assert len(entity_entries) == 1


async def test_static_config_with_port(hass: HomeAssistant, pywemo_device) -> None:
    """Static device with host and port is added and removed."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_STATIC: [f"{MOCK_HOST}:{MOCK_PORT}"],
            },
        },
    )
    await hass.async_block_till_done()
    entity_reg = er.async_get(hass)
    entity_entries = list(entity_reg.entities.values())
    assert len(entity_entries) == 1


async def test_static_config_without_port(hass: HomeAssistant, pywemo_device) -> None:
    """Static device with host and no port is added and removed."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_STATIC: [MOCK_HOST],
            },
        },
    )
    await hass.async_block_till_done()
    entity_reg = er.async_get(hass)
    entity_entries = list(entity_reg.entities.values())
    assert len(entity_entries) == 1


async def test_reload_config_entry(
    hass: HomeAssistant,
    pywemo_device: pywemo.WeMoDevice,
    pywemo_registry: pywemo.SubscriptionRegistry,
) -> None:
    """Config entry can be reloaded without errors."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_STATIC: [MOCK_HOST],
            },
        },
    )

    async def _async_test_entry_and_entity() -> tuple[str, str]:
        await hass.async_block_till_done()

        pywemo_device.get_state.assert_called()
        pywemo_device.get_state.reset_mock()

        pywemo_registry.register.assert_called_once_with(pywemo_device)
        pywemo_registry.register.reset_mock()

        entity_registry = er.async_get(hass)
        entity_entries = list(entity_registry.entities.values())
        assert len(entity_entries) == 1
        await entity_test_helpers.test_turn_off_state(
            hass, entity_entries[0], SWITCH_DOMAIN
        )

        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1

        return entries[0].entry_id, entity_entries[0].entity_id

    entry_id, entity_id = await _async_test_entry_and_entity()
    pywemo_registry.unregister.assert_not_called()

    assert await hass.config_entries.async_reload(entry_id)

    ids = await _async_test_entry_and_entity()
    pywemo_registry.unregister.assert_called_once_with(pywemo_device)
    assert ids == (entry_id, entity_id)


async def test_static_config_with_invalid_host(hass: HomeAssistant) -> None:
    """Component setup fails if a static host is invalid."""
    setup_success = await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_STATIC: [""],
            },
        },
    )
    assert not setup_success


async def test_static_with_upnp_failure(
    hass: HomeAssistant, pywemo_device: pywemo.WeMoDevice
) -> None:
    """Device that fails to get state is not added."""
    pywemo_device.get_state.side_effect = pywemo.exceptions.ActionException("Failed")
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_STATIC: [f"{MOCK_HOST}:{MOCK_PORT}"],
            },
        },
    )
    await hass.async_block_till_done()
    entity_reg = er.async_get(hass)
    entity_entries = list(entity_reg.entities.values())
    assert len(entity_entries) == 0
    pywemo_device.get_state.assert_called_once()


async def test_discovery(hass: HomeAssistant, pywemo_registry) -> None:
    """Verify that discovery dispatches devices to the platform for setup."""

    def create_device(counter):
        """Create a unique mock Motion detector device for each counter value."""
        device = create_autospec(pywemo.Motion, instance=True)
        device.host = f"{MOCK_HOST}_{counter}"
        device.port = MOCK_PORT + counter
        device.name = f"{MOCK_NAME}_{counter}"
        device.serial_number = f"{MOCK_SERIAL_NUMBER}_{counter}"
        device.model_name = "Motion"
        device.udn = f"uuid:{device.model_name}-1_0-{device.serial_number}"
        device.firmware_version = MOCK_FIRMWARE_VERSION
        device.get_state.return_value = 0  # Default to Off
        device.supports_long_press.return_value = False
        return device

    semaphore = asyncio.Semaphore(value=0)

    async def async_connect(*args):
        await async_wemo_dispatcher_connect(*args)
        semaphore.release()

    pywemo_devices = [create_device(0), create_device(1)]
    # Setup the component and start discovery.
    with (
        patch("pywemo.discover_devices", return_value=pywemo_devices) as mock_discovery,
        patch(
            "homeassistant.components.wemo.WemoDiscovery.discover_statics"
        ) as mock_discover_statics,
        patch(
            "homeassistant.components.wemo.binary_sensor.async_wemo_dispatcher_connect",
            side_effect=async_connect,
        ),
    ):
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_DISCOVERY: True}}
        )
        await semaphore.acquire()  # Returns after platform setup.
        mock_discovery.assert_called()
        mock_discover_statics.assert_called()
        pywemo_devices.append(create_device(2))

        # Test that discovery runs periodically and the async_dispatcher_send code works.
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=WemoDiscovery.ADDITIONAL_SECONDS_BETWEEN_SCANS + 1),
        )
        await hass.async_block_till_done()
        # Test that discover_statics runs during discovery
        assert mock_discover_statics.call_count == 3

    # Verify that the expected number of devices were setup.
    entity_reg = er.async_get(hass)
    entity_entries = list(entity_reg.entities.values())
    assert len(entity_entries) == 3

    # Verify that hass stops cleanly.
    await hass.async_stop()
    await hass.async_block_till_done()
