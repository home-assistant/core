"""Test cases for the switcher_kis component."""

from datetime import timedelta
from typing import Any, Generator, TYPE_CHECKING

from pytest import raises
from voluptuous import MultipleInvalid

from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.components.switcher_kis import (
    CONF_AUTO_OFF, DOMAIN, DATA_DEVICE, SERVICE_SET_AUTO_OFF_NAME,
    SERVICE_SET_AUTO_OFF_SCHEMA, SERVICE_UPDATE_DEVICE_NAME_NAME,
    SERVICE_UPDATE_DEVICE_NAME_SCHEMA, SIGNAL_SWITCHER_DEVICE_UPDATE)
from homeassistant.core import callback, Context
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from tests.common import async_mock_service, async_fire_time_changed

from .consts import (
    DUMMY_AUTO_OFF_SET, DUMMY_DEVICE_ID, DUMMY_DEVICE_NAME,
    DUMMY_DEVICE_STATE, DUMMY_ELECTRIC_CURRENT, DUMMY_IP_ADDRESS,
    DUMMY_MAC_ADDRESS, DUMMY_PHONE_ID, DUMMY_POWER_CONSUMPTION,
    DUMMY_REMAINING_TIME, MANDATORY_CONFIGURATION, SWITCH_ENTITY_ID)

if TYPE_CHECKING:
    from tests.common import MockUser
    from aioswitcher.devices import SwitcherV2Device


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
        mock_api: Generator[None, Any, None], hass_owner_user: 'MockUser',
        hass_read_only_user: 'MockUser') -> None:
    """Test the update_device_name service."""
    assert await async_setup_component(hass, DOMAIN, MANDATORY_CONFIGURATION)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME)

    await hass.services.async_call(
        DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME,
        {CONF_ENTITY_ID: SWITCH_ENTITY_ID,
         CONF_NAME: DUMMY_DEVICE_NAME},
        blocking=True, context=Context(user_id=hass_owner_user.id))

    with raises(Unauthorized) as unauthorized_exc:
        await hass.services.async_call(
            DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME,
            {CONF_ENTITY_ID: SWITCH_ENTITY_ID,
             CONF_NAME: DUMMY_DEVICE_NAME},
            blocking=True, context=Context(user_id=hass_read_only_user.id))

    assert unauthorized_exc.type is Unauthorized

    with raises(UnknownUser) as unknown_user_exc:
        await hass.services.async_call(
            DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME,
            {CONF_ENTITY_ID: SWITCH_ENTITY_ID,
             CONF_NAME: DUMMY_DEVICE_NAME},
            blocking=True, context=Context(user_id="fake_user"))

    assert unknown_user_exc.type is UnknownUser

    service_calls = async_mock_service(
        hass, DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME,
        SERVICE_UPDATE_DEVICE_NAME_SCHEMA)

    with raises(MultipleInvalid) as too_short_exc:
        await hass.services.async_call(
            DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME,
            {CONF_ENTITY_ID: SWITCH_ENTITY_ID, CONF_NAME: 'x'})

    assert too_short_exc.type is MultipleInvalid

    with raises(MultipleInvalid) as too_long_exc:
        await hass.services.async_call(
            DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME,
            {CONF_ENTITY_ID: SWITCH_ENTITY_ID, CONF_NAME: 'x' * 33})

    assert too_long_exc.type is MultipleInvalid

    await hass.services.async_call(
        DOMAIN, SERVICE_UPDATE_DEVICE_NAME_NAME,
        {CONF_ENTITY_ID: SWITCH_ENTITY_ID,
         CONF_NAME: DUMMY_DEVICE_NAME})

    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_NAME] == DUMMY_DEVICE_NAME


async def test_set_auto_off_service(
        hass: HomeAssistantType, mock_bridge: Generator[None, Any, None],
        mock_api: Generator[None, Any, None], hass_owner_user: 'MockUser',
        hass_read_only_user: 'MockUser') -> None:
    """Test the set_auto_off service."""
    assert await async_setup_component(hass, DOMAIN, MANDATORY_CONFIGURATION)

    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_SET_AUTO_OFF_NAME)

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_AUTO_OFF_NAME,
        {CONF_ENTITY_ID: SWITCH_ENTITY_ID,
         CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET},
        blocking=True, context=Context(user_id=hass_owner_user.id))

    with raises(Unauthorized) as unauthorized_exc:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_AUTO_OFF_NAME,
            {CONF_ENTITY_ID: SWITCH_ENTITY_ID,
             CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET},
            blocking=True, context=Context(user_id=hass_read_only_user.id))

    assert unauthorized_exc.type is Unauthorized

    with raises(UnknownUser) as unknown_user_exc:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_AUTO_OFF_NAME,
            {CONF_ENTITY_ID: SWITCH_ENTITY_ID,
             CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET},
            blocking=True, context=Context(user_id="fake_user"))

    assert unknown_user_exc.type is UnknownUser

    service_calls = async_mock_service(
        hass, DOMAIN, SERVICE_SET_AUTO_OFF_NAME, SERVICE_SET_AUTO_OFF_SCHEMA)

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_AUTO_OFF_NAME,
        {CONF_ENTITY_ID: SWITCH_ENTITY_ID,
         CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET})

    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert str(service_calls[0].data[CONF_AUTO_OFF]) \
        == DUMMY_AUTO_OFF_SET.lstrip('0')


async def test_signal_dispatcher(
        hass: HomeAssistantType,
        mock_bridge: Generator[None, Any, None]) -> None:
    """Test signal dispatcher dispatching device updates every 4 seconds."""
    assert await async_setup_component(hass, DOMAIN, MANDATORY_CONFIGURATION)

    await hass.async_block_till_done()

    @callback
    def verify_update_data(device: 'SwitcherV2Device') -> None:
        """Use as callback for signal dispatcher."""
        pass

    async_dispatcher_connect(
        hass, SIGNAL_SWITCHER_DEVICE_UPDATE, verify_update_data)

    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=5))
