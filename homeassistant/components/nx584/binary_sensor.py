"""Support for exposing NX584 elements as sensors."""

from collections.abc import Mapping
import logging
import threading
from typing import Any, override

from nx584 import client as nx584_client
import probatio
import requests
from requests import PreparedRequest, Response
from requests.adapters import HTTPAdapter

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import NX584ConfigEntry, async_import_yaml, create_client
from .const import CONF_EXCLUDE_ZONES, CONF_ZONE_TYPES, DEFAULT_HOST, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

BYPASS_ZONE_FLAGS = {"Bypass", "Inhibit"}

# How long the server holds an event request open when there is nothing new.
EVENTS_POLL_TIMEOUT = 60
# pynx584 sets no transport timeout, so a stalled server would block forever.
EVENTS_REQUEST_TIMEOUT = EVENTS_POLL_TIMEOUT + 5

ZONE_TYPES_SCHEMA = probatio.Schema(
    {cv.positive_int: BINARY_SENSOR_DEVICE_CLASSES_SCHEMA}
)

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_EXCLUDE_ZONES, default=[]): probatio.All(
            probatio.EnsureList(), [cv.positive_int]
        ),
        probatio.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(CONF_ZONE_TYPES, default={}): ZONE_TYPES_SCHEMA,
    }
)


def _zone_flags_indicate_bypass(zone_flags: list[str]) -> bool:
    """Return if NX584 zone condition flags indicate bypass."""
    return not BYPASS_ZONE_FLAGS.isdisjoint(zone_flags)


def _fetch_zones(client: nx584_client.Client) -> tuple[list[dict[str, Any]], str]:
    """Return the zones and the version of the server."""
    return client.list_zones(), client.get_version()


class _TimeoutAdapter(HTTPAdapter):
    """Transport adapter that bounds every request of the watcher."""

    @override
    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: Any = None,
        verify: bool | str = True,
        cert: Any = None,
        proxies: Mapping[str, str] | None = None,
    ) -> Response:
        """Send the request with the watcher timeout."""
        return super().send(
            request, stream, EVENTS_REQUEST_TIMEOUT, verify, cert, proxies
        )


def create_watcher_client(host: str, port: int) -> nx584_client.Client:
    """Create a client for the watcher thread whose requests time out."""
    client = create_client(host, port)
    client._session.mount("http://", _TimeoutAdapter())  # noqa: SLF001
    return client


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML platform into a config entry."""
    await async_import_yaml(
        hass,
        Platform.BINARY_SENSOR,
        {
            CONF_HOST: config[CONF_HOST],
            CONF_PORT: config[CONF_PORT],
            CONF_EXCLUDE_ZONES: config[CONF_EXCLUDE_ZONES],
            CONF_ZONE_TYPES: config[CONF_ZONE_TYPES],
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NX584ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NX584 zone sensors from a config entry."""
    client = entry.runtime_data
    exclude: list[int] = entry.options.get(CONF_EXCLUDE_ZONES, [])
    zone_types: dict[str, str] = entry.options.get(CONF_ZONE_TYPES, {})

    zones, version = await hass.async_add_executor_job(_fetch_zones, client)
    if [int(v) for v in version.split(".")] < [1, 1]:
        _LOGGER.error("NX584 is too old to use for sensors (>=0.2 required)")
        return

    zone_sensors = {
        zone["number"]: NX584ZoneSensor(
            zone,
            BinarySensorDeviceClass(
                zone_types.get(str(zone["number"]), BinarySensorDeviceClass.OPENING)
            ),
        )
        for zone in zones
        if zone["number"] not in exclude
    }
    if zone_sensors:
        async_add_entities(zone_sensors.values())
        watcher = NX584Watcher(
            create_watcher_client(entry.data[CONF_HOST], entry.data[CONF_PORT]),
            zone_sensors,
        )
        entry.async_on_unload(watcher.stop)
        watcher.start()
    else:
        _LOGGER.warning("No zones found on NX584")


class NX584ZoneSensor(BinarySensorEntity):
    """Representation of a NX584 zone as a sensor."""

    _attr_should_poll = False

    def __init__(
        self, zone: dict[str, Any], zone_type: BinarySensorDeviceClass
    ) -> None:
        """Initialize the nx594 binary sensor."""
        self._zone = zone
        self._attr_device_class = zone_type

    @property
    @override
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return self._zone["name"]

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        # True means "faulted" or "open" or "abnormal state"
        return self._zone["state"]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "zone_number": self._zone["number"],
            "bypassed": self._zone.get("bypassed", False),
        }


class NX584Watcher(threading.Thread):
    """Event listener thread to process NX584 events."""

    def __init__(self, client, zone_sensors) -> None:
        """Initialize NX584 watcher thread."""
        super().__init__()
        self.daemon = True
        self._client = client
        self._zone_sensors = zone_sensors
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Ask the watcher to stop once the pending request returns."""
        self._stop_event.set()

    def _process_zone_event(self, event):
        zone = event["zone"]
        if not (zone_sensor := self._zone_sensors.get(zone)):
            return
        zone_sensor._zone["state"] = event["zone_state"]  # noqa: SLF001
        if "zone_flags" in event:
            zone_sensor._zone["bypassed"] = _zone_flags_indicate_bypass(  # noqa: SLF001
                event["zone_flags"]
            )
        zone_sensor.schedule_update_ha_state()

    def _process_events(self, events):
        for event in events:
            if event.get("type") == "zone_status":
                self._process_zone_event(event)

    def _run(self):
        """Throw away any existing events so we don't replay history."""
        self._client.get_events(timeout=EVENTS_POLL_TIMEOUT)
        while not self._stop_event.is_set():
            events = self._client.get_events(timeout=EVENTS_POLL_TIMEOUT)
            if events and not self._stop_event.is_set():
                self._process_events(events)

    @override
    def run(self):
        """Run the watcher."""
        while not self._stop_event.is_set():
            try:
                self._run()
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ):
                if self._stop_event.is_set():
                    return
                _LOGGER.error("Failed to reach NX584 server")
                self._stop_event.wait(10)
