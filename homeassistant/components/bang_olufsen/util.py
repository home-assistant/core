"""Various utilities for the Bang & Olufsen integration."""

from __future__ import annotations

from typing import cast

from mozart_api.models import PairedRemote
from mozart_api.mozart_client import MozartClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    BEO_REMOTE_CONTROL_KEYS,
    BEO_REMOTE_KEYS,
    BEO_REMOTE_SUBMENU_CONTROL,
    BEO_REMOTE_SUBMENU_LIGHT,
    DEVICE_BUTTONS,
    DOMAIN,
    BeoButtons,
    BeoModel,
)


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


def get_device_buttons(model: BeoModel) -> list[str]:
    """Get supported buttons for a given model."""
    # Beoconnect Core does not have any buttons
    if model == BeoModel.BEOCONNECT_CORE:
        return []

    buttons = DEVICE_BUTTONS.copy()

    # Models that don't have a microphone button
    if model in (
        BeoModel.BEOSOUND_A5,
        BeoModel.BEOSOUND_A9,
        BeoModel.BEOSOUND_PREMIERE,
    ):
        buttons.remove(BeoButtons.MICROPHONE)

    # Models that don't have a Bluetooth button
    if model in (
        BeoModel.BEOSOUND_A9,
        BeoModel.BEOSOUND_PREMIERE,
    ):
        buttons.remove(BeoButtons.BLUETOOTH)

    return buttons


def get_remote_keys() -> list[str]:
    """Get remote keys for the Beoremote One. Formatted for Home Assistant use."""
    return [
        *[f"{BEO_REMOTE_SUBMENU_LIGHT}/{key_type}" for key_type in BEO_REMOTE_KEYS],
        *[
            f"{BEO_REMOTE_SUBMENU_CONTROL}/{key_type}"
            for key_type in (*BEO_REMOTE_KEYS, *BEO_REMOTE_CONTROL_KEYS)
        ],
    ]
