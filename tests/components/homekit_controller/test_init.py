"""Tests for homekit_controller init."""

from unittest.mock import patch

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes
from aiohomekit.testing import FakeController

from homeassistant.components.homekit_controller.const import ENTITY_MAP
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from tests.components.homekit_controller.common import setup_test_component


def create_motion_sensor_service(accessory):
    """Define motion characteristics as per page 225 of HAP spec."""
    service = accessory.add_service(ServicesTypes.MOTION_SENSOR)
    cur_state = service.add_char(CharacteristicsTypes.MOTION_DETECTED)
    cur_state.value = 0


async def test_unload_on_stop(hass, utcnow):
    """Test async_unload is called on stop."""
    await setup_test_component(hass, create_motion_sensor_service)
    with patch(
        "homeassistant.components.homekit_controller.HKDevice.async_unload"
    ) as async_unlock_mock:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert async_unlock_mock.called


async def test_async_remove_entry(hass: HomeAssistant):
    """Test unpairing a component."""
    helper = await setup_test_component(hass, create_motion_sensor_service)

    hkid = "00:00:00:00:00:00"

    with patch("aiohomekit.Controller") as controller_cls:
        # Setup a fake controller with 1 pairing
        controller = controller_cls.return_value = FakeController()
        await controller.add_paired_device([helper.accessory], hkid)
        assert len(controller.pairings) == 1

        assert hkid in hass.data[ENTITY_MAP].storage_data

        # Remove it via config entry and number of pairings should go down
        await helper.config_entry.async_remove(hass)
        assert len(controller.pairings) == 0

        assert hkid not in hass.data[ENTITY_MAP].storage_data
