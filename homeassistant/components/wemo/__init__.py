"""Support for WeMo device discovery."""
import logging

import pywemo
import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
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
    hass.data[DOMAIN] = config

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up a wemo config entry."""
    known_devices = set()
    loaded_components = set()

    config = hass.data[DOMAIN]

    # Keep track of WeMo devices
    devices = []

    # Keep track of WeMo device subscriptions for push updates
    hass.data[DOMAIN] = pywemo.SubscriptionRegistry()
    await hass.async_add_executor_job(hass.data[DOMAIN].start)

    def stop_wemo(event):
        """Shutdown Wemo subscriptions and subscription thread on exit."""
        _LOGGER.debug("Shutting down WeMo event subscriptions")
        hass.data[DOMAIN].stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_wemo)

    async def async_discover_wemo_devices(now):
        """Run discovery for WeMo devices."""
        _LOGGER.debug("Beginning WeMo device discovery...")
        _LOGGER.debug("Adding statically configured WeMo devices...")
        for host, port in config.get(DOMAIN, {}).get(CONF_STATIC, []):
            url = await hass.async_add_executor_job(setup_url_for_address, host, port)

            if not url:
                _LOGGER.error(
                    "Unable to get description url for WeMo at: %s",
                    f"{host}:{port}" if port else host,
                )
                continue

            try:
                device = await hass.async_add_executor_job(
                    pywemo.discovery.device_from_description, url, None
                )
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as err:
                _LOGGER.error("Unable to access WeMo at %s (%s)", url, err)
                continue

            if not [d[1] for d in devices if d[1].serialnumber == device.serialnumber]:
                devices.append((url, device))

        if config.get(DOMAIN, {}).get(CONF_DISCOVERY, DEFAULT_DISCOVERY):
            _LOGGER.debug("Scanning network for WeMo devices...")
            for device in await hass.async_add_executor_job(pywemo.discover_devices):
                if not [
                    d[1] for d in devices if d[1].serialnumber == device.serialnumber
                ]:
                    devices.append(
                        (f"http://{device.host}:{device.port}/setup.xml", device)
                    )

        for url, device in devices:
            _LOGGER.debug("Adding WeMo device at %s:%i", device.host, device.port)

            # Only register a device once
            if device.serialnumber in known_devices:
                _LOGGER.debug("Ignoring known device %s", device.serialnumber)
                return

            _LOGGER.debug("Discovered unique WeMo device: %s", device.serialnumber)
            known_devices.add(device.serialnumber)

            component = WEMO_MODEL_DISPATCH.get(device.model_name, "switch")

            if component not in loaded_components:
                loaded_components.add(component)
                await hass.config_entries.async_forward_entry_setup(entry, component)

            async_dispatcher_send(
                hass,
                f"{DOMAIN}.{component}",
                {
                    "model_name": device.model_name,
                    "serial": device.serialnumber,
                    "mac_address": device.mac,
                    "ssdp_description": url,
                },
            )

        _LOGGER.debug("WeMo device discovery has finished")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, async_discover_wemo_devices)

    return True


def setup_url_for_address(host, port):
    """Determine setup.xml url for given host and port pair."""
    if not port:
        port = pywemo.ouimeaux_device.probe_wemo(host)

    if not port:
        return None

    return f"http://{host}:{port}/setup.xml"
