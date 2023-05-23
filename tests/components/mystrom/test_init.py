"""Test the myStrom init."""
from unittest.mock import AsyncMock, PropertyMock, patch

from pymystrom.exceptions import MyStromConnectionError

from homeassistant.components.mystrom.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_NAME = "test-myStrom Device"

ENTRY_ID = "uuid"
DEVICE_MAC = "6001940376EB"
DEVICE_NAME = "6001940376eb"


async def init_integration(hass, platform, device_type, bulb_type="strip"):
    """Inititialize integration for testing."""
    with patch("homeassistant.components.mystrom.PLATFORMS", [platform]), patch(
        "pymystrom.get_device_info",
        side_effect=AsyncMock(return_value={"type": device_type, "mac": DEVICE_MAC}),
    ), patch("pymystrom.switch.MyStromSwitch.get_state", return_value={}), patch(
        "pymystrom.bulb.MyStromBulb.get_state", return_value={}
    ), patch(
        "pymystrom.bulb.MyStromBulb.bulb_type", bulb_type
    ), patch(
        "pymystrom.switch.MyStromSwitch.mac",
        new_callable=PropertyMock,
        return_value=DEVICE_MAC,
    ), patch(
        "pymystrom.bulb.MyStromBulb.mac",
        new_callable=PropertyMock,
        return_value=DEVICE_MAC,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id=ENTRY_ID,
            unique_id="uuid",
            data={CONF_HOST: "1.1.1.1"},
            title="myStrom",
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED


async def test_init_switch(hass: HomeAssistant) -> None:
    """Test the initialization of a myStrom switch."""
    await init_integration(hass, Platform.SWITCH, 101)
    state = hass.states.get("switch." + DEVICE_NAME)
    assert state is not None


async def test_init_bulb(hass: HomeAssistant) -> None:
    """Test the initialization of a myStrom bulb."""
    await init_integration(hass, Platform.LIGHT, 102)
    state = hass.states.get("light." + DEVICE_NAME)
    assert state is not None


async def test_init_of_unknown_bulb(hass: HomeAssistant) -> None:
    """Test the initialization of a unknown myStrom bulb."""
    with patch("homeassistant.components.mystrom.PLATFORMS", [Platform.LIGHT]), patch(
        "pymystrom.get_device_info",
        side_effect=AsyncMock(return_value={"type": 102, "mac": DEVICE_MAC}),
    ), patch("pymystrom.bulb.MyStromBulb.get_state", return_value={}), patch(
        "pymystrom.bulb.MyStromBulb.bulb_type", "new_type"
    ), patch(
        "pymystrom.bulb.MyStromBulb.mac",
        new_callable=PropertyMock,
        return_value=DEVICE_MAC,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id=ENTRY_ID,
            unique_id="uuid",
            data={CONF_HOST: "1.1.1.1"},
            title="myStrom",
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_init_of_unknown_device(hass: HomeAssistant) -> None:
    """Test the initialization of a unsupported myStrom device."""
    with patch("homeassistant.components.mystrom.PLATFORMS", [Platform.SWITCH]), patch(
        "pymystrom.get_device_info",
        side_effect=AsyncMock(return_value={"type": 103, "mac": DEVICE_MAC}),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id=ENTRY_ID,
            unique_id="uuid",
            data={CONF_HOST: "1.1.1.1"},
            title="myStrom",
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_ERROR


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
        "pymystrom.get_device_info",
        side_effect=MyStromConnectionError(),
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
