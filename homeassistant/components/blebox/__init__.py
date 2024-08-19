"""The BleBox devices integration."""

import logging

from blebox_uniapi.box import Box
from blebox_uniapi.error import Error
from blebox_uniapi.session import ApiHost

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType
from homeassistant.components import lovelace
from homeassistant.components.lovelace import dashboard

from .const import DEFAULT_SETUP_TIMEOUT, DOMAIN, PRODUCT
from .helpers import get_maybe_authenticated_session

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

PARALLEL_UPDATES = 0


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def setup_dashboard(call):
        dashboards_collection: dashboard.DashboardsCollection = hass.data[lovelace.DOMAIN][
            "dashboards_collection"
        ]

        for id_, product in hass.data[DOMAIN].items():
            url = "url_path"
            dashboard_create_data = {
                lovelace.CONF_ALLOW_SINGLE_WORD: True,
                lovelace.CONF_URL_PATH: url,
                lovelace.CONF_TITLE: f"Energy ({id_})",
            }

            await dashboards_collection.async_create_item(dashboard_create_data)
            dashboard_store: dashboard.LovelaceStorage = hass.data[lovelace.DOMAIN]["dashboards"][url]
            await dashboard_store.async_save({
                "views": [
                    {
                        "title": "ALL PHASES(1 + 2 + 3)",
                        "badges": [
                            {
                                "type": "entity",
                                "entity": "light.my_wlightbox_ct_v20200229_wlightbox_color_cct"}
                        ],
                    }
                ]
            })

    hass.services.async_register(DOMAIN, "dashboard", setup_dashboard)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BleBox devices from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    timeout = DEFAULT_SETUP_TIMEOUT

    websession = get_maybe_authenticated_session(hass, password, username)

    api_host = ApiHost(host, port, timeout, websession, hass.loop)

    try:
        product = await Box.async_from_host(api_host)
    except Error as ex:
        _LOGGER.error("Identify failed at %s:%d (%s)", api_host.host, api_host.port, ex)
        raise ConfigEntryNotReady from ex

    domain = hass.data.setdefault(DOMAIN, {})
    domain_entry = domain.setdefault(entry.entry_id, {})
    product = domain_entry.setdefault(PRODUCT, product)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
