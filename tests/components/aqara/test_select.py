"""Tests for the Aqara select device."""
from unittest.mock import patch
import aqara_iot.openmq
from .common import mock_start
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
    ATTR_OPTION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .common import setup_platform
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNKNOWN,
)


DEVICE_ID = "select.mao_jin_jia_lumi_54ef44100031821d"
DEVICE_UID = "Aqara.lumi.54ef44100031821d__4.21.85"


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Tests that the devices are registered in the entity registry."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):
        await setup_platform(hass, SELECT_DOMAIN)
        entity_registry = er.async_get(hass)
        entry = entity_registry.async_get(DEVICE_ID)
        print("=============test_entity_registry=============")
        print(entry)
        assert entry.unique_id == DEVICE_UID  # "Aqara.lumi.12345__4.7.85"


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the select attributes are correct."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, SELECT_DOMAIN)
        state = hass.states.get(DEVICE_ID)
        assert state.state == "close"
        print("====== test_attributes =====")
        print(state.state)


async def test_select(hass: HomeAssistant) -> None:
    """Test the select can be press."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, SELECT_DOMAIN)

        with patch("aqara_iot.AqaraDeviceManager.send_commands") as mock_command:
            assert await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {ATTR_ENTITY_ID: DEVICE_ID, ATTR_OPTION: "open"},
                blocking=True,
            )
            await hass.async_block_till_done()
            mock_command.assert_called_once()

    # data = {
    #     ATTR_ENTITY_ID: "select.reg_number_charge_mode",
    #     ATTR_OPTION: "always",
    # }

    # with patch(
    #     "renault_api.renault_vehicle.RenaultVehicle.set_charge_mode",
    #     return_value=(
    #         schemas.KamereonVehicleHvacStartActionDataSchema.loads(
    #             load_fixture("renault/action.set_charge_mode.json")
    #         )
    #     ),
    # ) as mock_action:
    #     await hass.services.async_call(
    #         SELECT_DOMAIN, SERVICE_SELECT_OPTION, service_data=data, blocking=True
    #     )
    # assert len(mock_action.mock_calls) == 1
    # assert mock_action.mock_calls[0][1] == ("always",)
