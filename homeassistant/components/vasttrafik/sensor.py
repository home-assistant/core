"""Support for Västtrafik public transport."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import vasttrafik
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_DELAY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import now

from . import VasttrafikConfigEntry
from .const import (
    CONF_DEPARTURES,
    CONF_FROM,
    CONF_HEADING,
    CONF_KEY,
    CONF_LINES,
    CONF_SECRET,
    CONF_STATION_GID,
    CONF_TRACKS,
    DEFAULT_DELAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

# Platform schema for YAML configuration (backward compatibility)
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_KEY): cv.string,
        vol.Required(CONF_SECRET): cv.string,
        vol.Required(CONF_DEPARTURES): [
            {
                vol.Required(CONF_FROM): cv.string,
                vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): cv.positive_int,
                vol.Optional(CONF_HEADING): cv.string,
                vol.Optional(CONF_LINES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_NAME): cv.string,
            }
        ],
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the departure sensor from YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2026.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Västtrafik",
            },
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VasttrafikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Västtrafik sensor based on a config entry."""
    planner = entry.runtime_data

    for subentry in entry.subentries.values():
        async_add_entities(
            [
                VasttrafikDepartureSensor(
                    planner=planner,
                    name=subentry.data[CONF_NAME],
                    station_gid=subentry.data[CONF_STATION_GID],
                    heading=subentry.data.get(CONF_HEADING, ""),
                    lines=subentry.data[CONF_LINES],
                    tracks=subentry.data[CONF_TRACKS],
                    delay=subentry.data[CONF_DELAY],
                    config_entry_id=entry.entry_id,
                    subentry_id=subentry.subentry_id,
                )
            ],
            update_before_add=True,
            config_subentry_id=subentry.subentry_id,
        )


class VasttrafikDepartureSensor(SensorEntity):
    """Implementation of a Vasttrafik Departure Sensor."""

    _attr_attribution = "Data provided by Västtrafik"
    _attr_icon = "mdi:train"
    _attr_has_entity_name = True

    def __init__(
        self,
        planner: vasttrafik.JournyPlanner,
        name: str,
        station_gid: str,
        heading: str,
        lines: list[str],
        tracks: list[str],
        delay: int,
        config_entry_id: str,
        subentry_id: str,
    ) -> None:
        """Initialize the sensor."""
        self._planner = planner
        self._attr_name = name
        self._station_gid = station_gid
        self._heading_name = heading
        self._lines = lines if lines else None
        self._tracks = tracks if tracks else None
        self._delay = timedelta(minutes=delay)
        self._departureboard: Any = None
        self._state: str | None = None
        self._attributes: dict[str, Any] | None = None

        # Build descriptive device name with filters (like Ollama shows model)
        device_name_parts = [f"Departure: {self._attr_name}"]

        # Add destination filter if specified
        if heading:
            device_name_parts.append(f"→ {heading}")

        # Add line filter if specified
        if lines:
            lines_str = ", ".join(str(line) for line in lines)
            device_name_parts.append(f"Lines: {lines_str}")

        # Add track filter if specified
        if tracks:
            tracks_str = ", ".join(str(track) for track in tracks)
            device_name_parts.append(f"Tracks: {tracks_str}")

        device_name = " • ".join(device_name_parts)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=device_name,
            manufacturer="Västtrafik",
            model="Departure Board",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

        self._attr_unique_id = subentry_id

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        return self._attributes

    @property
    def native_value(self) -> str | None:
        """Return the next departure time."""
        return self._state

    async def async_update(self) -> None:
        """Get the departure board."""
        try:
            self._departureboard = await self.hass.async_add_executor_job(
                self._planner.departureboard,
                self._station_gid,
                now() + self._delay,
                None,
            )
        except vasttrafik.Error:
            _LOGGER.debug("Unable to read departure board")
            self._departureboard = None

        if not self._departureboard:
            _LOGGER.debug(
                "No departures from departure station %s to destination station %s",
                self._attr_name,
                self._heading_name,
            )
            self._state = None
            self._attributes = {}
        else:
            departures_list = []
            next_departure = None
            total_departures = len(self._departureboard)

            _LOGGER.debug(
                "Processing %d departures for %s (line_filter=%s, track_filter=%s, heading_filter=%s)",
                total_departures,
                self._attr_name,
                self._lines,
                self._tracks,
                self._heading_name,
            )

            for departure in self._departureboard:
                service_journey = departure.get("serviceJourney", {})
                line = service_journey.get("line", {})

                if departure.get("isCancelled"):
                    continue

                stop_point = departure.get("stopPoint", {})
                line_name = line.get("shortName")
                platform = stop_point.get("platform")

                # Apply line filter if specified
                line_matches = not self._lines or line_name in self._lines

                # Apply track filter if specified
                track_matches = not self._tracks or platform in self._tracks

                # Heading name match if specified
                heading_name_match = (
                    not self._heading_name
                    or service_journey.get("direction") == self._heading_name
                )

                _LOGGER.debug(
                    "Departure: line=%s, platform=%s, line_matches=%s, track_matches=%s, heading_name_match=%s",
                    line_name,
                    platform,
                    line_matches,
                    track_matches,
                    heading_name_match,
                )

                if line_matches and track_matches and heading_name_match:
                    # Parse departure time
                    departure_time = None
                    if "estimatedOtherwisePlannedTime" in departure:
                        try:
                            departure_time = datetime.fromisoformat(
                                departure["estimatedOtherwisePlannedTime"]
                            ).strftime("%H:%M")
                        except ValueError:
                            departure_time = departure["estimatedOtherwisePlannedTime"]

                    # Set the next departure as the sensor state (first valid one)
                    if next_departure is None:
                        next_departure = departure_time

                    # Build departure info for attributes
                    departure_info = {
                        "time": departure_time,
                        "line": line.get("shortName"),
                        "direction": service_journey.get("direction"),
                        "track": stop_point.get("platform"),
                        "accessibility": "wheelChair"
                        if line.get("isWheelchairAccessible")
                        else None,
                        "line_color": line.get("backgroundColor"),
                        "line_text_color": line.get("foregroundColor"),
                    }

                    departures_list.append(
                        {k: v for k, v in departure_info.items() if v is not None}
                    )

            # Set sensor state to next departure time
            self._state = next_departure

            _LOGGER.debug(
                "Departure board update complete: found %d matching departures, next_departure=%s",
                len(departures_list),
                next_departure,
            )

            # Set attributes with multiple departures and general info
            self._attributes = {
                "departures": departures_list,
                "station": self._attr_name,
                "destination": self._heading_name
                if self._heading_name
                else "Any direction",
                "line_filter": self._lines if self._lines else None,
                "track_filter": self._tracks if self._tracks else None,
                "delay_minutes": self._delay.seconds // 60 % 60,
                "next_update": (now() + timedelta(seconds=120)).strftime("%H:%M:%S"),
            }

            # Remove None values
            self._attributes = {
                k: v for k, v in self._attributes.items() if v is not None
            }
