"""Test the myStrom init."""
from unittest.mock import patch

from homeassistant.components.mystrom.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant

from .conftest import ResponseMock

from tests.common import MockConfigEntry

DEVICE_NAME = "test-myStrom Device"

ENTRY_ID = "uuid"


async def init_integration(hass, platform, device_type, bulb_type="strip"):
    """Inititialize integration for testing."""
    with patch("homeassistant.components.mystrom.PLATFORMS", [platform]), patch(
        "homeassistant.components.mystrom.get_device_info",
        return_value={"type": device_type, "mac": "AB:CD:EF:AB:CD:EF"},
    ), patch("pymystrom.switch.MyStromSwitch.get_state", return_value={}), patch(
        "pymystrom.bulb.MyStromBulb.get_state", return_value={}
    ), patch(
        "pymystrom.bulb.MyStromBulb.bulb_type", bulb_type
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id=ENTRY_ID,
            unique_id="uuid",
            data={
                CONF_HOST: "1.1.1.1",
                CONF_NAME: "test",
            },
            title="myStrom",
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED


async def test_init_switch(hass: HomeAssistant) -> None:
    """Test the initialization of a myStrom switch."""
    await init_integration(hass, Platform.SWITCH, 101)
    state = hass.states.get("switch.test")
    assert state is not None


async def test_init_bulb(hass: HomeAssistant) -> None:
    """Test the initialization of a myStrom bulb."""
    await init_integration(hass, Platform.LIGHT, 102)
    state = hass.states.get("light.test")
    assert state is not None


async def test_init_of_unknown_bulb(hass: HomeAssistant) -> None:
    """Test the initialization of a unknown myStrom bulb."""
    await init_integration(hass, Platform.LIGHT, 102, "new_type")
    state = hass.states.get("light.test")
    assert state is None


async def test_unload(hass: HomeAssistant) -> None:
    """Test the unloading of a myStrom witch."""
    await init_integration(hass, Platform.SWITCH, 101)
    await hass.config_entries.async_unload(ENTRY_ID)
    await hass.async_block_till_done()
    state = hass.states.get("switch.test")
    assert state is None


async def test_init_cannot_connect(hass: HomeAssistant) -> None:
    """Inititialize integration for testing."""
    with patch("homeassistant.components.mystrom.PLATFORMS", [Platform.SWITCH]), patch(
        "aiohttp.ClientSession.get", return_value=ResponseMock({"type": 101}, 400)
    ), patch("pymystrom.switch.MyStromSwitch.get_state", return_value={}), patch(
        "pymystrom.bulb.MyStromBulb.get_state", return_value={}
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id=ENTRY_ID,
            unique_id="uuid",
            data={
                CONF_HOST: "1.1.1.1",
                CONF_NAME: "test",
            },
            title="myStrom",
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY
