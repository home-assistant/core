"""Tests for the Shelly integration init."""
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.shelly.const import DOMAIN, SERVICE_OTA_UPDATE, SERVICES
from homeassistant.components.shelly.service import async_services_setup
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    async_entries_for_config_entry,
    async_get,
)


async def test_services_registered(hass):
    """Test if all services are registered."""
    await async_services_setup(hass)
    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)


async def test_service_error(hass):
    """Test for errors in service call."""
    await async_services_setup(hass)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_OTA_UPDATE,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_service_ota_coap_device(hass, coap_wrapper):
    """Test OTA update service with block device."""
    assert coap_wrapper
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            coap_wrapper.entry, BINARY_SENSOR_DOMAIN
        )
    )
    await hass.async_block_till_done()

    dev_reg = async_get(hass)
    devices = async_entries_for_config_entry(dev_reg, coap_wrapper.entry.entry_id)
    assert devices
    assert devices[0]

    await async_services_setup(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_OTA_UPDATE,
        {ATTR_DEVICE_ID: devices[0].id},
        blocking=True,
    )
    await hass.async_block_till_done()
    coap_wrapper.device.trigger_ota_update.assert_called_once()


async def test_service_ota_rpc_device(hass, rpc_wrapper):
    """Test OTA update service with rpc device."""
    assert rpc_wrapper
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            rpc_wrapper.entry, BINARY_SENSOR_DOMAIN
        )
    )
    await hass.async_block_till_done()

    dev_reg = async_get(hass)
    devices = async_entries_for_config_entry(dev_reg, rpc_wrapper.entry.entry_id)
    assert devices
    assert devices[0]

    await async_services_setup(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_OTA_UPDATE,
        {ATTR_DEVICE_ID: devices[0].id},
        blocking=True,
    )
    await hass.async_block_till_done()
    rpc_wrapper.device.trigger_ota_update.assert_called_once()
