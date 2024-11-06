"""Unit tests for the VegeHub integration's switch.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.vegehub.const import DOMAIN
from homeassistant.components.vegehub.switch import SwitchDeviceClass, VegeHubSwitch
from homeassistant.const import UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from tests.test_util.aiohttp import AiohttpClientMocker

# Constants for the tests
CONFIG_ENTRY_DATA = {
    "mac_address": "AABBCCDDEEFF",
    "ip_addr": "192.168.1.10",
    "hostname": "VegeHub 1",
    "hub": {
        "num_channels": 2,
        "num_actuators": 2,
        "is_ac": False,
    },
}
CONFIG_ENTRY_OPTIONS = {"user_act_duration": 1200}


@pytest.fixture
def mock_session():
    """Mock aiohttp.ClientSession."""
    mocker = AiohttpClientMocker()

    with patch(
        "aiohttp.ClientSession",
        side_effect=lambda *args, **kwargs: mocker.create_session(
            asyncio.get_event_loop()
        ),
    ):
        yield mocker


@pytest.fixture
def mock_config_entry():
    """Fixture for a mock config entry."""
    config_entry = AsyncMock()
    config_entry.data = CONFIG_ENTRY_DATA
    config_entry.options = CONFIG_ENTRY_OPTIONS
    return config_entry


@pytest.fixture
def hass():
    """Mock a HomeAssistant instance."""
    hass_mock = MagicMock()
    hass_mock.data = {DOMAIN: {}}
    return hass_mock


@pytest.fixture
def vegehub_switch(hass: HomeAssistant, mock_config_entry):
    """Fixture for initializing the VegeHubSwitch."""

    switch = VegeHubSwitch(
        name="VegeHub Actuator 1",
        sens_slot=3,
        act_slot=1,
        config_entry=mock_config_entry,
    )
    switch.hass = hass
    return switch


def test_switch_attributes(vegehub_switch) -> None:
    """Test that VegeHubSwitch has correct attributes."""
    assert vegehub_switch.name == "VegeHub Actuator 1"
    assert vegehub_switch.device_class == SwitchDeviceClass.SWITCH
    assert vegehub_switch.native_unit_of_measurement == UnitOfElectricPotential.VOLT
    assert vegehub_switch.unique_id == "vegehub_aabbccddeeff_3"


def test_device_info(vegehub_switch) -> None:
    """Test that device info is correctly set."""
    assert vegehub_switch.device_info == DeviceInfo(
        identifiers={("vegehub", "AABBCCDDEEFF")},
        name="VegeHub 1",
        manufacturer="vegetronix",
        model="VegeHub",
    )


def test_user_duration(vegehub_switch) -> None:
    """Test user duration retrieval."""
    assert vegehub_switch.user_duration == 1200


@pytest.mark.asyncio
async def test_turn_on_off(vegehub_switch, mock_session) -> None:
    """Test turning the switch on and off."""
    mock_session.post(
        "http://192.168.1.10/api/actuators/set",
        status=200,
        text="",
    )

    assert vegehub_switch.is_on is False

    # Test turning on the switch
    vegehub_switch.turn_on()
    vegehub_switch._state = 1
    assert vegehub_switch.is_on is True

    # Test turning off the switch
    vegehub_switch.turn_off()
    vegehub_switch._state = 0
    assert vegehub_switch.is_on is False


@pytest.mark.asyncio
async def test_set_actuator_failure(vegehub_switch, mock_session) -> None:
    """Test that setting actuator fails on non-200 response."""
    mock_session.post(
        "http://192.168.1.10/api/actuators/set",
        status=404,
        text="",
    )

    with pytest.raises(ConnectionError):
        await vegehub_switch._set_actuator(1)


@pytest.mark.asyncio
async def test_update_sensor(vegehub_switch) -> None:
    """Test updating the sensor state."""
    with patch.object(vegehub_switch, "async_write_ha_state") as mock_write_ha_state:
        await vegehub_switch.async_update_sensor(5)
        assert vegehub_switch._state == 5
        mock_write_ha_state.assert_called_once()
