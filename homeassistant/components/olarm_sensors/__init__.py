"""Integration for Olarm Devices for Home Assistant."""
import asyncio
import os
import re

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_ALARM_CODE,
    CONF_OLARM_DEVICES,
    DOMAIN,
    LOGGER,
    OLARM_DEVICE_AMOUNT,
    OLARM_DEVICES,
)
from .coordinator import OlarmCoordinator
from .exceptions import (
    APIClientConnectorError,
    APIContentTypeError,
    APIForbiddenError,
    DictionaryKeyError,
)
from .olarm_api import OlarmApi, OlarmSetupApi

path = os.path.abspath(__file__).replace("__init__.py", "")
PLATFORMS = [
    ALARM_CONTROL_PANEL_DOMAIN,
    BINARY_SENSOR_DOMAIN,
    BUTTON_DOMAIN,
    SWITCH_DOMAIN,
    UPDATE_DOMAIN,
]


def replace_characters(text):
    """Replace illegal characters in the device name."""
    # Remove punctuation and weird characters
    text = re.sub(r"[^\w\s]", "", text)

    # Replace spaces with underscore
    text = re.sub(r"\s", "_", text)

    return text


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Olarm integration. Create a coordinator instance, register services for each zone, and forward the setup for other platforms."""

    # Updating and syncing options and integration data.
    await update_listener(hass, config_entry)

    # Getting the devices associated with the users account.
    setup_api = OlarmSetupApi(api_key=config_entry.data[CONF_API_KEY])
    try:
        devices = await setup_api.get_olarm_devices()

    except (APIClientConnectorError, APIContentTypeError, APIForbiddenError) as ex:
        raise ConfigEntryNotReady(
            "Could not connect to the Olarm Api to get the devices linked to your Olarm account. Check your API key or reload the integration"
        ) from ex

    if len(devices) > int(config_entry.data[OLARM_DEVICE_AMOUNT]):
        LOGGER.warning(
            "The amount of Olarm Devices linked to your profile changed. It was %s and is now %s. Please select the correct devices for this instance under options",
            int(config_entry.data[OLARM_DEVICE_AMOUNT]),
            len(devices),
        )

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["devices"] = devices

    # Generating services file
    filedata: list = []
    for device in devices:
        if device["deviceName"] not in config_entry.data[CONF_OLARM_DEVICES]:
            continue

        LOGGER.info(
            "Setting up Olarm device (%s) with device id: %s",
            device["deviceName"],
            device["deviceId"],
        )

        coordinator = OlarmCoordinator(
            hass,
            entry=config_entry,
            device_id=device["deviceId"],
            device_name=device["deviceName"],
            device_make=device["deviceAlarmType"],
        )

        await coordinator.update_data()

        hass.data[DOMAIN][device["deviceId"]] = coordinator

        LOGGER.info(
            "Creating bypass service for Olarm device (%s) with device id: %s",
            device["deviceName"],
            device["deviceId"],
        )

        device_name_for_ha = replace_characters(device["deviceName"].lower())

        # Creating an instance of the Olarm API class to call the requests to arm, disarm, sleep, or stay the zones.
        OLARM_API = OlarmApi(
            device_id=device["deviceId"],
            api_key=config_entry.data[CONF_API_KEY],
        )

        filedata = []
        filedata.append(
            f"{device_name_for_ha}_bypass_zone:\n  description: Send a request to Olarm to bypass the zone on {device['deviceName']}.\n  fields:\n    zone_num:\n      description: 'Zone Number (Can be found under state attributes for the specified zone.)'\n      example: '1'\n      required: true\n"
        )
        # Registering Services

        # Bypass service
        # Register the bypass service
        hass.services.async_register(
            DOMAIN,
            f"{device_name_for_ha}_bypass_zone",
            OLARM_API.bypass_zone_with_service,
            vol.Schema(
                {
                    vol.Required("zone_num"): vol.Coerce(int),
                }
            ),
        )

        LOGGER.info(
            "Set up Olarm device (%s) with device id: %s",
            device["deviceName"],
            device["deviceId"],
        )

    with open(
        file=os.path.join(path, "services.yaml"), mode="w+", encoding="utf8"
    ) as service_file:
        for line in filedata:
            service_file.write(line)

    # Forwarding the setup for the other Home Assistant platforms.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle the removal of an entry."""
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload config entry."""
    await async_setup_entry(hass, entry)
    await hass.config_entries.async_reload(entry.entry_id)


async def update_listener(hass: HomeAssistant, config_entry):
    """Handle options update."""
    # Updating the API_KEY
    try:
        if config_entry.options[CONF_API_KEY] != config_entry.data[CONF_API_KEY]:
            data = {**config_entry.data}
            options = {**config_entry.options}

            data[CONF_API_KEY] = options[CONF_API_KEY]

            hass.config_entries.async_update_entry(
                config_entry, data=data, options=options
            )

    except (DictionaryKeyError, KeyError):
        data = {**config_entry.data}
        options = {**config_entry.options}
        options[CONF_API_KEY] = data[CONF_API_KEY]

        hass.config_entries.async_update_entry(config_entry, data=data, options=options)

    # Updating the alarm code
    try:
        if config_entry.options[CONF_ALARM_CODE] != config_entry.data[CONF_ALARM_CODE]:
            data = {**config_entry.data}

            data[CONF_ALARM_CODE] = config_entry.options[CONF_ALARM_CODE]

            options = {**config_entry.options}

            hass.config_entries.async_update_entry(
                config_entry, data=data, options=options
            )

    except (DictionaryKeyError, KeyError):
        data = {**config_entry.data}
        options = {**config_entry.options}
        if data[CONF_ALARM_CODE] is not None:
            options[CONF_ALARM_CODE] = data[CONF_ALARM_CODE]

        else:
            options[CONF_ALARM_CODE] = data[CONF_ALARM_CODE] = None

        hass.config_entries.async_update_entry(config_entry, data=data, options=options)

    # Updating the devices
    # Getting all the devices.
    setup_api = OlarmSetupApi(api_key=config_entry.data[CONF_API_KEY])
    devices = await setup_api.get_olarm_devices()
    try:
        if len(config_entry.options[CONF_OLARM_DEVICES]) != len(
            config_entry.data[CONF_OLARM_DEVICES]
        ):
            data = {**config_entry.data}

            options = {**config_entry.options}

            data[CONF_OLARM_DEVICES] = config_entry.options[CONF_OLARM_DEVICES]

            data[OLARM_DEVICES] = devices
            options[OLARM_DEVICES] = devices

            hass.config_entries.async_update_entry(
                config_entry, data=data, options=options
            )

    except (DictionaryKeyError, KeyError):
        data = {**config_entry.data}
        options = {**config_entry.options}

        if data[CONF_OLARM_DEVICES] is not None:
            options[CONF_OLARM_DEVICES] = data[CONF_OLARM_DEVICES]

        data[OLARM_DEVICES] = devices
        options[OLARM_DEVICES] = devices
        hass.config_entries.async_update_entry(config_entry, data=data, options=options)

    # Updating the Device Amount
    try:
        if (
            config_entry.options[OLARM_DEVICE_AMOUNT]
            != config_entry.data[OLARM_DEVICE_AMOUNT]
        ):
            data = {**config_entry.data}

            data[OLARM_DEVICE_AMOUNT] = config_entry.options[OLARM_DEVICE_AMOUNT]

            options = {**config_entry.options}

            hass.config_entries.async_update_entry(
                config_entry, data=data, options=options
            )

    except (DictionaryKeyError, KeyError):
        data = {**config_entry.data}
        options = {**config_entry.options}

        if data[OLARM_DEVICE_AMOUNT] is not None:
            options[OLARM_DEVICE_AMOUNT] = data[OLARM_DEVICE_AMOUNT]

        hass.config_entries.async_update_entry(config_entry, data=data, options=options)

    # Updating the scan interval
    try:
        if int(config_entry.options[CONF_SCAN_INTERVAL]) != int(
            config_entry.data[CONF_SCAN_INTERVAL]
        ):
            data = {**config_entry.data}

            data[CONF_SCAN_INTERVAL] = config_entry.options[CONF_SCAN_INTERVAL]

            options = {**config_entry.options}

            hass.config_entries.async_update_entry(
                config_entry, data=data, options=options
            )

    except (DictionaryKeyError, KeyError):
        data = {**config_entry.data}
        options = {**config_entry.options}

        if data[CONF_SCAN_INTERVAL] is not None:
            options[CONF_SCAN_INTERVAL] = data[CONF_SCAN_INTERVAL]

        hass.config_entries.async_update_entry(config_entry, data=data, options=options)


async def handle_service_call_event(coordinator: OlarmCoordinator, event, service_name):
    """Update when there has been a service call."""
    if event.data["domain"] == DOMAIN and event.data["service"] == service_name:
        await asyncio.sleep(1)
        await coordinator.async_update_bypass_data()
