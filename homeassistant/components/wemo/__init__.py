"""Support for WeMo device discovery."""
from __future__ import annotations

from collections.abc import Callable, Coroutine, Sequence
from datetime import datetime
import logging
from typing import Any

import pywemo
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DISCOVERY, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.async_ import gather_with_limited_concurrency

from .const import DOMAIN
from .models import WemoConfigEntryData, WemoData, async_wemo_data
from .wemo_device import DeviceCoordinator, async_register_device

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

DispatchCallback = Callable[[DeviceCoordinator], Coroutine[Any, Any, None]]
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
    # Keep track of WeMo device subscriptions for push updates
    registry = pywemo.SubscriptionRegistry()
    await hass.async_add_executor_job(registry.start)

    # Respond to discovery requests from WeMo devices.
    discovery_responder = pywemo.ssdp.DiscoveryResponder(registry.port)
    await hass.async_add_executor_job(discovery_responder.start)

    async def _on_hass_stop(_: Event) -> None:
        await hass.async_add_executor_job(discovery_responder.stop)
        await hass.async_add_executor_job(registry.stop)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_hass_stop)

    yaml_config = config.get(DOMAIN, {})
    hass.data[DOMAIN] = WemoData(
        discovery_enabled=yaml_config.get(CONF_DISCOVERY, DEFAULT_DISCOVERY),
        static_config=yaml_config.get(CONF_STATIC, []),
        registry=registry,
    )

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a wemo config entry."""
    wemo_data = async_wemo_data(hass)
    dispatcher = WemoDispatcher(entry)
    discovery = WemoDiscovery(hass, dispatcher, wemo_data.static_config)
    wemo_data.config_entry_data = WemoConfigEntryData(
        device_coordinators={},
        discovery=discovery,
        dispatcher=dispatcher,
    )

    # Need to do this at least once in case statistics are defined and discovery is disabled
    await discovery.discover_statics()

    if wemo_data.discovery_enabled:
        await discovery.async_discover_and_schedule()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a wemo config entry."""
    _LOGGER.debug("Unloading WeMo")
    wemo_data = async_wemo_data(hass)

    wemo_data.config_entry_data.discovery.async_stop_discovery()

    dispatcher = wemo_data.config_entry_data.dispatcher
    if unload_ok := await dispatcher.async_unload_platforms(hass):
        assert not wemo_data.config_entry_data.device_coordinators
        wemo_data.config_entry_data = None  # type: ignore[assignment]
    return unload_ok


async def async_wemo_dispatcher_connect(
    hass: HomeAssistant,
    dispatch: DispatchCallback,
) -> None:
    """Connect a wemo platform with the WemoDispatcher."""
    module = dispatch.__module__  # Example: "homeassistant.components.wemo.switch"
    platform = Platform(module.rsplit(".", 1)[1])

    dispatcher = async_wemo_data(hass).config_entry_data.dispatcher
    await dispatcher.async_connect_platform(platform, dispatch)


class WemoDispatcher:
    """Dispatch WeMo devices to the correct platform."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the WemoDispatcher."""
        self._config_entry = config_entry
        self._added_serial_numbers: set[str] = set()
        self._failed_serial_numbers: set[str] = set()
        self._dispatch_backlog: dict[Platform, list[DeviceCoordinator]] = {}
        self._dispatch_callbacks: dict[Platform, DispatchCallback] = {}

    async def async_add_unique_device(
        self, hass: HomeAssistant, wemo: pywemo.WeMoDevice
    ) -> None:
        """Add a WeMo device to hass if it has not already been added."""
        if wemo.serial_number in self._added_serial_numbers:
            return

        try:
            coordinator = await async_register_device(hass, self._config_entry, wemo)
        except pywemo.PyWeMoException as err:
            if wemo.serial_number not in self._failed_serial_numbers:
                self._failed_serial_numbers.add(wemo.serial_number)
                _LOGGER.error(
                    "Unable to add WeMo %s %s: %s", repr(wemo), wemo.host, err
                )
            return

        platforms = set(WEMO_MODEL_DISPATCH.get(wemo.model_name, [Platform.SWITCH]))
        platforms.add(Platform.SENSOR)
        for platform in platforms:
            # Three cases:
            # - Platform is loaded, dispatch discovery
            # - Platform is being loaded, add to backlog
            # - First time we see platform, we need to load it and initialize the backlog

            if platform in self._dispatch_callbacks:
                await self._dispatch_callbacks[platform](coordinator)
            elif platform in self._dispatch_backlog:
                self._dispatch_backlog[platform].append(coordinator)
            else:
                self._dispatch_backlog[platform] = [coordinator]
                hass.async_create_task(
                    hass.config_entries.async_forward_entry_setup(
                        self._config_entry, platform
                    )
                )

        self._added_serial_numbers.add(wemo.serial_number)
        self._failed_serial_numbers.discard(wemo.serial_number)

    async def async_connect_platform(
        self, platform: Platform, dispatch: DispatchCallback
    ) -> None:
        """Consider a platform as loaded and dispatch any backlog of discovered devices."""
        self._dispatch_callbacks[platform] = dispatch

        await gather_with_limited_concurrency(
            MAX_CONCURRENCY,
            *(
                dispatch(coordinator)
                for coordinator in self._dispatch_backlog.pop(platform)
            ),
        )

    async def async_unload_platforms(self, hass: HomeAssistant) -> bool:
        """Forward the unloading of an entry to platforms."""
        platforms: set[Platform] = set(self._dispatch_backlog.keys())
        platforms.update(self._dispatch_callbacks.keys())
        return await hass.config_entries.async_unload_platforms(
            self._config_entry, platforms
        )


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
        self._discover_job: HassJob[[datetime], Coroutine[Any, Any, None]] | None = None

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
            if not self._discover_job:
                self._discover_job = HassJob(self.async_discover_and_schedule)
            self._stop = async_call_later(
                self._hass,
                self._scan_delay,
                self._discover_job,
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
        for device in await gather_with_limited_concurrency(
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
