"""Test the myStrom init."""
from unittest.mock import AsyncMock, PropertyMock, patch

from pymystrom.exceptions import MyStromConnectionError

from homeassistant.components.mystrom.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import DEVICE_MAC

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_type: int,
    bulb_type: str = "strip",
) -> None:
    """Inititialize integration for testing."""
    with patch(
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
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED


async def test_init_switch_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the initialization of a myStrom switch."""
    await init_integration(hass, config_entry, 101)
    state = hass.states.get("switch.mystrom_device")
    assert state is not None
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_init_bulb(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the initialization of a myStrom bulb."""
    await init_integration(hass, config_entry, 102)
    state = hass.states.get("light.mystrom_device")
    assert state is not None
    assert config_entry.state is ConfigEntryState.LOADED


async def test_init_of_unknown_bulb(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the initialization of a unknown myStrom bulb."""
    with patch(
        "pymystrom.get_device_info",
        side_effect=AsyncMock(return_value={"type": 102, "mac": DEVICE_MAC}),
    ), patch("pymystrom.bulb.MyStromBulb.get_state", return_value={}), patch(
        "pymystrom.bulb.MyStromBulb.bulb_type", "new_type"
    ), patch(
        "pymystrom.bulb.MyStromBulb.mac",
        new_callable=PropertyMock,
        return_value=DEVICE_MAC,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_init_of_unknown_device(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the initialization of a unsupported myStrom device."""
    with patch(
        "pymystrom.get_device_info",
        side_effect=AsyncMock(return_value={"type": 103, "mac": DEVICE_MAC}),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_init_cannot_connect_because_of_device_info(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test error handling for failing get_device_info."""
    with patch(
        "pymystrom.get_device_info",
        side_effect=MyStromConnectionError(),
    ), patch("pymystrom.switch.MyStromSwitch.get_state", return_value={}), patch(
        "pymystrom.bulb.MyStromBulb.get_state", return_value={}
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_init_cannot_connect_because_of_get_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test error handling for failing get_state."""
    with patch(
        "pymystrom.get_device_info",
        side_effect=AsyncMock(return_value={"type": 101, "mac": DEVICE_MAC}),
    ), patch(
        "pymystrom.switch.MyStromSwitch.get_state", side_effect=MyStromConnectionError()
    ), patch(
        "pymystrom.bulb.MyStromBulb.get_state", side_effect=MyStromConnectionError()
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_ERROR
