"""Test the Home Assistant Yellow integration helpers."""

from __future__ import annotations

import contextlib
import typing
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.homeassistant_yellow.helpers import (
    YellowGPIO,
    async_validate_gpio_states,
    async_validate_hardware_consistent,
    validate_usb_hub_present,
)
from homeassistant.core import HomeAssistant

if typing.TYPE_CHECKING:
    import gpiod


@contextlib.contextmanager
def mock_gpio_pin_states(pin_states: dict[int, list[bool]]):
    """Mock the GPIO pin read function."""

    read_count = 0

    def mock_get_lines(pins: list[int]):
        def mock_get_values() -> list[gpiod.line.Value]:
            nonlocal read_count

            values = [pin_states[pin][read_count] for pin in pins]
            read_count += 1

            return values

        mock = MagicMock()
        mock.get_values.side_effect = mock_get_values

        return mock

    mock_gpiod = MagicMock()
    mock_gpiod.chip.return_value.get_lines = MagicMock(side_effect=mock_get_lines)

    with patch.dict("sys.modules", gpiod=mock_gpiod):
        yield


@pytest.mark.parametrize(
    ("states", "result"),
    [
        (
            # Normal
            {
                YellowGPIO.RADIO_BOOT: [1, 1, 1, 1, 1],
                YellowGPIO.RADIO_RESET: [1, 1, 1, 1, 1],
            },
            True,
        ),
        (
            # Unstable
            {
                YellowGPIO.RADIO_BOOT: [1, 1, 0, 1, 1],
                YellowGPIO.RADIO_RESET: [1, 1, 1, 1, 1],
            },
            False,
        ),
        (
            # Stable but inverted
            {
                YellowGPIO.RADIO_BOOT: [0, 0, 0, 0, 0],
                YellowGPIO.RADIO_RESET: [0, 0, 0, 0, 0],
            },
            False,
        ),
        (
            # Half stable but inverted
            {
                YellowGPIO.RADIO_BOOT: [1, 1, 1, 1, 1],
                YellowGPIO.RADIO_RESET: [0, 0, 0, 0, 0],
            },
            False,
        ),
    ],
)
async def test_validate_gpio_pins(
    states: dict[YellowGPIO, list[int]], result: bool, hass: HomeAssistant
) -> None:
    """Test validating GPIO pin states, success."""
    with mock_gpio_pin_states(states):
        assert (await async_validate_gpio_states(hass)) == result


@pytest.mark.parametrize(
    ("find_result", "result"),
    [
        (["hub1", "hub2"], True),
        (["hub1", None], False),
        ([None], False),
    ],
)
def test_validate_usb_hub_present(find_result: list[bool], result: bool) -> None:
    """Test validating USB hubs."""
    with patch(
        "homeassistant.components.homeassistant_yellow.helpers.usb.core.find",
        side_effect=find_result,
    ):
        assert validate_usb_hub_present() is result


@pytest.mark.parametrize(
    ("hub_present", "gpio_valid", "result"),
    [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ],
)
async def test_async_validate_hardware_consistent(
    hub_present: bool, gpio_valid: bool, result: bool, hass: HomeAssistant
) -> None:
    """Test validating hardware consistency."""
    with (
        patch(
            "homeassistant.components.homeassistant_yellow.helpers.validate_usb_hub_present",
            return_value=hub_present,
        ),
        patch(
            "homeassistant.components.homeassistant_yellow.helpers.async_validate_gpio_states",
            return_value=gpio_valid,
        ),
    ):
        assert (await async_validate_hardware_consistent(hass)) is result
