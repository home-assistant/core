"""Support for WeMo device discovery."""
import asyncio
import logging

import pywemo
import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

# Mapping from Wemo model_name to component.
WEMO_MODEL_DISPATCH = {
    "Bridge": "light",
    "CoffeeMaker": "switch",
    "Dimmer": "light",
    "Humidifier": "fan",
    "Insight": "switch",
    "LightSwitch": "switch",
    "Maker": "switch",
    "Motion": "binary_sensor",
    "Sensor": "binary_sensor",
    "Socket": "switch",
}

_LOGGER = logging.getLogger(__name__)


def coerce_host_port(value):
    """Validate that provided value is either just host or host:port.

    Returns (host, None) or (host, port) respectively.
    """
    host, _, port = value.partition(":")

    if not host:
        raise vol.Invalid("host cannot be empty")

    if port:
        port = cv.port(port)
    else:
        port = None

    return host, port


CONF_STATIC = "static"
CONF_DISCOVERY = "discovery"

DEFAULT_DISCOVERY = True

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_STATIC, default=[]): vol.Schema(
                    [vol.All(cv.string, coerce_host_port)]
                ),
                vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up for WeMo devices."""
    hass.data[DOMAIN] = {
        "config": config.get(DOMAIN, {}),
        "registry": None,
        "pending": {},
    }

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up a wemo config entry."""
    config = hass.data[DOMAIN].pop("config")

    # Keep track of WeMo device subscriptions for push updates
    registry = hass.data[DOMAIN]["registry"] = pywemo.SubscriptionRegistry()
    await hass.async_add_executor_job(registry.start)

    def stop_wemo(event):
        """Shutdown Wemo subscriptions and subscription thread on exit."""
        _LOGGER.debug("Shutting down WeMo event subscriptions")
        registry.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_wemo)

    devices = {}

    static_conf = config.get(CONF_STATIC, [])
    if static_conf:
        _LOGGER.debug("Adding statically configured WeMo devices...")
        for device in await asyncio.gather(
            *[
                hass.async_add_executor_job(validate_static_config, host, port)
                for host, port in static_conf
            ]
        ):
            if device is None:
                continue

            devices.setdefault(device.serialnumber, device)

    if config.get(CONF_DISCOVERY, DEFAULT_DISCOVERY):
        _LOGGER.debug("Scanning network for WeMo devices...")
        for device in await hass.async_add_executor_job(pywemo.discover_devices):
            devices.setdefault(
                device.serialnumber,
                device,
            )

    loaded_components = set()

    for device in devices.values():
        _LOGGER.debug(
            "Adding WeMo device at %s:%i (%s)",
            device.host,
            device.port,
            device.serialnumber,
        )

        component = WEMO_MODEL_DISPATCH.get(device.model_name, "switch")

        # Three cases:
        # - First time we see component, we need to load it and initialize the backlog
        # - Component is being loaded, add to backlog
        # - Component is loaded, backlog is gone, dispatch discovery

        if component not in loaded_components:
            hass.data[DOMAIN]["pending"][component] = [device]
            loaded_components.add(component)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, component)
            )

        elif component in hass.data[DOMAIN]["pending"]:
            hass.data[DOMAIN]["pending"][component].append(device)

        else:
            async_dispatcher_send(
                hass,
                f"{DOMAIN}.{component}",
                device,
            )

    return True


def validate_static_config(host, port):
    """Handle a static config."""
    url = pywemo.setup_url_for_address(host, port)

    if not url:
        _LOGGER.error(
            "Unable to get description url for WeMo at: %s",
            f"{host}:{port}" if port else host,
        )
        return None

    try:
        device = pywemo.discovery.device_from_description(url, None)
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    ) as err:
        _LOGGER.error("Unable to access WeMo at %s (%s)", url, err)
        return None

    return device
