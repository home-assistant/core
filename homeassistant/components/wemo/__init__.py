"""Support for WeMo device discovery."""
import asyncio
import logging

import pywemo
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DISCOVERY, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

# Mapping from Wemo model_name to domain.
WEMO_MODEL_DISPATCH = {
    "Bridge": LIGHT_DOMAIN,
    "CoffeeMaker": SWITCH_DOMAIN,
    "Dimmer": LIGHT_DOMAIN,
    "Humidifier": FAN_DOMAIN,
    "Insight": SWITCH_DOMAIN,
    "LightSwitch": SWITCH_DOMAIN,
    "Maker": SWITCH_DOMAIN,
    "Motion": BINARY_SENSOR_DOMAIN,
    "OutdoorPlug": SWITCH_DOMAIN,
    "Sensor": BINARY_SENSOR_DOMAIN,
    "Socket": SWITCH_DOMAIN,
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a wemo config entry."""
    config = hass.data[DOMAIN].pop("config")

    # Keep track of WeMo device subscriptions for push updates
    registry = hass.data[DOMAIN]["registry"] = pywemo.SubscriptionRegistry()
    await hass.async_add_executor_job(registry.start)
    static_conf = config.get(CONF_STATIC, [])
    wemo_dispatcher = WemoDispatcher(entry)
    wemo_discovery = WemoDiscovery(hass, wemo_dispatcher, static_conf)

    async def async_stop_wemo(event):
        """Shutdown Wemo subscriptions and subscription thread on exit."""
        _LOGGER.debug("Shutting down WeMo event subscriptions")
        await hass.async_add_executor_job(registry.stop)
        wemo_discovery.async_stop_discovery()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_wemo)
    )

    # Need to do this at least once in case statics are defined and discovery is disabled
    await wemo_discovery.discover_statics()

    if config.get(CONF_DISCOVERY, DEFAULT_DISCOVERY):
        await wemo_discovery.async_discover_and_schedule()

    return True


class WemoDispatcher:
    """Dispatch WeMo devices to the correct platform."""

    def __init__(self, config_entry: ConfigEntry):
        """Initialize the WemoDispatcher."""
        self._config_entry = config_entry
        self._added_serial_numbers = set()
        self._loaded_components = set()

    @callback
    def async_add_unique_device(
        self, hass: HomeAssistant, device: pywemo.WeMoDevice
    ) -> None:
        """Add a WeMo device to hass if it has not already been added."""
        if device.serialnumber in self._added_serial_numbers:
            return

        component = WEMO_MODEL_DISPATCH.get(device.model_name, SWITCH_DOMAIN)

        # Three cases:
        # - First time we see component, we need to load it and initialize the backlog
        # - Component is being loaded, add to backlog
        # - Component is loaded, backlog is gone, dispatch discovery

        if component not in self._loaded_components:
            hass.data[DOMAIN]["pending"][component] = [device]
            self._loaded_components.add(component)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    self._config_entry, component
                )
            )

        elif component in hass.data[DOMAIN]["pending"]:
            hass.data[DOMAIN]["pending"][component].append(device)

        else:
            async_dispatcher_send(
                hass,
                f"{DOMAIN}.{component}",
                device,
            )

        self._added_serial_numbers.add(device.serialnumber)


class WemoDiscovery:
    """Use SSDP to discover WeMo devices."""

    ADDITIONAL_SECONDS_BETWEEN_SCANS = 10
    MAX_SECONDS_BETWEEN_SCANS = 300

    def __init__(
        self, hass: HomeAssistant, wemo_dispatcher: WemoDispatcher, staticConfig
    ) -> None:
        """Initialize the WemoDiscovery."""
        self._hass = hass
        self._wemo_dispatcher = wemo_dispatcher
        self._stop = None
        self._scan_delay = 0
        self._static_config = staticConfig

    async def async_discover_and_schedule(self, *_) -> None:
        """Periodically scan the network looking for WeMo devices."""
        _LOGGER.debug("Scanning network for WeMo devices")
        try:
            for device in await self._hass.async_add_executor_job(
                pywemo.discover_devices
            ):
                self._wemo_dispatcher.async_add_unique_device(self._hass, device)
            await self.discover_statics()

        finally:
            # Run discovery more frequently after hass has just started.
            self._scan_delay = min(
                self._scan_delay + self.ADDITIONAL_SECONDS_BETWEEN_SCANS,
                self.MAX_SECONDS_BETWEEN_SCANS,
            )
            self._stop = async_call_later(
                self._hass,
                self._scan_delay,
                self.async_discover_and_schedule,
            )

    @callback
    def async_stop_discovery(self) -> None:
        """Stop the periodic background scanning."""
        if self._stop:
            self._stop()
            self._stop = None

    async def discover_statics(self):
        """Initialize or Re-Initialize connections to statically configured devices."""
        if self._static_config:
            _LOGGER.debug("Adding statically configured WeMo devices")
            for device in await asyncio.gather(
                *[
                    self._hass.async_add_executor_job(
                        validate_static_config, host, port
                    )
                    for host, port in self._static_config
                ]
            ):
                if device:
                    self._wemo_dispatcher.async_add_unique_device(self._hass, device)


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
        device = pywemo.discovery.device_from_description(url)
    except (
        pywemo.exceptions.ActionException,
        pywemo.exceptions.HTTPException,
    ) as err:
        _LOGGER.error("Unable to access WeMo at %s (%s)", url, err)
        return None

    return device
