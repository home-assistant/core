"""Sensor for De Lijn (Flemish public transport) departure information."""

from datetime import datetime
from types import MappingProxyType
from typing import Any, override

from pydelijn import (
    DeLijnAuthError,
    DeLijnClient,
    DeLijnConnectionError,
    DeLijnError,
    DeLijnNotFoundError,
    Passage,
    Stop,
)
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigSubentry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_NUMBER_OF_DEPARTURES,
    CONF_STOP_ID,
    CONF_STOP_NUMBER,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    SUBENTRY_TYPE_STOP,
)
from .coordinator import DeLijnConfigEntry, DeLijnCoordinator
from .util import stop_delijn_url, stop_title

PARALLEL_UPDATES = 0

CONF_NEXT_DEPARTURE = "next_departure"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_NEXT_DEPARTURE): [
            {
                vol.Required(CONF_STOP_ID): cv.string,
                vol.Optional(CONF_NUMBER_OF_DEPARTURES, default=5): cv.positive_int,
            }
        ],
    }
)


def _find_entry_by_api_key(
    hass: HomeAssistant, api_key: str
) -> DeLijnConfigEntry | None:
    """Return the existing De Lijn entry using this API key, if any."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_API_KEY] == api_key:
            return entry
    return None


def _is_stop_on_entry(entry: DeLijnConfigEntry, stop_number: str) -> bool:
    """Return whether a stop is already configured as a subentry of entry."""
    return any(
        subentry.unique_id == stop_number for subentry in entry.subentries.values()
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the legacy YAML configuration into config entries.

    One main entry is used per API key; each configured stop becomes a
    subentry of it. Subentries can only be created from a user-initiated
    flow, so each stop is validated here and added directly.

    Adding a subentry fires the entry's update listener as a separately
    scheduled task (not awaited here), which reloads the entry. That reload
    rebuilds every coordinator from entry.subentries as it stands at the
    moment it actually runs. If stops were added one at a time with an
    ``await`` in between (e.g. the API lookup), a scheduled reload can start
    and even finish while only some of the stops have been added, settling
    on an incomplete set with nothing left to correct it afterwards.
    Every stop is therefore first validated (the only part that awaits),
    and only then are all of the resulting subentries added back-to-back
    with no ``await`` between them, so nothing can run in between and act on
    a partial set. A reload is triggered once at the end regardless, both to
    apply the change promptly and as a safety net.
    """
    api_key = config[CONF_API_KEY]
    entry = _find_entry_by_api_key(hass, api_key)
    if entry is None:
        entry_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_API_KEY: api_key},
        )
        if entry_result.get("type") is FlowResultType.CREATE_ENTRY:
            entry = entry_result["result"]
        else:
            # A race created the entry between our lookup and this call.
            entry = _find_entry_by_api_key(hass, api_key)
    assert entry is not None

    client = DeLijnClient(api_key, async_get_clientsession(hass))
    any_failure = False
    to_add: list[tuple[Stop, int]] = []
    pending_numbers: set[str] = set()

    for departure in config[CONF_NEXT_DEPARTURE]:
        stop_id = departure[CONF_STOP_ID]
        issue_id = f"deprecated_yaml_import_issue_{stop_id}"

        if _is_stop_on_entry(entry, stop_id) or stop_id in pending_numbers:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            continue

        try:
            stop = await client.get_stop(stop_id)
        except DeLijnNotFoundError:
            reason: str | None = "invalid_stop"
        except DeLijnAuthError as err:
            LOGGER.error(
                "De Lijn rejected the API key while importing stop %s: %s",
                stop_id,
                err,
            )
            reason = "invalid_auth"
        except DeLijnConnectionError as err:
            LOGGER.error(
                "Error connecting to the De Lijn API while importing stop %s: %s",
                stop_id,
                err,
            )
            reason = "cannot_connect"
        except DeLijnError:
            LOGGER.exception("Unexpected error importing De Lijn stop %s", stop_id)
            reason = "unknown"
        else:
            reason = None

        if reason is not None:
            any_failure = True
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{reason}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "De Lijn",
                    "stop_id": stop_id,
                },
            )
            continue

        # A successful import, or one already configured in a prior
        # restart, resolves any previously reported import failure.
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        if _is_stop_on_entry(entry, stop.number) or stop.number in pending_numbers:
            continue

        pending_numbers.add(stop.number)
        to_add.append((stop, departure[CONF_NUMBER_OF_DEPARTURES]))

    for stop, number_of_departures in to_add:
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(
                    {
                        CONF_STOP_NUMBER: stop.number,
                        CONF_NUMBER_OF_DEPARTURES: number_of_departures,
                    }
                ),
                subentry_type=SUBENTRY_TYPE_STOP,
                title=stop_title(stop),
                unique_id=stop.number,
            ),
        )

    if to_add:
        await hass.config_entries.async_reload(entry.entry_id)

    generic_issue_id = f"deprecated_yaml_{DOMAIN}"
    if any_failure:
        # Don't tell the user to remove the YAML config while a stop still
        # needs it to retry; drop any stale notice from an earlier restart.
        ir.async_delete_issue(hass, HOMEASSISTANT_DOMAIN, generic_issue_id)
    else:
        ir.async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            generic_issue_id,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "De Lijn",
            },
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeLijnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the De Lijn sensors from a config entry, one per stop subentry."""
    for subentry_id, coordinator in entry.runtime_data.items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            [DeLijnSensor(coordinator, subentry)], config_subentry_id=subentry_id
        )


def _due_in_minutes(due_at: datetime | None) -> int | None:
    """Return the number of minutes from now until due_at."""
    if due_at is None:
        return None
    return round((due_at - dt_util.utcnow()).total_seconds() / 60)


def _bare_hex(colour: str | None) -> str | None:
    """Return a colour hex value without the leading #.

    The pre-config-flow integration exposed colours this way, and community
    dashboard cards prepend the # themselves.
    """
    if colour is None:
        return None
    return colour.removeprefix("#")


def _passage_attributes(index: int, passage: Passage) -> dict[str, Any]:
    """Return the legacy attribute mapping for a single passage."""
    line = passage.line
    return {
        "passage": index,
        "line_number": line.number,
        "direction": passage.direction,
        "final_destination": passage.destination,
        "due_at_schedule": (
            passage.due_at_schedule.isoformat() if passage.due_at_schedule else None
        ),
        "due_at_realtime": (
            passage.due_at_realtime.isoformat() if passage.due_at_realtime else None
        ),
        "due_in_min": _due_in_minutes(passage.due_at),
        "is_realtime": passage.is_realtime,
        "cancelled": passage.cancelled,
        "line_number_public": line.public_number,
        "line_desc": line.description,
        "line_transport_type": line.transport_type,
        "line_number_colourFront": _bare_hex(line.colour_front_hex),
        "line_number_colourFrontHex": _bare_hex(line.colour_front_hex),
        "line_number_colourBack": _bare_hex(line.colour_back_hex),
        "line_number_colourBackHex": _bare_hex(line.colour_back_hex),
        "line_number_colourFrontBorder": _bare_hex(line.colour_front_border_hex),
        "line_number_colourFrontBorderHex": _bare_hex(line.colour_front_border_hex),
        "line_number_colourBackBorder": _bare_hex(line.colour_back_border_hex),
        "line_number_colourBackBorderHex": _bare_hex(line.colour_back_border_hex),
    }


class DeLijnSensor(CoordinatorEntity[DeLijnCoordinator], SensorEntity):
    """Representation of the next De Lijn departure at a stop."""

    _attr_attribution = "Data provided by data.delijn.be"
    _attr_has_entity_name = True
    _attr_translation_key = "next_departure"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: DeLijnCoordinator, subentry: ConfigSubentry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        stop_number = subentry.data[CONF_STOP_NUMBER]
        self._stopname = subentry.title
        self._attr_unique_id = f"{stop_number}_next_departure"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stop_number)},
            name=subentry.title,
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=stop_delijn_url(stop_number),
            model="Stop",
            model_id=stop_number,
        )

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the due time of the next passage."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data[0].due_at

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return backward-compatible attributes for the community Lovelace card."""
        passages = self.coordinator.data
        if not passages:
            return {
                "stopname": self._stopname,
                "line_number_public": None,
                "line_transport_type": None,
                "final_destination": None,
                "due_at_schedule": None,
                "due_at_realtime": None,
                "is_realtime": None,
                "cancelled": None,
                "next_passages": [],
            }

        first = passages[0]
        return {
            "stopname": self._stopname,
            "line_number_public": first.line.public_number,
            "line_transport_type": first.line.transport_type,
            "final_destination": first.destination,
            "due_at_schedule": (
                first.due_at_schedule.isoformat() if first.due_at_schedule else None
            ),
            "due_at_realtime": (
                first.due_at_realtime.isoformat() if first.due_at_realtime else None
            ),
            "is_realtime": first.is_realtime,
            "cancelled": first.cancelled,
            "next_passages": [
                _passage_attributes(index, passage)
                for index, passage in enumerate(passages)
            ],
        }
