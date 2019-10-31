"""The test for zha device automation actions."""
from unittest.mock import patch

import pytest
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.security as security
import zigpy.zcl.foundation as zcl_f

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import (
    _async_get_device_automations as async_get_device_automations,
)
from homeassistant.components.zha import DOMAIN
from homeassistant.components.zha.core.const import CHANNEL_ON_OFF
from homeassistant.helpers.device_registry import async_get_registry
from homeassistant.setup import async_setup_component

from .common import async_enable_traffic, async_init_zigpy_device

from tests.common import async_mock_service, mock_coro

SHORT_PRESS = "remote_button_short_press"
COMMAND = "command"
COMMAND_SINGLE = "single"


@pytest.fixture
def calls(hass):
    """Track calls to a mock serivce."""
    return async_mock_service(hass, "zha", "warning_device_warn")


async def test_get_actions(hass, config_entry, zha_gateway):
    """Test we get the expected actions from a zha device."""

    # create zigpy device
    zigpy_device = await async_init_zigpy_device(
        hass,
        [
            general.Basic.cluster_id,
            security.IasZone.cluster_id,
            security.IasWd.cluster_id,
        ],
        [],
        None,
        zha_gateway,
    )

    await hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor")
    await hass.async_block_till_done()
    hass.config_entries._entries.append(config_entry)

    zha_device = zha_gateway.get_device(zigpy_device.ieee)
    ieee_address = str(zha_device.ieee)

    ha_device_registry = await async_get_registry(hass)
    reg_device = ha_device_registry.async_get_device({(DOMAIN, ieee_address)}, set())

    actions = await async_get_device_automations(hass, "action", reg_device.id)

    expected_actions = [
        {"domain": DOMAIN, "type": "squawk", "device_id": reg_device.id},
        {"domain": DOMAIN, "type": "warn", "device_id": reg_device.id},
    ]

    assert actions == expected_actions


async def test_action(hass, config_entry, zha_gateway, calls):
    """Test for executing a zha device action."""

    # create zigpy device
    zigpy_device = await async_init_zigpy_device(
        hass,
        [
            general.Basic.cluster_id,
            security.IasZone.cluster_id,
            security.IasWd.cluster_id,
        ],
        [general.OnOff.cluster_id],
        None,
        zha_gateway,
    )

    zigpy_device.device_automation_triggers = {
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE}
    }

    await hass.config_entries.async_forward_entry_setup(config_entry, "switch")
    await hass.async_block_till_done()

    hass.config_entries._entries.append(config_entry)

    zha_device = zha_gateway.get_device(zigpy_device.ieee)
    ieee_address = str(zha_device.ieee)

    ha_device_registry = await async_get_registry(hass)
    reg_device = ha_device_registry.async_get_device({(DOMAIN, ieee_address)}, set())

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, zha_gateway, [zha_device])

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

        on_off_channel = zha_device.cluster_channels[CHANNEL_ON_OFF]
        on_off_channel.zha_send_event(on_off_channel.cluster, COMMAND_SINGLE, [])
        await hass.async_block_till_done()

        assert len(calls) == 1
        assert calls[0].domain == DOMAIN
        assert calls[0].service == "warning_device_warn"
        assert calls[0].data["ieee"] == ieee_address
