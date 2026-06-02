"""Test the Avea light platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.avea.const import UNKNOWN_NAME
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import AVEA_DISCOVERY_INFO, AVEA_FIRMWARE_VERSION, AVEA_SERIAL_NUMBER

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_bulb() -> MagicMock:
    """Return a mocked Avea bulb."""
    bulb = MagicMock()
    bulb.name = "Unknown"
    bulb.fw_version = "Unknown"
    bulb.hardware_revision = "Unknown"
    bulb.manufacturer_name = "Unknown"
    bulb.serial_number = "Unknown"
    bulb.brightness = 0
    bulb.connect.return_value = True
    bulb.get_brightness.return_value = 0
    bulb.get_fw_version.return_value = AVEA_FIRMWARE_VERSION
    bulb.get_hardware_revision.return_value = "Elgato Avea"
    bulb.get_manufacturer_name.return_value = "Elgato Systems GmbH"
    bulb.get_rgb.return_value = (0, 0, 0)
    bulb.get_serial_number.return_value = AVEA_SERIAL_NUMBER
    return bulb


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bulb: MagicMock,
) -> AsyncGenerator[MagicMock]:
    """Set up the integration."""
    with (
        patch(
            "homeassistant.components.avea.async_ble_device_from_address",
            return_value=AVEA_DISCOVERY_INFO.device,
        ),
        patch("homeassistant.components.avea.avea.Bulb", return_value=mock_bulb),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_bulb


async def test_init_state(
    hass: HomeAssistant,
    setup_integration: MagicMock,
) -> None:
    """Test the initial state."""
    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.name == "Bedroom"
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.HS]


async def test_device_info(
    device_registry: dr.DeviceRegistry,
    setup_integration: MagicMock,
) -> None:
    """Test the device info."""
    bulb = setup_integration
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_BLUETOOTH, AVEA_DISCOVERY_INFO.address)},
    )

    assert device is not None
    assert device.name == "Bedroom"
    assert device.manufacturer == "Elgato Systems GmbH"
    assert device.model == "Avea"
    assert device.hw_version == "Elgato Avea"
    assert device.sw_version == AVEA_FIRMWARE_VERSION
    assert device.serial_number == AVEA_SERIAL_NUMBER
    bulb.get_manufacturer_name.assert_called_once()
    bulb.get_hardware_revision.assert_called_once()
    bulb.get_fw_version.assert_called_once()
    bulb.get_serial_number.assert_called_once()


async def test_device_info_populates_when_connect_fails(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_bulb: MagicMock,
) -> None:
    """Test device info is populated when the shared connection fails."""
    mock_bulb.connect.return_value = False

    with (
        patch(
            "homeassistant.components.avea.async_ble_device_from_address",
            return_value=AVEA_DISCOVERY_INFO.device,
        ),
        patch("homeassistant.components.avea.avea.Bulb", return_value=mock_bulb),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_bulb.connect.assert_called_once()
    mock_bulb.get_manufacturer_name.assert_called_once()
    mock_bulb.get_hardware_revision.assert_called_once()
    mock_bulb.get_fw_version.assert_called_once()
    mock_bulb.get_serial_number.assert_called_once()
    mock_bulb.disconnect.assert_not_called()

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_BLUETOOTH, AVEA_DISCOVERY_INFO.address)},
    )

    assert device is not None
    assert device.manufacturer == "Elgato Systems GmbH"
    assert device.model == "Avea"
    assert device.hw_version == "Elgato Avea"
    assert device.sw_version == AVEA_FIRMWARE_VERSION
    assert device.serial_number == AVEA_SERIAL_NUMBER


async def test_device_info_ignores_unknown_values(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_bulb: MagicMock,
) -> None:
    """Test unknown device info is not populated."""
    mock_bulb.get_manufacturer_name.return_value = UNKNOWN_NAME
    mock_bulb.get_hardware_revision.return_value = ""
    mock_bulb.get_fw_version.return_value = UNKNOWN_NAME
    mock_bulb.get_serial_number.return_value = ""

    with (
        patch(
            "homeassistant.components.avea.async_ble_device_from_address",
            return_value=AVEA_DISCOVERY_INFO.device,
        ),
        patch("homeassistant.components.avea.avea.Bulb", return_value=mock_bulb),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_BLUETOOTH, AVEA_DISCOVERY_INFO.address)},
    )

    assert device is not None
    assert device.manufacturer is None
    assert device.model == "Avea"
    assert device.hw_version is None
    assert device.sw_version is None
    assert device.serial_number is None


async def test_device_info_is_read_once(
    hass: HomeAssistant,
    setup_integration: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device info is read once."""
    bulb = setup_integration
    bulb.get_manufacturer_name.reset_mock()
    bulb.get_hardware_revision.reset_mock()
    bulb.get_fw_version.reset_mock()
    bulb.get_serial_number.reset_mock()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    bulb.get_manufacturer_name.assert_not_called()
    bulb.get_hardware_revision.assert_not_called()
    bulb.get_fw_version.assert_not_called()
    bulb.get_serial_number.assert_not_called()


async def test_turn_on_and_off(
    hass: HomeAssistant,
    setup_integration: MagicMock,
) -> None:
    """Test turning the light on and off."""
    bulb = setup_integration

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom"},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(4095)

    bulb.set_brightness.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(2056)

    bulb.set_rgb.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_HS_COLOR: (0, 100)},
        blocking=True,
    )
    bulb.set_rgb.assert_called_with(255, 0, 0)

    bulb.set_brightness.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_off",
        {ATTR_ENTITY_ID: "light.bedroom"},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(0)


async def test_turn_on_restores_last_brightness(
    hass: HomeAssistant,
    setup_integration: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test turning the light on restores the last brightness."""
    bulb = setup_integration

    bulb.get_brightness.side_effect = [3212, None, None, None]

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.attributes[ATTR_BRIGHTNESS] == 200

    bulb.set_brightness.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_BRIGHTNESS: 10},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(161)

    bulb.set_brightness.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_off",
        {ATTR_ENTITY_ID: "light.bedroom"},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(0)

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_BRIGHTNESS] is None

    bulb.set_brightness.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom"},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(161)


async def test_update_state(
    hass: HomeAssistant, setup_integration: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test updating the entity state."""
    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_BRIGHTNESS] is None

    bulb = setup_integration
    bulb.reset_mock()
    bulb.connect.return_value = True
    bulb.get_brightness.return_value = 2048
    bulb.get_rgb.return_value = (0, 255, 0)

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    bulb.connect.assert_called_once()
    bulb.get_brightness.assert_called_once()
    bulb.get_rgb.assert_called_once()
    bulb.disconnect.assert_called_once()

    bulb.assert_has_calls(
        [
            call.connect(),
            call.get_brightness(),
            call.get_rgb(),
            call.disconnect(),
        ]
    )

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_HS_COLOR] == (120.0, 100.0)


async def test_update_state_uses_cached_values_when_connect_fails(
    hass: HomeAssistant, setup_integration: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test updating the entity state when the shared connection fails."""
    bulb = setup_integration
    bulb.reset_mock()
    bulb.connect.return_value = False
    bulb.get_brightness.return_value = 2048
    bulb.get_rgb.return_value = (0, 255, 0)

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    bulb.connect.assert_called_once()
    bulb.get_brightness.assert_called_once()
    bulb.get_rgb.assert_called_once()
    bulb.disconnect.assert_not_called()

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_HS_COLOR] == (120.0, 100.0)
