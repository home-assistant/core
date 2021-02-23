"""Support for WeMo device discovery."""
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
from homeassistant.util.async_ import gather_with_concurrency

from .const import DOMAIN

# Max number of devices to initialize at once. This limit is in place to
# avoid tying up too many executor threads with WeMo device setup.
MAX_CONCURRENCY = 3

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

    wemo_dispatcher = WemoDispatcher(entry)
    wemo_discovery = WemoDiscovery(hass, wemo_dispatcher)

    async def async_stop_wemo(event):
        """Shutdown Wemo subscriptions and subscription thread on exit."""
        _LOGGER.debug("Shutting down WeMo event subscriptions")
        await hass.async_add_executor_job(registry.stop)
        wemo_discovery.async_stop_discovery()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_wemo)

    static_conf = config.get(CONF_STATIC, [])
    if static_conf:
        _LOGGER.debug("Adding statically configured WeMo devices...")
        for device in await gather_with_concurrency(
            MAX_CONCURRENCY,
            *[
                hass.async_add_executor_job(validate_static_config, host, port)
                for host, port in static_conf
            ],
        ):
            if device:
                wemo_dispatcher.async_add_unique_device(hass, device)

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

    def __init__(self, hass: HomeAssistant, wemo_dispatcher: WemoDispatcher) -> None:
        """Initialize the WemoDiscovery."""
        self._hass = hass
        self._wemo_dispatcher = wemo_dispatcher
        self._stop = None
        self._scan_delay = 0
        self._upnp_entries = set()

    async def async_add_from_upnp_entry(self, entry: pywemo.ssdp.UPNPEntry) -> None:
        """Create a WeMoDevice from an UPNPEntry and add it to the dispatcher.

        Uses the self._upnp_entries set to avoid interrogating the same device
        multiple times.
        """
        if entry in self._upnp_entries:
            return
        try:
            device = await self._hass.async_add_executor_job(
                pywemo.discovery.device_from_uuid_and_location,
                entry.udn,
                entry.location,
            )
        except pywemo.PyWeMoException as err:
            _LOGGER.error("Unable to setup WeMo %r (%s)", entry, err)
        else:
            self._wemo_dispatcher.async_add_unique_device(self._hass, device)
            self._upnp_entries.add(entry)

    async def async_discover_and_schedule(self, *_) -> None:
        """Periodically scan the network looking for WeMo devices."""
        _LOGGER.debug("Scanning network for WeMo devices...")
        try:
            # pywemo.ssdp.scan is a light-weight UDP UPnP scan for WeMo devices.
            entries = await self._hass.async_add_executor_job(pywemo.ssdp.scan)

            # async_add_from_upnp_entry causes multiple HTTP requests to be sent
            # to the WeMo device for the initial setup of the WeMoDevice
            # instance. This may take some time to complete. The per-device
            # setup work is done in parallel to speed up initial setup for the
            # component.
            await gather_with_concurrency(
                MAX_CONCURRENCY,
                *[self.async_add_from_upnp_entry(entry) for entry in entries],
            )
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
