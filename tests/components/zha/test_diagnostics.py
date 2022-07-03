"""Tests for the diagnostics data provided by the ESPHome integration."""


from unittest.mock import patch

import pytest
import zigpy.profiles.zha as zha
import zigpy.zcl.clusters.security as security

from homeassistant.components.diagnostics.const import REDACTED
from homeassistant.components.zha.core.device import ZHADevice
from homeassistant.components.zha.diagnostics import KEYS_TO_REDACT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)

CONFIG_ENTRY_DIAGNOSTICS_KEYS = [
    "config",
    "config_entry",
    "application_state",
    "versions",
]


@pytest.fixture(autouse=True)
def required_platforms_only():
    """Only setup the required platform and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS", (Platform.ALARM_CONTROL_PANEL,)
    ):
        yield


@pytest.fixture
def zigpy_device(zigpy_device_mock):
    """Device tracker zigpy device."""
    endpoints = {
        1: {
            SIG_EP_INPUT: [security.IasAce.cluster_id],
            SIG_EP_OUTPUT: [],
            SIG_EP_TYPE: zha.DeviceType.IAS_ANCILLARY_CONTROL,
            SIG_EP_PROFILE: zha.PROFILE_ID,
        }
    }
    return zigpy_device_mock(
        endpoints, node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00"
    )


async def test_diagnostics_for_config_entry(
    hass: HomeAssistant,
    hass_client,
    config_entry,
    zha_device_joined,
    zigpy_device,
):
    """Test diagnostics for config entry."""
    await zha_device_joined(zigpy_device)
    diagnostics_data = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert diagnostics_data
    for key in CONFIG_ENTRY_DIAGNOSTICS_KEYS:
        assert key in diagnostics_data
        assert diagnostics_data[key] is not None


async def test_diagnostics_for_device(
    hass: HomeAssistant,
    hass_client,
    config_entry,
    zha_device_joined,
    zigpy_device,
):
    """Test diagnostics for device."""

    zha_device: ZHADevice = await zha_device_joined(zigpy_device)
    dev_reg = async_get(hass)
    device = dev_reg.async_get_device({("zha", str(zha_device.ieee))})
    assert device
    diagnostics_data = await get_diagnostics_for_device(
        hass, hass_client, config_entry, device
    )
    assert diagnostics_data
    device_info: dict = zha_device.zha_device_info
    for key, value in device_info.items():
        assert key in diagnostics_data
        if key not in KEYS_TO_REDACT:
            assert key in diagnostics_data
        else:
            assert diagnostics_data[key] == REDACTED
