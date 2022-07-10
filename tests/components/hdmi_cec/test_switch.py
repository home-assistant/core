"""Tests for the HDMI-CEC switch platform."""
from unittest.mock import Mock

import pytest

from homeassistant.components.hdmi_cec import (
    DOMAIN,
    EVENT_HDMI_CEC_UNAVAILABLE,
    POWER_OFF,
    POWER_ON,
    STATUS_PLAY,
    STATUS_STILL,
    STATUS_STOP,
    PhysicalAddress,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.setup import async_setup_component


class MockHDMIDevice:
    """Mock of a HDMIDevice."""

    turn_on = Mock()
    turn_off = Mock()

    def __init__(self, *, logical_address, **values):
        """Mock of a HDMIDevice."""
        super().__setattr__(
            "set_update_callback", Mock(side_effect=self._set_update_callback)
        )
        super().__setattr__("logical_address", logical_address)
        super().__setattr__("name", f"hdmi_{logical_address:x}")
        if "power_status" not in values:
            # Default to invalid state.
            values["power_status"] = -1
        super().__setattr__("_values", values)

    def __getattr__(self, name):
        """Get attribute from `_values` if not explicitly set."""
        return self._values.get(name)

    def __setattr__(self, name, value):
        """Set attributes in `_values` if not one of the known attributes."""
        if name in ("logical_address", "name", "_values", "_update"):
            raise AttributeError("can't set attribute")
        self._values[name] = value
        self._update()

    def _set_update_callback(self, update):
        super().__setattr__("_update", update)


async def test_switch_on_off(hass, create_hdmi_network, create_cec_entity):
    """Test that switch triggers on & off commands."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3)
    await create_cec_entity(hdmi_network, mock_hdmi_device)
    mock_hdmi_device.set_update_callback.assert_called_once()

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "switch.hdmi_3"}, blocking=True
    )

    mock_hdmi_device.turn_on.assert_called_once_with()

    state = hass.states.get("switch.hdmi_3")
    assert state.state == STATE_ON

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
    "power_status,expected_state",
    [(3, STATE_OFF), (POWER_OFF, STATE_OFF), (4, STATE_ON), (POWER_ON, STATE_ON)],
)
@pytest.mark.parametrize(
    "status",
    [
        None,
        pytest.param(
            STATUS_PLAY,
            marks=pytest.mark.xfail(
                reason="`CecSwitchEntity.is_on` returns `False` here instead of the correct state."
            ),
        ),
        pytest.param(
            STATUS_STOP,
            marks=pytest.mark.xfail(
                reason="`CecSwitchEntity.is_on` returns `False` here instead of the correct state."
            ),
        ),
        pytest.param(
            STATUS_STILL,
            marks=pytest.mark.xfail(
                reason="`CecSwitchEntity.is_on` returns `False` here instead of the correct state."
            ),
        ),
    ],
)
async def test_device_status_change(
    hass, create_hdmi_network, create_cec_entity, power_status, expected_state, status
):
    """Test state change on device status change."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3, status=status)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    mock_hdmi_device.power_status = power_status
    await hass.async_block_till_done()

    state = hass.states.get("switch.hdmi_3")
    assert state.state == expected_state


@pytest.mark.parametrize(
    "device_values, expected",
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
    hass, create_hdmi_network, create_cec_entity, device_values, expected
):
    """Test friendly name setup."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3, **device_values)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    state = hass.states.get("switch.hdmi_3")
    assert state.attributes["friendly_name"] == expected


@pytest.mark.parametrize(
    "device_values,expected_attributes",
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
    hass, create_hdmi_network, create_cec_entity, device_values, expected_attributes
):
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
    "device_type,expected_icon",
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
    hass, create_hdmi_network, create_cec_entity, device_type, expected_icon
):
    """Test icon selection."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3, type=device_type)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    state = hass.states.get("switch.hdmi_3")
    assert state.attributes["icon"] == expected_icon


@pytest.mark.xfail(
    reason="The code only sets the state to unavailable, doesn't set the `_attr_available` to false."
)
async def test_unavailable_status(hass, create_hdmi_network, create_cec_entity):
    """Test entity goes into unavailable status when expected."""
    hdmi_network = await create_hdmi_network()
    mock_hdmi_device = MockHDMIDevice(logical_address=3)
    await create_cec_entity(hdmi_network, mock_hdmi_device)

    state = hass.states.get("switch.hdmi_3")
    print(state)
    mock_hdmi_device._update()
    import asyncio

    await asyncio.sleep(2)
    hass.bus.async_fire(EVENT_HDMI_CEC_UNAVAILABLE)
    mock_hdmi_device._update()
    state = hass.states.get("switch.hdmi_3")
    print(state)
    await hass.async_block_till_done()

    state = hass.states.get("switch.hdmi_3")
    print(state)
    print(dir(state))
    assert state.state == STATE_UNAVAILABLE


@pytest.fixture
def create_hdmi_network(hass, MockHDMINetwork):
    """Create an initialized mock hdmi_network."""

    async def hdmi_network(config=None):
        if not config:
            config = {}
        await async_setup_component(hass, DOMAIN, {DOMAIN: config})

        mock_hdmi_network = MockHDMINetwork.return_value

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        return mock_hdmi_network

    return hdmi_network


@pytest.fixture
def create_cec_entity(hass):
    """Create a CecEntity."""

    async def cec_entity(hdmi_network, device):
        new_device_callback = hdmi_network.set_new_device_callback.call_args.args[0]
        new_device_callback(device)
        await hass.async_block_till_done()

    return cec_entity
