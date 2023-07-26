"""The test for ZHA device automation actions."""
from unittest.mock import call, patch

import pytest
from pytest_unordered import unordered
from zhaquirks.inovelli.VZM31SN import InovelliVZM31SNv11
import zigpy.profiles.zha
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.security as security
import zigpy.zcl.foundation as zcl_f

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.zha import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_TYPE

from tests.common import (
    async_get_device_automations,
    async_mock_service,
    mock_coro,
)


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


@pytest.fixture
async def device_inovelli(hass, zigpy_device_mock, zha_device_joined):
    """Inovelli device fixture."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    general.Identify.cluster_id,
                    general.OnOff.cluster_id,
                    general.LevelControl.cluster_id,
                    0xFC31,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.DIMMABLE_LIGHT,
            }
        },
        ieee="00:1d:8f:08:0c:90:69:6b",
        manufacturer="Inovelli",
        model="VZM31-SN",
        quirk=InovelliVZM31SNv11,
    )

    zha_device = await zha_device_joined(zigpy_device)
    zha_device.update_available(True)
    await hass.async_block_till_done()
    return zigpy_device, zha_device


async def test_get_actions(hass: HomeAssistant, device_ias) -> None:
    """Test we get the expected actions from a ZHA device."""

    ieee_address = str(device_ias[0].ieee)

    ha_device_registry = dr.async_get(hass)
    reg_device = ha_device_registry.async_get_device(
        identifiers={(DOMAIN, ieee_address)}
    )
    ha_entity_registry = er.async_get(hass)
    siren_level_select = ha_entity_registry.async_get(
        "select.fakemanufacturer_fakemodel_default_siren_level"
    )
    siren_tone_select = ha_entity_registry.async_get(
        "select.fakemanufacturer_fakemodel_default_siren_tone"
    )
    strobe_level_select = ha_entity_registry.async_get(
        "select.fakemanufacturer_fakemodel_default_strobe_level"
    )
    strobe_select = ha_entity_registry.async_get(
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
            for action in [
                "select_first",
                "select_last",
                "select_next",
                "select_option",
                "select_previous",
            ]
            for entity_id in [
                siren_level_select.id,
                siren_tone_select.id,
                strobe_level_select.id,
                strobe_select.id,
            ]
        ]
    )

    assert actions == unordered(expected_actions)


async def test_get_inovelli_actions(hass: HomeAssistant, device_inovelli) -> None:
    """Test we get the expected actions from a ZHA device."""

    inovelli_ieee_address = str(device_inovelli[0].ieee)
    ha_device_registry = dr.async_get(hass)
    inovelli_reg_device = ha_device_registry.async_get_device(
        identifiers={(DOMAIN, inovelli_ieee_address)}
    )
    ha_entity_registry = er.async_get(hass)
    inovelli_button = ha_entity_registry.async_get("button.inovelli_vzm31_sn_identify")
    inovelli_light = ha_entity_registry.async_get("light.inovelli_vzm31_sn_light")

    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, inovelli_reg_device.id
    )

    expected_actions = [
        {
            "device_id": inovelli_reg_device.id,
            "domain": DOMAIN,
            "metadata": {},
            "type": "issue_all_led_effect",
        },
        {
            "device_id": inovelli_reg_device.id,
            "domain": DOMAIN,
            "metadata": {},
            "type": "issue_individual_led_effect",
        },
        {
            "device_id": inovelli_reg_device.id,
            "domain": Platform.BUTTON,
            "entity_id": inovelli_button.id,
            "metadata": {"secondary": True},
            "type": "press",
        },
        {
            "device_id": inovelli_reg_device.id,
            "domain": Platform.LIGHT,
            "entity_id": inovelli_light.id,
            "metadata": {"secondary": False},
            "type": "turn_off",
        },
        {
            "device_id": inovelli_reg_device.id,
            "domain": Platform.LIGHT,
            "entity_id": inovelli_light.id,
            "metadata": {"secondary": False},
            "type": "turn_on",
        },
        {
            "device_id": inovelli_reg_device.id,
            "domain": Platform.LIGHT,
            "entity_id": inovelli_light.id,
            "metadata": {"secondary": False},
            "type": "toggle",
        },
        {
            "device_id": inovelli_reg_device.id,
            "domain": Platform.LIGHT,
            "entity_id": inovelli_light.id,
            "metadata": {"secondary": False},
            "type": "brightness_increase",
        },
        {
            "device_id": inovelli_reg_device.id,
            "domain": Platform.LIGHT,
            "entity_id": inovelli_light.id,
            "metadata": {"secondary": False},
            "type": "brightness_decrease",
        },
        {
            "device_id": inovelli_reg_device.id,
            "domain": Platform.LIGHT,
            "entity_id": inovelli_light.id,
            "metadata": {"secondary": False},
            "type": "flash",
        },
    ]

    assert actions == unordered(expected_actions)


async def test_action(hass: HomeAssistant, device_ias, device_inovelli) -> None:
    """Test for executing a ZHA device action."""
    zigpy_device, zha_device = device_ias
    inovelli_zigpy_device, inovelli_zha_device = device_inovelli

    zigpy_device.device_automation_triggers = {
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE}
    }

    ieee_address = str(zha_device.ieee)
    inovelli_ieee_address = str(inovelli_zha_device.ieee)

    ha_device_registry = dr.async_get(hass)
    reg_device = ha_device_registry.async_get_device(
        identifiers={(DOMAIN, ieee_address)}
    )
    inovelli_reg_device = ha_device_registry.async_get_device(
        identifiers={(DOMAIN, inovelli_ieee_address)}
    )

    cluster = inovelli_zigpy_device.endpoints[1].in_clusters[0xFC31]

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
                        "action": [
                            {
                                "domain": DOMAIN,
                                "device_id": reg_device.id,
                                "type": "warn",
                            },
                            {
                                "domain": DOMAIN,
                                "device_id": inovelli_reg_device.id,
                                "type": "issue_all_led_effect",
                                "effect_type": "Open_Close",
                                "duration": 5,
                                "level": 10,
                                "color": 41,
                            },
                            {
                                "domain": DOMAIN,
                                "device_id": inovelli_reg_device.id,
                                "type": "issue_individual_led_effect",
                                "effect_type": "Falling",
                                "led_number": 1,
                                "duration": 5,
                                "level": 10,
                                "color": 41,
                            },
                        ],
                    }
                ]
            },
        )

        await hass.async_block_till_done()
        calls = async_mock_service(hass, DOMAIN, "warning_device_warn")

        cluster_handler = zha_device.endpoints[1].client_cluster_handlers["1:0x0006"]
        cluster_handler.zha_send_event(COMMAND_SINGLE, [])
        await hass.async_block_till_done()

        assert len(calls) == 1
        assert calls[0].domain == DOMAIN
        assert calls[0].service == "warning_device_warn"
        assert calls[0].data["ieee"] == ieee_address

        assert len(cluster.request.mock_calls) == 2
        assert (
            call(
                False,
                cluster.commands_by_name["led_effect"].id,
                cluster.commands_by_name["led_effect"].schema,
                6,
                41,
                10,
                5,
                expect_reply=False,
                manufacturer=4151,
                tsn=None,
            )
            in cluster.request.call_args_list
        )
        assert (
            call(
                False,
                cluster.commands_by_name["individual_led_effect"].id,
                cluster.commands_by_name["individual_led_effect"].schema,
                1,
                6,
                41,
                10,
                5,
                expect_reply=False,
                manufacturer=4151,
                tsn=None,
            )
            in cluster.request.call_args_list
        )


async def test_invalid_zha_event_type(hass: HomeAssistant, device_ias) -> None:
    """Test that unexpected types are not passed to `zha_send_event`."""
    zigpy_device, zha_device = device_ias
    cluster_handler = zha_device._endpoints[1].client_cluster_handlers["1:0x0006"]

    # `zha_send_event` accepts only zigpy responses, lists, and dicts
    with pytest.raises(TypeError):
        cluster_handler.zha_send_event(COMMAND_SINGLE, 123)
