"""Support for IKEA Tradfri."""
import asyncio
import logging

from pytradfri import Gateway, RequestError
from pytradfri.api.aiocoap_api import APIFactory
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json

from . import config_flow  # noqa: F401
from .const import (
    ATTR_TRADFRI_GATEWAY,
    ATTR_TRADFRI_GATEWAY_MODEL,
    ATTR_TRADFRI_MANUFACTURER,
    CONF_ALLOW_TRADFRI_GROUPS,
    CONF_GATEWAY_ID,
    CONF_HOST,
    CONF_IDENTITY,
    CONF_IMPORT_GROUPS,
    CONF_KEY,
    CONFIG_FILE,
    DEFAULT_ALLOW_TRADFRI_GROUPS,
    DOMAIN,
    KEY_API,
    KEY_GATEWAY,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

FACTORY = "tradfri_factory"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(
                    CONF_ALLOW_TRADFRI_GROUPS, default=DEFAULT_ALLOW_TRADFRI_GROUPS
                ): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Tradfri component."""
    conf = config.get(DOMAIN)

    if conf is None:
        return True

    configured_hosts = [
        entry.data["host"] for entry in hass.config_entries.async_entries(DOMAIN)
    ]

    legacy_hosts = await hass.async_add_executor_job(
        load_json, hass.config.path(CONFIG_FILE)
    )

    for host, info in legacy_hosts.items():
        if host in configured_hosts:
            continue

        info[CONF_HOST] = host
        info[CONF_IMPORT_GROUPS] = conf[CONF_ALLOW_TRADFRI_GROUPS]

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=info
            )
        )

    host = conf.get(CONF_HOST)
    import_groups = conf[CONF_ALLOW_TRADFRI_GROUPS]

    if host is None or host in configured_hosts or host in legacy_hosts:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: host, CONF_IMPORT_GROUPS: import_groups},
        )
    )

    return True


async def async_setup_entry(hass, entry):
    """Create a gateway."""
    # host, identity, key, allow_tradfri_groups

    factory = await APIFactory.init(
        entry.data[CONF_HOST],
        psk_id=entry.data[CONF_IDENTITY],
        psk=entry.data[CONF_KEY],
    )

    async def on_hass_stop(event):
        """Close connection when hass stops."""
        await factory.shutdown()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)

    api = factory.request
    gateway = Gateway()

    try:
        gateway_info = await api(gateway.get_gateway_info())
    except RequestError as err:
        await factory.shutdown()
        raise ConfigEntryNotReady from err

    hass.data.setdefault(KEY_API, {})[entry.entry_id] = api
    hass.data.setdefault(KEY_GATEWAY, {})[entry.entry_id] = gateway
    tradfri_data = hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {}
    tradfri_data[FACTORY] = factory

    dev_reg = await hass.helpers.device_registry.async_get_registry()
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={(DOMAIN, entry.data[CONF_GATEWAY_ID])},
        manufacturer=ATTR_TRADFRI_MANUFACTURER,
        name=ATTR_TRADFRI_GATEWAY,
        # They just have 1 gateway model. Type is not exposed yet.
        model=ATTR_TRADFRI_GATEWAY_MODEL,
        sw_version=gateway_info.firmware_version,
    )

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass, entry):
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
        hass.data[KEY_API].pop(entry.entry_id)
        hass.data[KEY_GATEWAY].pop(entry.entry_id)
        tradfri_data = hass.data[DOMAIN].pop(entry.entry_id)
        factory = tradfri_data[FACTORY]
        await factory.shutdown()

    return unload_ok
