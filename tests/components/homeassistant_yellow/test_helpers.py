"""Test the Home Assistant Yellow integration helpers."""

from __future__ import annotations

import contextlib
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.homeassistant_yellow.helpers import (
    YellowGPIO,
    async_validate_gpio_states,
    async_validate_hardware_consistent,
    validate_usb_hub_present,
)
from homeassistant.core import HomeAssistant


@contextlib.contextmanager
def mock_gpio_pin_states(pin_states: dict[int, list[bool]]):
    """Mock the GPIO pin read function."""

    # pylint: disable-next=import-outside-toplevel
    from gpiod.line import Value

    # pylint: disable-next=import-outside-toplevel
    from gpiod.line_request import LineRequest

    read_count = 0

    def mock_request_lines(
        path: str, consumer: str, config: dict[int, Any]
    ) -> MagicMock:
        def mock_get_values() -> list[Value]:
            nonlocal read_count

            values = [
                Value.ACTIVE if pin_states[pin][read_count] else Value.INACTIVE
                for pin, _ in config.items()
            ]
            read_count += 1

            return values

        mock_line_request = MagicMock(autospec=LineRequest(None))
        mock_line_request.__enter__.return_value = mock_line_request
        mock_line_request.get_values.side_effect = mock_get_values

        return mock_line_request

    with patch("gpiod.request_lines", autospec=True, side_effect=mock_request_lines):
        yield


@pytest.mark.skipif(sys.platform != "linux", reason="gpiod requires linux")
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
