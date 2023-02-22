"""The iCloud component."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

from .account import IcloudAccount
from .const import (
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    CONF_WITH_FAMILY,
    DOMAIN,
    PLATFORMS,
    STORAGE_KEY,
    STORAGE_VERSION,
)

ATTRIBUTION = "Data provided by Apple iCloud"

# entity attributes
ATTR_ACCOUNT_FETCH_INTERVAL = "account_fetch_interval"
ATTR_BATTERY = "battery"
ATTR_BATTERY_STATUS = "battery_status"
ATTR_DEVICE_NAME = "device_name"
ATTR_DEVICE_STATUS = "device_status"
ATTR_LOW_POWER_MODE = "low_power_mode"
ATTR_OWNER_NAME = "owner_fullname"

# services
SERVICE_ICLOUD_PLAY_SOUND = "play_sound"
SERVICE_ICLOUD_DISPLAY_MESSAGE = "display_message"
SERVICE_ICLOUD_LOST_DEVICE = "lost_device"
SERVICE_ICLOUD_UPDATE = "update"
ATTR_ACCOUNT = "account"
ATTR_LOST_DEVICE_MESSAGE = "message"
ATTR_LOST_DEVICE_NUMBER = "number"
ATTR_LOST_DEVICE_SOUND = "sound"

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

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an iCloud account from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    with_family = entry.data[CONF_WITH_FAMILY]
    max_interval = entry.data[CONF_MAX_INTERVAL]
    gps_accuracy_threshold = entry.data[CONF_GPS_ACCURACY_THRESHOLD]

    # For backwards compat
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=username)

    icloud_dir = Store[Any](hass, STORAGE_VERSION, STORAGE_KEY)

    account = IcloudAccount(
        hass,
        username,
        password,
        icloud_dir,
        with_family,
        max_interval,
        gps_accuracy_threshold,
        entry,
    )
    await hass.async_add_executor_job(account.setup)

    hass.data[DOMAIN][entry.unique_id] = account

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def play_sound(service: ServiceCall) -> None:
        """Play sound on the device."""
        account = service.data[ATTR_ACCOUNT]
        device_name: str = service.data[ATTR_DEVICE_NAME]
        device_name = slugify(device_name.replace(" ", "", 99))

        for device in _get_account(account).get_devices_with_name(device_name):
            device.play_sound()

    def display_message(service: ServiceCall) -> None:
        """Display a message on the device."""
        account = service.data[ATTR_ACCOUNT]
        device_name: str = service.data[ATTR_DEVICE_NAME]
        device_name = slugify(device_name.replace(" ", "", 99))
        message = service.data.get(ATTR_LOST_DEVICE_MESSAGE)
        sound = service.data.get(ATTR_LOST_DEVICE_SOUND, False)

        for device in _get_account(account).get_devices_with_name(device_name):
            device.display_message(message, sound)

    def lost_device(service: ServiceCall) -> None:
        """Make the device in lost state."""
        account = service.data[ATTR_ACCOUNT]
        device_name: str = service.data[ATTR_DEVICE_NAME]
        device_name = slugify(device_name.replace(" ", "", 99))
        number = service.data.get(ATTR_LOST_DEVICE_NUMBER)
        message = service.data.get(ATTR_LOST_DEVICE_MESSAGE)

        for device in _get_account(account).get_devices_with_name(device_name):
            device.lost_device(number, message)

    def update_account(service: ServiceCall) -> None:
        """Call the update function of an iCloud account."""
        if (account := service.data.get(ATTR_ACCOUNT)) is None:
            for account in hass.data[DOMAIN].values():
                account.keep_alive()
        else:
            _get_account(account).keep_alive()

    def _get_account(account_identifier: str) -> IcloudAccount:
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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.data[CONF_USERNAME])
    return unload_ok
