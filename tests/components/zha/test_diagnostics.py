"""Tests for the diagnostics data provided by the ESPHome integration."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props
from zigpy.profiles import zha
from zigpy.zcl.clusters import security

from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def required_platforms_only():
    """Only set up the required platform and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS", (Platform.ALARM_CONTROL_PANEL,)
    ):
        yield


async def test_diagnostics_for_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    setup_zha,
    zigpy_device_mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [security.IasAce.cluster_id, security.IasZone.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.IAS_ANCILLARY_CONTROL,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee="01:2d:6f:00:0a:90:69:e8",
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    scan = {c: c for c in range(11, 26 + 1)}

    gateway.application_controller.energy_scan.side_effect = None
    gateway.application_controller.energy_scan.return_value = scan
    diagnostics_data = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics_data == snapshot(
        exclude=props("created_at", "modified_at", "entry_id", "versions")
    )


async def test_diagnostics_for_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    setup_zha,
    zigpy_device_mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for device."""
    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [security.IasAce.cluster_id, security.IasZone.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.IAS_ANCILLARY_CONTROL,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee="01:2d:6f:00:0a:90:69:e8",
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)

    # add unknown unsupported attribute with id and name
    zha_device_proxy.device.device.endpoints[1].in_clusters[
        security.IasAce.cluster_id
    ].unsupported_attributes.update({0x1000, "unknown_attribute_name"})

    # add known unsupported attributes with id and name
    zha_device_proxy.device.device.endpoints[1].in_clusters[
        security.IasZone.cluster_id
    ].unsupported_attributes.update(
        {
            security.IasZone.AttributeDefs.num_zone_sensitivity_levels_supported.id,
            security.IasZone.AttributeDefs.current_zone_sensitivity_level.name,
        }
    )

    device = device_registry.async_get_device(
        identifiers={("zha", str(zha_device_proxy.device.ieee))}
    )
    assert device
    diagnostics_data = await get_diagnostics_for_device(
        hass, hass_client, config_entry, device
    )

    assert diagnostics_data == snapshot(exclude=props("device_reg_id", "last_seen"))
