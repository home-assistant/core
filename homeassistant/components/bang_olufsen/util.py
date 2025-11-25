"""Various utilities for the Bang & Olufsen integration."""

from __future__ import annotations

from typing import cast

from mozart_api.models import PairedRemote
from mozart_api.mozart_client import MozartClient

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


async def get_remotes(client: MozartClient) -> list[PairedRemote]:
    """Get paired remotes."""

    bluetooth_remote_list = await client.get_bluetooth_remotes()

    return [
        remote
        for remote in cast(list[PairedRemote], bluetooth_remote_list.items)
        if remote.serial_number is not None
    ]


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
