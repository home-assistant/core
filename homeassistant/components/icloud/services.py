"""The iCloud component."""

from enum import StrEnum

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from .account import IcloudAccount, IcloudConfigEntry
from .const import DOMAIN


class IcloudService(StrEnum):
    """Store keys for iCloud services."""

    UPDATE = "update"
    PLAY_SOUND = "play_sound"
    DISPLAY_MESSAGE = "display_message"
    LOST_DEVICE = "lost_device"


class IcloudServiceArgument(StrEnum):
    """Store keys for iCloud service arguments."""

    ACCOUNT = "account"
    DEVICE_NAME = "device_name"
    MESSAGE = "message"
    SOUND = "sound"
    NUMBER = "number"


SERVICE_SCHEMA = probatio.Schema(
    {probatio.Optional(IcloudServiceArgument.ACCOUNT): cv.string}
)

SERVICE_SCHEMA_PLAY_SOUND = probatio.Schema(
    {
        probatio.Required(IcloudServiceArgument.ACCOUNT): cv.string,
        probatio.Required(IcloudServiceArgument.DEVICE_NAME): cv.string,
    }
)

SERVICE_SCHEMA_DISPLAY_MESSAGE = probatio.Schema(
    {
        probatio.Required(IcloudServiceArgument.ACCOUNT): cv.string,
        probatio.Required(IcloudServiceArgument.DEVICE_NAME): cv.string,
        probatio.Required(IcloudServiceArgument.MESSAGE): cv.string,
        probatio.Optional(IcloudServiceArgument.SOUND): cv.boolean,
    }
)

SERVICE_SCHEMA_LOST_DEVICE = probatio.Schema(
    {
        probatio.Required(IcloudServiceArgument.ACCOUNT): cv.string,
        probatio.Required(IcloudServiceArgument.DEVICE_NAME): cv.string,
        probatio.Required(IcloudServiceArgument.NUMBER): cv.string,
        probatio.Required(IcloudServiceArgument.MESSAGE): cv.string,
    }
)


def play_sound(service: ServiceCall) -> None:
    """Play sound on the device."""
    account = service.data[IcloudServiceArgument.ACCOUNT]
    device_name: str = service.data[IcloudServiceArgument.DEVICE_NAME]
    device_name = slugify(device_name.replace(" ", "", 99))

    for device in _get_account(service.hass, account).get_devices_with_name(
        device_name
    ):
        device.play_sound()


def display_message(service: ServiceCall) -> None:
    """Display a message on the device."""
    account = service.data[IcloudServiceArgument.ACCOUNT]
    device_name: str = service.data[IcloudServiceArgument.DEVICE_NAME]
    device_name = slugify(device_name.replace(" ", "", 99))
    message = service.data.get(IcloudServiceArgument.MESSAGE)
    sound = service.data.get(IcloudServiceArgument.SOUND, False)

    for device in _get_account(service.hass, account).get_devices_with_name(
        device_name
    ):
        device.display_message(message, sound)


def lost_device(service: ServiceCall) -> None:
    """Make the device in lost state."""
    account = service.data[IcloudServiceArgument.ACCOUNT]
    device_name: str = service.data[IcloudServiceArgument.DEVICE_NAME]
    device_name = slugify(device_name.replace(" ", "", 99))
    number = service.data.get(IcloudServiceArgument.NUMBER)
    message = service.data.get(IcloudServiceArgument.MESSAGE)

    for device in _get_account(service.hass, account).get_devices_with_name(
        device_name
    ):
        device.lost_device(number, message)


def update_account(service: ServiceCall) -> None:
    """Call the update function of an iCloud account."""
    if (account := service.data.get(IcloudServiceArgument.ACCOUNT)) is None:
        # Update all accounts when no specific account is provided
        entry: IcloudConfigEntry
        for entry in service.hass.config_entries.async_loaded_entries(DOMAIN):
            entry.runtime_data.keep_alive()
    else:
        _get_account(service.hass, account).keep_alive()


def _get_account(hass: HomeAssistant, account_identifier: str) -> IcloudAccount:
    if account_identifier is None:
        return None

    entry: IcloudConfigEntry
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if entry.runtime_data.username == account_identifier:
            return entry.runtime_data

    raise ValueError(f"No iCloud account with username or name {account_identifier}")


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register iCloud services."""

    hass.services.async_register(
        DOMAIN, IcloudService.PLAY_SOUND, play_sound, schema=SERVICE_SCHEMA_PLAY_SOUND
    )

    hass.services.async_register(
        DOMAIN,
        IcloudService.DISPLAY_MESSAGE,
        display_message,
        schema=SERVICE_SCHEMA_DISPLAY_MESSAGE,
    )

    hass.services.async_register(
        DOMAIN,
        IcloudService.LOST_DEVICE,
        lost_device,
        schema=SERVICE_SCHEMA_LOST_DEVICE,
    )

    hass.services.async_register(
        DOMAIN, IcloudService.UPDATE, update_account, schema=SERVICE_SCHEMA
    )
