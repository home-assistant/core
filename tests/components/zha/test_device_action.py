"""The test for ZHA device automation actions."""

from unittest.mock import patch

import pytest
from pytest_unordered import unordered
from zigpy.profiles import zha
from zigpy.zcl.clusters import general, security
import zigpy.zcl.foundation as zcl_f

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.zha import DOMAIN
from homeassistant.components.zha.helpers import get_zha_gateway
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.common import async_get_device_automations, async_mock_service


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


SHORT_PRESS = "remote_button_short_press"
COMMAND = "command"
COMMAND_SINGLE = "single"


@pytest.fixture(autouse=True)
def required_platforms_only():
    """Only set up the required platforms and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BINARY_SENSOR,
            Platform.BUTTON,
            Platform.DEVICE_TRACKER,
            Platform.LIGHT,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SWITCH,
            Platform.SIREN,
        ),
    ):
        yield


async def test_get_actions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    setup_zha,
    zigpy_device_mock,
) -> None:
    """Test we get the expected actions from a ZHA device."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    security.IasZone.cluster_id,
                    security.IasWd.cluster_id,
                ],
                SIG_EP_OUTPUT: [general.OnOff.cluster_id],
                SIG_EP_TYPE: zha.DeviceType.IAS_WARNING_DEVICE,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        }
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)
    ieee_address = str(zigpy_device.ieee)

    reg_device = device_registry.async_get_device(identifiers={(DOMAIN, ieee_address)})
    siren_level_select = entity_registry.async_get(
        "select.fakemanufacturer_fakemodel_default_siren_level"
    )
    siren_tone_select = entity_registry.async_get(
        "select.fakemanufacturer_fakemodel_default_siren_tone"
    )
    strobe_level_select = entity_registry.async_get(
        "select.fakemanufacturer_fakemodel_default_strobe_level"
    )
    strobe_select = entity_registry.async_get(
        "select.fakemanufacturer_fakemodel_default_strobe"
    )

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
    ]
    expected_actions.extend(
        [
            {
                "domain": Platform.SELECT,
                "type": action,
                "device_id": reg_device.id,
                "entity_id": entity_id,
                "metadata": {"secondary": True},
            }
            for action in (
                "select_first",
                "select_last",
                "select_next",
                "select_option",
                "select_previous",
            )
            for entity_id in (
                siren_level_select.id,
                siren_tone_select.id,
                strobe_level_select.id,
                strobe_select.id,
            )
        ]
    )

    assert actions == unordered(expected_actions)


async def test_action(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_zha,
    zigpy_device_mock,
) -> None:
    """Test for executing a ZHA device action."""
    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    security.IasZone.cluster_id,
                    security.IasWd.cluster_id,
                ],
                SIG_EP_OUTPUT: [general.OnOff.cluster_id],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        }
    )
    zigpy_device.device_automation_triggers = {
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE}
    }

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)
    ieee_address = str(zigpy_device.ieee)

    reg_device = device_registry.async_get_device(identifiers={(DOMAIN, ieee_address)})

    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x00, zcl_f.Status.SUCCESS],
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
                        "action": [
                            {
                                "domain": DOMAIN,
                                "device_id": reg_device.id,
                                "type": "warn",
                            },
                        ],
                    }
                ]
            },
        )

        await hass.async_block_till_done()
        calls = async_mock_service(hass, DOMAIN, "warning_device_warn")

        cluster_handler = (
            gateway.get_device(zigpy_device.ieee)
            .endpoints[1]
            .client_cluster_handlers["1:0x0006"]
        )
        cluster_handler.zha_send_event(COMMAND_SINGLE, [])
        await hass.async_block_till_done()

        assert len(calls) == 1
        assert calls[0].domain == DOMAIN
        assert calls[0].service == "warning_device_warn"
        assert calls[0].data["ieee"] == ieee_address


async def test_invalid_zha_event_type(
    hass: HomeAssistant, setup_zha, zigpy_device_mock
) -> None:
    """Test that unexpected types are not passed to `zha_send_event`."""
    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    security.IasZone.cluster_id,
                    security.IasWd.cluster_id,
                ],
                SIG_EP_OUTPUT: [general.OnOff.cluster_id],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        }
    )
    zigpy_device.device_automation_triggers = {
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE}
    }

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    cluster_handler = (
        gateway.get_device(zigpy_device.ieee)
        .endpoints[1]
        .client_cluster_handlers["1:0x0006"]
    )

    # `zha_send_event` accepts only zigpy responses, lists, and dicts
    with pytest.raises(TypeError):
        cluster_handler.zha_send_event(COMMAND_SINGLE, 123)
