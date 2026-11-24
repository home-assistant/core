"""Test the LED BLE light platform."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.led_ble.const import DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_ADDRESS, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from . import LED_BLE_DISCOVERY_INFO

ENTITY_ID = "light.triones_f30200000152c"


@pytest.fixture
def mock_device() -> MagicMock:
    """Return a mocked LEDBLE device that is currently off."""
    device = MagicMock()
    device.name = "Triones:F30200000152C"
    device.address = LED_BLE_DISCOVERY_INFO.address
    device.on = False
    device.w = None
    device.brightness = 255
    device.rgb_unscaled = (255, 255, 255)
    device.effect = None
    device.effect_list = []
    device.speed = None
    device.update = AsyncMock()
    device.stop = AsyncMock()
    device.turn_on = AsyncMock()
    device.turn_off = AsyncMock()
    device.set_rgb = AsyncMock()
    device.set_brightness = AsyncMock()

    def _register_callback(callback: Callable[..., None]) -> Callable[[], None]:
        # Report a first state straight away so setup does not wait for it.
        callback(MagicMock())
        return lambda: None

    device.register_callback.side_effect = _register_callback
    return device


@pytest.fixture
async def setup_entry(hass: HomeAssistant, mock_device: MagicMock) -> None:
    """Set up the integration with the mocked device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=LED_BLE_DISCOVERY_INFO.address,
        data={CONF_ADDRESS: LED_BLE_DISCOVERY_INFO.address},
        title="Triones:F30200000152C",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.led_ble.bluetooth.async_ble_device_from_address",
            return_value=LED_BLE_DISCOVERY_INFO.device,
        ),
        patch("homeassistant.components.led_ble.LEDBLE", return_value=mock_device),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.mark.usefixtures("setup_entry")
@pytest.mark.parametrize(
    ("service_data", "write_method"),
    [
        ({ATTR_BRIGHTNESS: 38}, "set_brightness"),
        ({ATTR_RGB_COLOR: (255, 0, 0), ATTR_BRIGHTNESS: 38}, "set_rgb"),
    ],
)
async def test_turn_on_with_data_powers_on_first_when_off(
    hass: HomeAssistant,
    mock_device: MagicMock,
    service_data: dict[str, Any],
    write_method: str,
) -> None:
    """Test colour and brightness commands power on a device that is off.

    The device ignores colour and brightness writes while it is off.
    """
    calls = MagicMock()
    calls.attach_mock(mock_device.turn_on, "turn_on")
    calls.attach_mock(getattr(mock_device, write_method), write_method)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    assert [call[0] for call in calls.mock_calls] == ["turn_on", write_method]


@pytest.mark.usefixtures("setup_entry")
async def test_turn_on_with_data_does_not_repeat_power_on_when_on(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test a device that is already on is not sent an extra power on."""
    mock_device.on = True

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 38},
        blocking=True,
    )

    mock_device.turn_on.assert_not_called()
    mock_device.set_brightness.assert_awaited_once_with(38)


@pytest.mark.usefixtures("setup_entry")
async def test_plain_turn_on_powers_on_once(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test a plain turn on sends a single power on."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_device.turn_on.assert_awaited_once_with()
