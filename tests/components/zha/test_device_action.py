"""The test for zha device automation actions."""
from unittest.mock import patch

import pytest
import zigpy.profiles.zha
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.security as security
import zigpy.zcl.foundation as zcl_f

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.zha import DOMAIN
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_TYPE

from tests.common import async_get_device_automations, async_mock_service, mock_coro
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401

SHORT_PRESS = "remote_button_short_press"
COMMAND = "command"
COMMAND_SINGLE = "single"


@pytest.fixture(autouse=True)
def required_platforms_only():
    """Only setup the required platforms and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BINARY_SENSOR,
            Platform.DEVICE_TRACKER,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SIREN,
        ),
    ):
        yield


@pytest.fixture
async def device_ias(hass, zigpy_device_mock, zha_device_joined_restored):
    """IAS device fixture."""

    clusters = [general.Basic, security.IasZone, security.IasWd]
    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [c.cluster_id for c in clusters],
                SIG_EP_OUTPUT: [general.OnOff.cluster_id],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        },
    )

    zha_device = await zha_device_joined_restored(zigpy_device)
    zha_device.update_available(True)
    await hass.async_block_till_done()
    return zigpy_device, zha_device


async def test_get_actions(hass, device_ias):
    """Test we get the expected actions from a zha device."""

    ieee_address = str(device_ias[0].ieee)

    ha_device_registry = dr.async_get(hass)
    reg_device = ha_device_registry.async_get_device({(DOMAIN, ieee_address)})

    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, reg_device.id
    )

    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "squawk",
            "device_id": reg_device.id,
            "metadata": {},
        },
        {"domain": DOMAIN, "type": "warn", "device_id": reg_device.id, "metadata": {}},
        {
            "domain": Platform.SELECT,
            "type": "select_option",
            "device_id": reg_device.id,
            "entity_id": "select.fakemanufacturer_fakemodel_defaulttoneselect",
            "metadata": {"secondary": True},
        },
        {
            "domain": Platform.SELECT,
            "type": "select_option",
            "device_id": reg_device.id,
            "entity_id": "select.fakemanufacturer_fakemodel_defaultsirenlevelselect",
            "metadata": {"secondary": True},
        },
        {
            "domain": Platform.SELECT,
            "type": "select_option",
            "device_id": reg_device.id,
            "entity_id": "select.fakemanufacturer_fakemodel_defaultstrobelevelselect",
            "metadata": {"secondary": True},
        },
        {
            "domain": Platform.SELECT,
            "type": "select_option",
            "device_id": reg_device.id,
            "entity_id": "select.fakemanufacturer_fakemodel_defaultstrobeselect",
            "metadata": {"secondary": True},
        },
    ]

    assert actions == expected_actions


async def test_action(hass, device_ias):
    """Test for executing a zha device action."""
    zigpy_device, zha_device = device_ias

    zigpy_device.device_automation_triggers = {
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE}
    }

    ieee_address = str(zha_device.ieee)

    ha_device_registry = dr.async_get(hass)
    reg_device = ha_device_registry.async_get_device({(DOMAIN, ieee_address)})

    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=mock_coro([0x00, zcl_f.Status.SUCCESS]),
    ):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: [
                    {
                        "trigger": {
                            "device_id": reg_device.id,
                            "domain": "zha",
                            "platform": "device",
                            "type": SHORT_PRESS,
                            "subtype": SHORT_PRESS,
                        },
                        "action": {
                            "domain": DOMAIN,
                            "device_id": reg_device.id,
                            "type": "warn",
                        },
                    }
                ]
            },
        )

        await hass.async_block_till_done()
        calls = async_mock_service(hass, DOMAIN, "warning_device_warn")

        channel = zha_device.channels.pools[0].client_channels["1:0x0006"]
        channel.zha_send_event(COMMAND_SINGLE, [])
        await hass.async_block_till_done()

        assert len(calls) == 1
        assert calls[0].domain == DOMAIN
        assert calls[0].service == "warning_device_warn"
        assert calls[0].data["ieee"] == ieee_address


async def test_invalid_zha_event_type(hass, device_ias):
    """Test that unexpected types are not passed to `zha_send_event`."""
    zigpy_device, zha_device = device_ias
    channel = zha_device.channels.pools[0].client_channels["1:0x0006"]

    # `zha_send_event` accepts only zigpy responses, lists, and dicts
    with pytest.raises(TypeError):
        channel.zha_send_event(COMMAND_SINGLE, 123)
