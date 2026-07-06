"""Support for exposing NX584 elements as sensors."""

import logging
import threading
import time
from typing import Any, override

from nx584 import client as nx584_client
import requests
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    entity_platform,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import NX584ConfigEntry
from .const import (
    CONF_EXCLUDE_ZONES,
    CONF_ZONE_TYPES,
    DOMAIN,
    EXCLUDE_ZONES_SCHEMA,
    ZONE_TYPES_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5007
BYPASS_ZONE_FLAGS = {"Bypass", "Inhibit"}
SERVICE_BYPASS = "bypass"
SERVICE_UNBYPASS = "unbypass"

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_EXCLUDE_ZONES, default=[]): EXCLUDE_ZONES_SCHEMA,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_ZONE_TYPES, default={}): ZONE_TYPES_SCHEMA,
    }
)


def _zone_flags_indicate_bypass(zone_flags: list[str]) -> bool:
    """Return if NX584 zone condition flags indicate bypass."""
    return not BYPASS_ZONE_FLAGS.isdisjoint(zone_flags)


def _build_zone_sensors(
    client: nx584_client.Client,
    exclude: list[int],
    zone_types: dict[int, BinarySensorDeviceClass],
    entry_id: str,
) -> dict[int, NX584ZoneSensor] | None:
    """Fetch the zones from the panel and build the zone sensor map."""
    try:
        zones = client.list_zones()
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error("Unable to connect to NX584: %s", str(ex))
        return None

    version = [int(v) for v in client.get_version().split(".")]
    if version < [1, 1]:
        _LOGGER.error("NX584 is too old to use for sensors (>=0.2 required)")
        return None

    return {
        zone["number"]: NX584ZoneSensor(
            zone,
            zone_types.get(zone["number"], BinarySensorDeviceClass.OPENING),
            client,
            entry_id,
        )
        for zone in zones
        if zone["number"] not in exclude
    }


def _async_register_services() -> None:
    """Register the bypass/unbypass entity services for zone sensors."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(SERVICE_BYPASS, None, "zone_bypass")
    platform.async_register_entity_service(SERVICE_UNBYPASS, None, "zone_unbypass")


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the NX584 binary sensor platform from YAML, importing it as a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "NX584",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "NX584",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NX584ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NX584 binary sensor platform from a config entry."""
    data = entry.runtime_data
    exclude_zones = entry.options.get(CONF_EXCLUDE_ZONES, [])
    zone_types = entry.options.get(CONF_ZONE_TYPES, {})

    zone_sensors = await hass.async_add_executor_job(
        _build_zone_sensors, data.client, exclude_zones, zone_types, entry.entry_id
    )
    if not zone_sensors:
        _LOGGER.warning("No zones found on NX584")
        return

    async_add_entities(zone_sensors.values())
    watcher = NX584Watcher(data.client, zone_sensors)
    watcher.start()

    _async_register_services()


class NX584ZoneSensor(BinarySensorEntity):
    """Representation of a NX584 zone as a sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        zone: dict[str, Any],
        zone_type: BinarySensorDeviceClass,
        client: nx584_client.Client,
        entry_id: str,
    ) -> None:
        """Initialize the nx594 binary sensor."""
        self._zone = zone
        self._attr_device_class = zone_type
        self._client = client
        self._attr_unique_id = f"{entry_id}_zone_{zone['number']}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)})

    @property
    @override
    def name(self):
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

    def zone_bypass(self) -> None:
        """Bypass this zone."""
        self._client.set_bypass(self._zone["number"], True)

    def zone_unbypass(self) -> None:
        """Un-bypass this zone."""
        self._client.set_bypass(self._zone["number"], False)


class NX584Watcher(threading.Thread):
    """Event listener thread to process NX584 events."""

    def __init__(self, client, zone_sensors):
        """Initialize NX584 watcher thread."""
        super().__init__()
        self.daemon = True
        self._client = client
        self._zone_sensors = zone_sensors

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

    def _set_zones_available(self, available: bool) -> None:
        """Mark all zone sensors as (un)available and refresh their state."""
        for zone_sensor in self._zone_sensors.values():
            if zone_sensor.available != available:
                zone_sensor._attr_available = available  # noqa: SLF001
                zone_sensor.schedule_update_ha_state()

    def _run(self):
        """Throw away any existing events so we don't replay history."""
        self._client.get_events()
        self._set_zones_available(True)
        while True:
            if events := self._client.get_events():
                self._process_events(events)

    @override
    def run(self):
        """Run the watcher."""
        while True:
            try:
                self._run()
            except requests.exceptions.ConnectionError:
                _LOGGER.error("Failed to reach NX584 server")
                self._set_zones_available(False)
                time.sleep(10)
