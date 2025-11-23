"""Various utilities for the Bang & Olufsen integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DEVICE_BUTTONS, DOMAIN, BangOlufsenButtons, BangOlufsenModel


def get_device(hass: HomeAssistant, unique_id: str) -> DeviceEntry:
    """Get the device."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, unique_id)})
    assert device

    return device


def get_serial_number_from_jid(jid: str) -> str:
    """Get serial number from Beolink JID."""
    return jid.split(".")[2].split("@")[0]


def get_device_buttons(model: BangOlufsenModel) -> list[str]:
    """Get supported buttons for a given model."""
    buttons = DEVICE_BUTTONS.copy()

    # Beosound Premiere does not have a bluetooth button
    if model == BangOlufsenModel.BEOSOUND_PREMIERE:
        buttons.remove(BangOlufsenButtons.BLUETOOTH)

    # Beoconnect Core does not have any buttons
    elif model == BangOlufsenModel.BEOCONNECT_CORE:
        buttons = []

    return buttons
