"""Support for WeMo device discovery."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
import logging

import pywemo
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DISCOVERY, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.async_ import gather_with_concurrency

from .const import DOMAIN
from .wemo_device import async_register_device

# Max number of devices to initialize at once. This limit is in place to
# avoid tying up too many executor threads with WeMo device setup.
MAX_CONCURRENCY = 3

# Mapping from Wemo model_name to domain.
WEMO_MODEL_DISPATCH = {
    "Bridge": [Platform.LIGHT],
    "CoffeeMaker": [Platform.SWITCH],
    "Dimmer": [Platform.LIGHT],
    "Humidifier": [Platform.FAN],
    "Insight": [Platform.BINARY_SENSOR, Platform.SWITCH],
    "LightSwitch": [Platform.SWITCH],
    "Maker": [Platform.BINARY_SENSOR, Platform.SWITCH],
    "Motion": [Platform.BINARY_SENSOR],
    "OutdoorPlug": [Platform.SWITCH],
    "Sensor": [Platform.BINARY_SENSOR],
    "Socket": [Platform.SWITCH],
}

_LOGGER = logging.getLogger(__name__)

HostPortTuple = tuple[str, int | None]


def coerce_host_port(value: str) -> HostPortTuple:
    """Validate that provided value is either just host or host:port.

    Returns (host, None) or (host, port) respectively.
    """
    host, _, port_str = value.partition(":")

    if not host:
        raise vol.Invalid("host cannot be empty")

    port = cv.port(port_str) if port_str else None

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a wemo config entry."""
    config = hass.data[DOMAIN].pop("config")

    # Keep track of WeMo device subscriptions for push updates
    registry = hass.data[DOMAIN]["registry"] = pywemo.SubscriptionRegistry()
    await hass.async_add_executor_job(registry.start)

    # Respond to discovery requests from WeMo devices.
    discovery_responder = pywemo.ssdp.DiscoveryResponder(registry.port)
    await hass.async_add_executor_job(discovery_responder.start)

    static_conf: Sequence[HostPortTuple] = config.get(CONF_STATIC, [])
    wemo_dispatcher = WemoDispatcher(entry)
    wemo_discovery = WemoDiscovery(hass, wemo_dispatcher, static_conf)

    async def async_stop_wemo(event: Event) -> None:
        """Shutdown Wemo subscriptions and subscription thread on exit."""
        _LOGGER.debug("Shutting down WeMo event subscriptions")
        await hass.async_add_executor_job(registry.stop)
        await hass.async_add_executor_job(discovery_responder.stop)
        wemo_discovery.async_stop_discovery()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_wemo)
    )

    # Need to do this at least once in case statistics are defined and discovery is disabled
    await wemo_discovery.discover_statics()

    if config.get(CONF_DISCOVERY, DEFAULT_DISCOVERY):
        await wemo_discovery.async_discover_and_schedule()

    return True


class WemoDispatcher:
    """Dispatch WeMo devices to the correct platform."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the WemoDispatcher."""
        self._config_entry = config_entry
        self._added_serial_numbers: set[str] = set()
        self._loaded_platforms: set[Platform] = set()

    async def async_add_unique_device(
        self, hass: HomeAssistant, wemo: pywemo.WeMoDevice
    ) -> None:
        """Add a WeMo device to hass if it has not already been added."""
        if wemo.serialnumber in self._added_serial_numbers:
            return

        coordinator = await async_register_device(hass, self._config_entry, wemo)
        platforms = set(WEMO_MODEL_DISPATCH.get(wemo.model_name, [Platform.SWITCH]))
        platforms.add(Platform.SENSOR)
        for platform in platforms:
            # Three cases:
            # - First time we see platform, we need to load it and initialize the backlog
            # - Platform is being loaded, add to backlog
            # - Platform is loaded, backlog is gone, dispatch discovery

            if platform not in self._loaded_platforms:
                hass.data[DOMAIN]["pending"][platform] = [coordinator]
                self._loaded_platforms.add(platform)
                hass.async_create_task(
                    hass.config_entries.async_forward_entry_setup(
                        self._config_entry, platform
                    )
                )

            elif platform in hass.data[DOMAIN]["pending"]:
                hass.data[DOMAIN]["pending"][platform].append(coordinator)

            else:
                async_dispatcher_send(
                    hass,
                    f"{DOMAIN}.{platform}",
                    coordinator,
                )

        self._added_serial_numbers.add(wemo.serialnumber)


class WemoDiscovery:
    """Use SSDP to discover WeMo devices."""

    ADDITIONAL_SECONDS_BETWEEN_SCANS = 10
    MAX_SECONDS_BETWEEN_SCANS = 300

    def __init__(
        self,
        hass: HomeAssistant,
        wemo_dispatcher: WemoDispatcher,
        static_config: Sequence[HostPortTuple],
    ) -> None:
        """Initialize the WemoDiscovery."""
        self._hass = hass
        self._wemo_dispatcher = wemo_dispatcher
        self._stop: CALLBACK_TYPE | None = None
        self._scan_delay = 0
        self._static_config = static_config

    async def async_discover_and_schedule(
        self, event_time: datetime | None = None
    ) -> None:
        """Periodically scan the network looking for WeMo devices."""
        _LOGGER.debug("Scanning network for WeMo devices")
        try:
            for device in await self._hass.async_add_executor_job(
                pywemo.discover_devices
            ):
                await self._wemo_dispatcher.async_add_unique_device(self._hass, device)
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

    async def discover_statics(self) -> None:
        """Initialize or Re-Initialize connections to statically configured devices."""
        if not self._static_config:
            return
        _LOGGER.debug("Adding statically configured WeMo devices")
        for device in await gather_with_concurrency(
            MAX_CONCURRENCY,
            *(
                self._hass.async_add_executor_job(validate_static_config, host, port)
                for host, port in self._static_config
            ),
        ):
            if device:
                await self._wemo_dispatcher.async_add_unique_device(self._hass, device)


def validate_static_config(host: str, port: int | None) -> pywemo.WeMoDevice | None:
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
