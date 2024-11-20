"""Test ZHA select entities."""

from unittest.mock import patch

import pytest
from zigpy.const import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE
from zigpy.profiles import zha
from zigpy.zcl.clusters import general, security

from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .common import find_entity_id

from tests.common import mock_restore_cache


@pytest.fixture(autouse=True)
def select_select_only():
    """Only set up the select and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BUTTON,
            Platform.DEVICE_TRACKER,
            Platform.SIREN,
            Platform.LIGHT,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SWITCH,
        ),
    ):
        yield


async def test_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_zha,
    zigpy_device_mock,
) -> None:
    """Test ZHA select platform."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id, security.IasWd.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.IAS_WARNING_DEVICE,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        }
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(
        Platform.SELECT, zha_device_proxy, hass, qualifier="tone"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes["options"] == [
        "Stop",
        "Burglar",
        "Fire",
        "Emergency",
        "Police Panic",
        "Fire Panic",
        "Emergency Panic",
    ]

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category == EntityCategory.CONFIG

    # Test select option with string value
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": entity_id,
            "option": security.IasWd.Warning.WarningMode.Burglar.name,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == security.IasWd.Warning.WarningMode.Burglar.name


@pytest.mark.parametrize(
    ("restored_state", "expected_state"),
    [
        # Unavailable is not restored
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
        # Normal state is
        (
            security.IasWd.Warning.WarningMode.Burglar.name,
            security.IasWd.Warning.WarningMode.Burglar.name,
        ),
    ],
)
async def test_select_restore_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_zha,
    zigpy_device_mock,
    restored_state: str,
    expected_state: str,
) -> None:
    """Test ZHA select platform restore state."""
    entity_id = "select.fakemanufacturer_fakemodel_default_siren_tone"

    mock_restore_cache(hass, [State(entity_id, restored_state)])

    await setup_zha()

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id, security.IasWd.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.IAS_WARNING_DEVICE,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        }
    )

    gateway = get_zha_gateway(hass)
    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state
