"""The iCloud component."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from .account import IcloudAccount
from .const import (
    ATTR_ACCOUNT,
    ATTR_DEVICE_NAME,
    ATTR_LOST_DEVICE_MESSAGE,
    ATTR_LOST_DEVICE_NUMBER,
    ATTR_LOST_DEVICE_SOUND,
    DOMAIN,
)

# services
SERVICE_ICLOUD_PLAY_SOUND = "play_sound"
SERVICE_ICLOUD_DISPLAY_MESSAGE = "display_message"
SERVICE_ICLOUD_LOST_DEVICE = "lost_device"
SERVICE_ICLOUD_UPDATE = "update"

SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ACCOUNT): cv.string})

SERVICE_SCHEMA_PLAY_SOUND = vol.Schema(
    {vol.Required(ATTR_ACCOUNT): cv.string, vol.Required(ATTR_DEVICE_NAME): cv.string}
)

SERVICE_SCHEMA_DISPLAY_MESSAGE = vol.Schema(
    {
        vol.Required(ATTR_ACCOUNT): cv.string,
        vol.Required(ATTR_DEVICE_NAME): cv.string,
        vol.Required(ATTR_LOST_DEVICE_MESSAGE): cv.string,
        vol.Optional(ATTR_LOST_DEVICE_SOUND): cv.boolean,
    }
)

SERVICE_SCHEMA_LOST_DEVICE = vol.Schema(
    {
        vol.Required(ATTR_ACCOUNT): cv.string,
        vol.Required(ATTR_DEVICE_NAME): cv.string,
        vol.Required(ATTR_LOST_DEVICE_NUMBER): cv.string,
        vol.Required(ATTR_LOST_DEVICE_MESSAGE): cv.string,
    }
)


def play_sound(service: ServiceCall) -> None:
    """Play sound on the device."""
    account = service.data[ATTR_ACCOUNT]
    device_name: str = service.data[ATTR_DEVICE_NAME]
    device_name = slugify(device_name.replace(" ", "", 99))

    for device in _get_account(service.hass, account).get_devices_with_name(
        device_name
    ):
        device.play_sound()


def display_message(service: ServiceCall) -> None:
    """Display a message on the device."""
    account = service.data[ATTR_ACCOUNT]
    device_name: str = service.data[ATTR_DEVICE_NAME]
    device_name = slugify(device_name.replace(" ", "", 99))
    message = service.data.get(ATTR_LOST_DEVICE_MESSAGE)
    sound = service.data.get(ATTR_LOST_DEVICE_SOUND, False)

    for device in _get_account(service.hass, account).get_devices_with_name(
        device_name
    ):
        device.display_message(message, sound)


def lost_device(service: ServiceCall) -> None:
    """Make the device in lost state."""
    account = service.data[ATTR_ACCOUNT]
    device_name: str = service.data[ATTR_DEVICE_NAME]
    device_name = slugify(device_name.replace(" ", "", 99))
    number = service.data.get(ATTR_LOST_DEVICE_NUMBER)
    message = service.data.get(ATTR_LOST_DEVICE_MESSAGE)

    for device in _get_account(service.hass, account).get_devices_with_name(
        device_name
    ):
        device.lost_device(number, message)


def update_account(service: ServiceCall) -> None:
    """Call the update function of an iCloud account."""
    if (account := service.data.get(ATTR_ACCOUNT)) is None:
        for account in service.hass.data[DOMAIN].values():
            account.keep_alive()
    else:
        _get_account(service.hass, account).keep_alive()


def _get_account(hass: HomeAssistant, account_identifier: str) -> IcloudAccount:
    if account_identifier is None:
        return None

    icloud_account: IcloudAccount | None = hass.data[DOMAIN].get(account_identifier)
    if icloud_account is None:
        for account in hass.data[DOMAIN].values():
            if account.username == account_identifier:
                icloud_account = account

    if icloud_account is None:
        raise ValueError(
            f"No iCloud account with username or name {account_identifier}"
        )
    return icloud_account


def register_services(hass: HomeAssistant) -> None:
    """Set up an iCloud account from a config entry."""

    hass.services.async_register(
        DOMAIN, SERVICE_ICLOUD_PLAY_SOUND, play_sound, schema=SERVICE_SCHEMA_PLAY_SOUND
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ICLOUD_DISPLAY_MESSAGE,
        display_message,
        schema=SERVICE_SCHEMA_DISPLAY_MESSAGE,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ICLOUD_LOST_DEVICE,
        lost_device,
        schema=SERVICE_SCHEMA_LOST_DEVICE,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_ICLOUD_UPDATE, update_account, schema=SERVICE_SCHEMA
    )
