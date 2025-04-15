"""Tests for the HDMI-CEC switch platform."""

from pycec.const import POWER_OFF, POWER_ON, STATUS_PLAY, STATUS_STILL, STATUS_STOP
from pycec.network import PhysicalAddress
import pytest

from homeassistant.components.hdmi_cec import EVENT_HDMI_CEC_UNAVAILABLE
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from . import MockHDMIDevice
from .conftest import CecEntityCreator, HDMINetworkCreator


@pytest.mark.parametrize("config", [{}, {"platform": "switch"}])
async def test_load_platform(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    config,
) -> None:
    """Test that switch entity is loaded."""
    hdmi_network = await create_hdmi_network(config=config)
    mock_hdmi_device = MockHDMIDevice(logical_address=3)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    mock_hdmi_device.set_update_callback.assert_called_once()
    state = hass.states.get("media_player.hdmi_3")
    assert state is None

    state = hass.states.get("switch.hdmi_3")
    assert state is not None


async def test_load_types(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
) -> None:
    """Test that switch entity is loaded when types is set."""
    config = {"platform": "media_player", "types": {"hdmi_cec.hdmi_3": "switch"}}
    hdmi_network = await create_hdmi_network(config=config)
    mock_hdmi_device = MockHDMIDevice(logical_address=3)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    mock_hdmi_device.set_update_callback.assert_called_once()
    state = hass.states.get("media_player.hdmi_3")
    assert state is None

    state = hass.states.get("switch.hdmi_3")
    assert state is not None

    mock_hdmi_device = MockHDMIDevice(logical_address=4)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    mock_hdmi_device.set_update_callback.assert_called_once()
    state = hass.states.get("media_player.hdmi_4")
    assert state is not None

    state = hass.states.get("switch.hdmi_4")
    assert state is None


async def test_service_on(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
) -> None:
    """Test that switch triggers on `on` service."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3, power_status=3)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    state = hass.states.get("switch.hdmi_3")
    assert state.state != STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "switch.hdmi_3"}, blocking=True
    )

    mock_hdmi_device.turn_on.assert_called_once_with()

    state = hass.states.get("switch.hdmi_3")
    assert state.state == STATE_ON


async def test_service_off(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
) -> None:
    """Test that switch triggers on `off` service."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3, power_status=4)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    state = hass.states.get("switch.hdmi_3")
    assert state.state != STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.hdmi_3"},
        blocking=True,
    )

    mock_hdmi_device.turn_off.assert_called_once_with()

    state = hass.states.get("switch.hdmi_3")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("power_status", "expected_state"),
    [(3, STATE_OFF), (POWER_OFF, STATE_OFF), (4, STATE_ON), (POWER_ON, STATE_ON)],
)
@pytest.mark.parametrize(
    "status",
    [
        None,
        STATUS_PLAY,
        STATUS_STOP,
        STATUS_STILL,
    ],
)
async def test_device_status_change(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    power_status,
    expected_state,
    status,
) -> None:
    """Test state change on device status change."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3, status=status)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    mock_hdmi_device.power_status = power_status
    await hass.async_block_till_done()

    state = hass.states.get("switch.hdmi_3")
    if power_status in (POWER_ON, 4) and status is not None:
        pytest.xfail(
            reason="`CecSwitchEntity.is_on` returns `False` here instead of `true` as expected."
        )
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("device_values", "expected"),
    [
        ({"osd_name": "Switch", "vendor": "Nintendo"}, "Nintendo Switch"),
        ({"type_name": "TV"}, "TV 3"),
        ({"type_name": "Playback", "osd_name": "Switch"}, "Playback 3 (Switch)"),
        ({"type_name": "TV", "vendor": "Samsung"}, "TV 3"),
        (
            {"type_name": "Playback", "osd_name": "Super PC", "vendor": "Unknown"},
            "Playback 3 (Super PC)",
        ),
    ],
)
async def test_friendly_name(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    device_values,
    expected,
) -> None:
    """Test friendly name setup."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3, **device_values)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    state = hass.states.get("switch.hdmi_3")
    assert state.attributes["friendly_name"] == expected


@pytest.mark.parametrize(
    ("device_values", "expected_attributes"),
    [
        (
            {"physical_address": PhysicalAddress("3.0.0.0")},
            {"physical_address": "3.0.0.0"},
        ),
        pytest.param(
            {},
            {},
            marks=pytest.mark.xfail(
                reason="physical address logic returns a string 'None' instead of not being set."
            ),
        ),
        (
            {"physical_address": PhysicalAddress("3.0.0.0"), "vendor_id": 5},
            {"physical_address": "3.0.0.0", "vendor_id": 5, "vendor_name": None},
        ),
        (
            {
                "physical_address": PhysicalAddress("3.0.0.0"),
                "vendor_id": 5,
                "vendor": "Samsung",
            },
            {"physical_address": "3.0.0.0", "vendor_id": 5, "vendor_name": "Samsung"},
        ),
        (
            {"physical_address": PhysicalAddress("3.0.0.0"), "type": 1},
            {"physical_address": "3.0.0.0", "type_id": 1, "type": None},
        ),
        (
            {
                "physical_address": PhysicalAddress("3.0.0.0"),
                "type": 1,
                "type_name": "TV",
            },
            {"physical_address": "3.0.0.0", "type_id": 1, "type": "TV"},
        ),
    ],
)
async def test_extra_state_attributes(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    device_values,
    expected_attributes,
) -> None:
    """Test extra state attributes."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3, **device_values)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    state = hass.states.get("switch.hdmi_3")
    attributes = state.attributes
    # We don't care about these attributes, so just copy them to the expected attributes
    for att in ("friendly_name", "icon"):
        expected_attributes[att] = attributes[att]
    assert attributes == expected_attributes


@pytest.mark.parametrize(
    ("device_type", "expected_icon"),
    [
        (None, "mdi:help"),
        (0, "mdi:television"),
        (1, "mdi:microphone"),
        (2, "mdi:help"),
        (3, "mdi:radio"),
        (4, "mdi:play"),
        (5, "mdi:speaker"),
    ],
)
async def test_icon(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
    device_type,
    expected_icon,
) -> None:
    """Test icon selection."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3, type=device_type)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    state = hass.states.get("switch.hdmi_3")
    assert state.attributes["icon"] == expected_icon


async def test_unavailable_status(
    hass: HomeAssistant,
    create_hdmi_network: HDMINetworkCreator,
    create_cec_entity: CecEntityCreator,
) -> None:
    """Test entity goes into unavailable status when expected."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    hass.bus.async_fire(EVENT_HDMI_CEC_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get("switch.hdmi_3")
    assert state.state == STATE_UNAVAILABLE
