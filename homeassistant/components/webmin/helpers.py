"""Helper functions for the Webmin integration."""

from collections.abc import Mapping
from typing import Any

from webmin_xmlrpc.client import WebminInstance
from yarl import URL

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession


def get_instance_from_options(
    hass: HomeAssistant, options: Mapping[str, Any]
) -> tuple[WebminInstance, URL]:
    """Retrieve a Webmin instance and the base URL from config options."""

    base_url = URL.build(
        scheme="https" if options[CONF_SSL] else "http",
        user=options[CONF_USERNAME],
        password=options[CONF_PASSWORD],
        host=options[CONF_HOST],
        port=int(options[CONF_PORT]),
    )

    return WebminInstance(
        session=async_create_clientsession(
            hass,
            verify_ssl=options[CONF_VERIFY_SSL],
            base_url=base_url,
        )
    ), base_url


def get_sorted_mac_addresses(data: dict[str, Any]) -> list[str]:
    """Return a sorted list of mac addresses."""
    return sorted(
        [iface["ether"] for iface in data["active_interfaces"] if "ether" in iface]
    )
