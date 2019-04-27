"""Test cases for the switcher_kis component."""

from typing import Any, Generator

from asynctest import CoroutineMock
from pytest import raises
from voluptuous import MultipleInvalid

from homeassistant.const import CONF_NAME
from homeassistant.components.switcher_kis import (
    CONF_AUTO_OFF, DOMAIN, DATA_DEVICE, SERVICE_SET_AUTO_OFF_NAME,
    SERVICE_SET_AUTO_OFF_SCHEMA, SERVICE_UPDATE_DEVICE_NAME_NAME,
    SERVICE_UPDATE_DEVICE_NAME_SCHEMA)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service

from .consts import (
    DUMMY_AUTO_OFF_SET, DUMMY_DEVICE_ID, DUMMY_DEVICE_NAME,
    DUMMY_DEVICE_STATE, DUMMY_ELECTRIC_CURRENT, DUMMY_IP_ADDRESS,
    DUMMY_MAC_ADDRESS, DUMMY_PHONE_ID, DUMMY_POWER_CONSUMPTION,
    DUMMY_REMAINING_TIME, MANDATORY_CONFIGURATION)


async def test_failed_config(
        hass: HomeAssistantType,
        mock_failed_bridge: Generator[None, Any, None]) -> None:
    """Test failed configuration."""
    assert await async_setup_component(
        hass, DOMAIN, MANDATORY_CONFIGURATION) is False


async def test_minimal_config(hass: HomeAssistantType,
                              mock_bridge: Generator[None, Any, None]
                              ) -> None:
    """Test setup with configuration minimal entries."""
    assert await async_setup_component(hass, DOMAIN, MANDATORY_CONFIGURATION)


async def test_discovery_data_bucket(
        hass: HomeAssistantType,
        mock_bridge: Generator[None, Any, None]
        ) -> None:
    """Test the event send with the updated device."""
    assert await async_setup_component(
        hass, DOMAIN, MANDATORY_CONFIGURATION)

    await hass.async_block_till_done()

    device = hass.data[DOMAIN].get(DATA_DEVICE)
    assert device.device_id == DUMMY_DEVICE_ID
    assert device.ip_addr == DUMMY_IP_ADDRESS
    assert device.mac_addr == DUMMY_MAC_ADDRESS
    assert device.name == DUMMY_DEVICE_NAME
    assert device.state == DUMMY_DEVICE_STATE
    assert device.remaining_time == DUMMY_REMAINING_TIME
    assert device.auto_off_set == DUMMY_AUTO_OFF_SET
    assert device.power_consumption == DUMMY_POWER_CONSUMPTION
    assert device.electric_current == DUMMY_ELECTRIC_CURRENT
    assert device.phone_id == DUMMY_PHONE_ID


async def test_update_device_name_service(
        hass: HomeAssistantType, mock_bridge: Generator[None, Any, None],
        mock_api: CoroutineMock) -> None:
    """Test the update_device_name service."""
    assert await async_setup_component(hass, DOMAIN, MANDATORY_CONFIGURATION)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME)

    mock_api.set_device_name = None

    await hass.services.async_call(
        DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME,
        {CONF_NAME: DUMMY_DEVICE_NAME})

    await hass.async_block_till_done()

    service_calls = async_mock_service(
        hass, DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME,
        SERVICE_UPDATE_DEVICE_NAME_SCHEMA)

    with raises(MultipleInvalid) as too_short_exc:
        await hass.services.async_call(
            DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME, {CONF_NAME: 'x'})

    assert too_short_exc.type is MultipleInvalid

    with raises(MultipleInvalid) as too_long_exc:
        await hass.services.async_call(
            DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME, {CONF_NAME: 'x' * 33})

    assert too_long_exc.type is MultipleInvalid

    await hass.services.async_call(
        DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME,
        {CONF_NAME: DUMMY_DEVICE_NAME})

    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_NAME] == DUMMY_DEVICE_NAME


async def test_set_auto_off_service(
        hass: HomeAssistantType, mock_bridge: Generator[None, Any, None],
        mock_api: CoroutineMock) -> None:
    """Test the set_auto_off service."""
    assert await async_setup_component(hass, DOMAIN, MANDATORY_CONFIGURATION)

    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_SET_AUTO_OFF_NAME)

    mock_api.set_auto_shutdown = None

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_AUTO_OFF_NAME,
        {CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET})

    await hass.async_block_till_done()

    service_calls = async_mock_service(
        hass, DOMAIN, SERVICE_SET_AUTO_OFF_NAME, SERVICE_SET_AUTO_OFF_SCHEMA)

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_AUTO_OFF_NAME,
        {CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET})

    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert str(service_calls[0].data[CONF_AUTO_OFF]) \
        == DUMMY_AUTO_OFF_SET.lstrip('0')
