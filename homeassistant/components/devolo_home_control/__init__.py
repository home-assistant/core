"""The devolo_home_control integration."""
import asyncio
from datetime import timedelta

import voluptuous as vol

from homeassistant.components import switch as ha_switch
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["switch"]

SCAN_INTERVAL = timedelta(milliseconds=1000)
SUPPORTED_PLATFORMS = [ha_switch.DOMAIN]


def setup(hass: HomeAssistant, config: dict):
    """Set up the devolo_home_control component."""
    # print('in async setup')
    # api = Api(user="dvt.devolo+automation@gmail.com",
    #           password="oloved03",
    #           url="https://dcloud-test.devolo.net/",
    #           mPRM_url="https://mprm-test.devolo.net",
    #           gateway_serial="1406126500001876")
    # devices = api.get_binary_switch_devices()
    # devices_list = []
    # for device in devices:
    #     try:
    #         devices_list.append(DevoloSwitch(name=device))
    #     except IndexError:
    #         pass
    # # devices.append(devoloSwitch(name='Metering Plug 1'))
    # for item in devices_list:
    #     # print(item)
    #     hass.states.set(f'devolo_home_control.{item.name.replace(" ", "_")}', item.state)
    #     print(f'{item.name}: {item.state} {item.should_poll} {item.unique_id} {item.enabled}')

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up devolo_home_control from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
