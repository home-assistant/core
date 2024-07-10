"""Helper functions for the Yellow."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
import enum

import usb

from homeassistant.core import HomeAssistant


class YellowGPIO(enum.IntEnum):
    """Yellow MGM210P GPIO pins."""

    RADIO_SWDIO = 6
    RADIO_SWCLK = 7
    RADIO_TXD = 8
    RADIO_RXD = 9
    RADIO_CTS = 10
    RADIO_RTS = 11
    RADIO_BOOT = 24
    RADIO_RESET = 25
    SW_USER = 26
    SW_WIPE = 27


# Pin states on a properly installed CM4
RUNNING_PIN_STATES = {
    YellowGPIO.RADIO_BOOT: True,
    YellowGPIO.RADIO_RESET: True,
}

GPIO_READ_ATTEMPTS = 5
GPIO_READ_DELAY_S = 0.01


# Bus 001 Device 001: ID 1d6b:0002
CM4_USB_HUB_VENDOR = 0x1D6B
CM4_USB_HUB_PRODUCT = 0x0002

# Bus 001 Device 002: ID 1a40:0101
YELLOW_USB_HUB_VENDOR = 0x1A40
YELLOW_USB_HUB_PRODUCT = 0x0101


def _read_gpio_pins[_PinsT: int](pins: Sequence[_PinsT]) -> dict[_PinsT, bool]:
    """Read the state of the given GPIO pins."""
    # pylint: disable-next=import-outside-toplevel
    import gpiod

    # pylint: disable-next=import-outside-toplevel
    from gpiod.line import Bias, Direction, Value

    with gpiod.request_lines(
        path="/dev/gpiochip0",
        consumer="core-yellow",
        config={
            pin: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.DISABLED)
            for pin in pins
        },
    ) as request:
        return {
            p: (v == Value.ACTIVE)
            for p, v in zip(pins, request.get_values(), strict=True)
        }


async def async_validate_gpio_states(hass: HomeAssistant) -> bool:
    """Validate the state of the GPIO pins."""
    # We read multiple times in a row to make sure the GPIO state isn't fluctuating
    for attempt in range(GPIO_READ_ATTEMPTS):
        if attempt > 0:
            await asyncio.sleep(GPIO_READ_DELAY_S)

        pin_states = await hass.async_add_executor_job(
            _read_gpio_pins, list(RUNNING_PIN_STATES)
        )

        if pin_states != RUNNING_PIN_STATES:
            return False

    return True


def validate_usb_hub_present() -> bool:
    """Validate that the USB hub is present."""
    root_hub = usb.core.find(
        # The root hub has no parent
        parent=None,
        idVendor=CM4_USB_HUB_VENDOR,
        idProduct=CM4_USB_HUB_PRODUCT,
    )

    # This really should not be possible
    if root_hub is None:
        return False

    yellow_hub = usb.core.find(
        # The Yellow's two-port hub is a child of the pi's root hub
        parent=root_hub,
        idVendor=YELLOW_USB_HUB_VENDOR,
        idProduct=YELLOW_USB_HUB_PRODUCT,
    )

    return yellow_hub is not None


async def async_validate_hardware_consistent(hass: HomeAssistant) -> bool:
    """Validate the hardware is consistent with a properly installed CM4."""
    if not await hass.async_add_executor_job(validate_usb_hub_present):
        return False

    if not await async_validate_gpio_states(hass):
        return False

    return True
