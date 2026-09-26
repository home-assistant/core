"""Real-time information about public transport departures in Norway."""

from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from random import randint
from typing import Any, cast, override

from aiohttp import ClientError
from enturclient import EnturPublicTransportData
import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SHOW_ON_MAP,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle, dt as dt_util

from .const import (
    API_CLIENT_NAME,
    ATTR_DELAY,
    ATTR_EXPECTED_AT,
    ATTR_NEXT_UP_AT,
    ATTR_NEXT_UP_DELAY,
    ATTR_NEXT_UP_IN,
    ATTR_NEXT_UP_REALTIME,
    ATTR_NEXT_UP_ROUTE,
    ATTR_NEXT_UP_ROUTE_ID,
    ATTR_REALTIME,
    ATTR_ROUTE,
    ATTR_ROUTE_ID,
    ATTR_STOP_ID,
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_PLATFORM_MODE,
    CONF_QUAY_IDS,
    CONF_STOP_ID,
    CONF_STOP_IDS,
    CONF_STOP_PLACE_NAME,
    CONF_WHITELIST_LINES,
    DEFAULT_ICON_KEY,
    DEFAULT_NAME,
    DOMAIN,
    ICONS,
    PLATFORM_MODE_ALL,
    PLATFORM_MODE_SELECTED,
    PLATFORM_MODE_STOP_PLACE,
    SUBENTRY_TYPE_STOP_PLACE,
)


@dataclass(frozen=True, slots=True)
class EnturStopConfiguration:
    """One logical group of Entur sensors to create."""

    stops: tuple[str, ...]
    quays: tuple[str, ...]
    line_whitelist: tuple[str, ...]
    expand_platforms: bool
    show_on_map: bool
    device_stop_id: str | None = None
    device_stop_name: str | None = None
    config_subentry_id: str | None = None


PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_STOP_IDS): probatio.All(cv.ensure_list, [cv.string]),
        probatio.Optional(CONF_EXPAND_PLATFORMS, default=True): cv.boolean,
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
        probatio.Optional(CONF_WHITELIST_LINES, default=[]): cv.ensure_list,
        probatio.Optional(CONF_OMIT_NON_BOARDING, default=True): cv.boolean,
        probatio.Optional(CONF_NUMBER_OF_DEPARTURES, default=2): probatio.All(
            cv.positive_int, probatio.Range(min=2, max=10)
        ),
    }
)


def due_in_minutes(timestamp: datetime) -> int:
    """Get the time in minutes from a timestamp."""
    if timestamp is None:
        return None
    diff = timestamp - dt_util.now()
    return int(diff.total_seconds() / 60)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Entur public transport sensor."""
    await _async_setup(hass, config, async_add_entities)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Entur sensors from a config entry."""
    await _async_setup(hass, entry.data, async_add_entities, entry.subentries.values())


async def _async_setup(
    hass: HomeAssistant,
    config: Mapping[str, Any],
    async_add_entities: AddEntitiesCallback | AddConfigEntryEntitiesCallback,
    subentries: Iterable[ConfigSubentry] = (),
) -> None:
    """Set up Entur sensors from configuration."""

    name = config[CONF_NAME]
    omit_non_boarding = config[CONF_OMIT_NON_BOARDING]
    number_of_departures = config[CONF_NUMBER_OF_DEPARTURES]

    for stop_config in _stop_configurations(config, subentries):
        entities = []
        data = EnturPublicTransportData(
            API_CLIENT_NAME.format(str(randint(100000, 999999))),
            stops=list(stop_config.stops),
            quays=list(stop_config.quays),
            line_whitelist=list(stop_config.line_whitelist),
            omit_non_boarding=omit_non_boarding,
            number_of_departures=number_of_departures,
            web_session=async_get_clientsession(hass),
        )

        try:
            if stop_config.expand_platforms:
                await data.expand_all_quays()
            await data.update()
        except (ClientError, TimeoutError) as err:
            raise PlatformNotReady from err

        proxy = EnturProxy(data)
        device_name = None
        if stop_config.device_stop_id:
            device_name = (
                f"{name} {stop_config.device_stop_name}"
                if stop_config.device_stop_name
                else None
            )
            with suppress(AttributeError, KeyError):
                device_name = device_name or (
                    f"{name} {data.get_stop_info(stop_config.device_stop_id).name}"
                )

        for place in data.all_stop_places_quays():
            try:
                given_name = f"{name} {data.get_stop_info(place).name}"
            except KeyError:
                given_name = f"{name} {place}"

            entities.append(
                EnturPublicTransportSensor(
                    proxy,
                    given_name,
                    place,
                    stop_config.show_on_map,
                    stop_config.device_stop_id,
                    device_name,
                    unique_id=(
                        place if stop_config.config_subentry_id is not None else None
                    ),
                )
            )

        if stop_config.config_subentry_id is None:
            async_add_entities(entities, True)
        else:
            cast(AddConfigEntryEntitiesCallback, async_add_entities)(
                entities,
                True,
                config_subentry_id=stop_config.config_subentry_id,
            )


def _string_values(value: Any) -> tuple[str, ...]:
    """Return string values stored in a config entry or subentry."""
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _stop_configurations(
    config: Mapping[str, Any], subentries: Iterable[ConfigSubentry]
) -> list[EnturStopConfiguration]:
    """Return sensor groups for legacy YAML and UI configuration."""
    configurations: list[EnturStopConfiguration] = []
    if stop_ids := _string_values(config.get(CONF_STOP_IDS)):
        configurations.append(
            EnturStopConfiguration(
                stops=tuple(stop_id for stop_id in stop_ids if "StopPlace" in stop_id),
                quays=tuple(stop_id for stop_id in stop_ids if "Quay" in stop_id),
                line_whitelist=_string_values(config.get(CONF_WHITELIST_LINES)),
                expand_platforms=bool(config[CONF_EXPAND_PLATFORMS]),
                show_on_map=bool(config[CONF_SHOW_ON_MAP]),
            )
        )

    for subentry in subentries:
        if (
            subentry.subentry_type != SUBENTRY_TYPE_STOP_PLACE
            or CONF_STOP_ID not in subentry.data
        ):
            continue

        stop_id = subentry.data[CONF_STOP_ID]
        if not isinstance(stop_id, str):
            continue
        mode = subentry.data.get(CONF_PLATFORM_MODE, PLATFORM_MODE_ALL)
        quay_ids = _string_values(subentry.data.get(CONF_QUAY_IDS))
        stops: tuple[str, ...]
        quays: tuple[str, ...]
        if mode == PLATFORM_MODE_SELECTED and quay_ids:
            stops = ()
            quays = quay_ids
            expand_platforms = False
        else:
            stops = (stop_id,)
            quays = ()
            expand_platforms = mode != PLATFORM_MODE_STOP_PLACE

        stop_place_name = subentry.data.get(CONF_STOP_PLACE_NAME)
        configurations.append(
            EnturStopConfiguration(
                stops=stops,
                quays=quays,
                line_whitelist=_string_values(subentry.data.get(CONF_WHITELIST_LINES)),
                expand_platforms=expand_platforms,
                show_on_map=bool(subentry.data.get(CONF_SHOW_ON_MAP, False)),
                device_stop_id=stop_id,
                device_stop_name=(
                    stop_place_name if isinstance(stop_place_name, str) else None
                ),
                config_subentry_id=subentry.subentry_id,
            )
        )
    return configurations


class EnturProxy:
    """Proxy for the Entur client.

    Ensure throttle to not hit rate limiting on the API.
    """

    def __init__(self, api):
        """Initialize the proxy."""
        self._api = api

    @Throttle(timedelta(seconds=15))
    async def async_update(self) -> None:
        """Update data in client."""
        await self._api.update()

    def get_stop_info(self, stop_id: str) -> dict:
        """Get info about specific stop place."""
        return self._api.get_stop_info(stop_id)


class EnturPublicTransportSensor(SensorEntity):
    """Implementation of a Entur public transport sensor."""

    _attr_attribution = "Data provided by entur.org under NLOD"

    def __init__(
        self,
        api: EnturProxy,
        name: str,
        stop: str,
        show_on_map: bool,
        device_stop_id: str | None = None,
        device_name: str | None = None,
        unique_id: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        self.api = api
        self._stop = stop
        self._show_on_map = show_on_map
        self._name = name
        if unique_id is not None:
            self._attr_unique_id = unique_id
        if device_stop_id and device_name:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device_stop_id)},
                name=device_name,
            )
        self._state: int | None = None
        self._icon = ICONS[DEFAULT_ICON_KEY]
        self._attributes: dict[str, str] = {}

    @property
    @override
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    @override
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self._state

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        self._attributes[ATTR_STOP_ID] = self._stop
        return self._attributes

    @property
    @override
    def native_unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return UnitOfTime.MINUTES

    @property
    @override
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return self._icon

    async def async_update(self) -> None:
        """Get the latest data and update the states."""
        await self.api.async_update()

        self._attributes = {}

        data: EnturPublicTransportData = self.api.get_stop_info(self._stop)
        if data is None:
            self._state = None
            return

        if self._show_on_map and data.latitude and data.longitude:
            self._attributes[CONF_LATITUDE] = data.latitude
            self._attributes[CONF_LONGITUDE] = data.longitude

        if not (calls := data.estimated_calls):
            self._state = None
            return

        self._state = due_in_minutes(calls[0].expected_departure_time)
        self._icon = ICONS.get(calls[0].transport_mode, ICONS[DEFAULT_ICON_KEY])

        self._attributes[ATTR_ROUTE] = calls[0].front_display
        self._attributes[ATTR_ROUTE_ID] = calls[0].line_id
        self._attributes[ATTR_EXPECTED_AT] = calls[0].expected_departure_time.strftime(
            "%H:%M"
        )
        self._attributes[ATTR_REALTIME] = calls[0].is_realtime
        self._attributes[ATTR_DELAY] = calls[0].delay_in_min

        number_of_calls = len(calls)
        if number_of_calls < 2:
            return

        self._attributes[ATTR_NEXT_UP_ROUTE] = calls[1].front_display
        self._attributes[ATTR_NEXT_UP_ROUTE_ID] = calls[1].line_id
        self._attributes[ATTR_NEXT_UP_AT] = calls[1].expected_departure_time.strftime(
            "%H:%M"
        )
        self._attributes[ATTR_NEXT_UP_IN] = (
            f"{due_in_minutes(calls[1].expected_departure_time)} min"
        )
        self._attributes[ATTR_NEXT_UP_REALTIME] = calls[1].is_realtime
        self._attributes[ATTR_NEXT_UP_DELAY] = calls[1].delay_in_min

        if number_of_calls < 3:
            return

        for i, call in enumerate(calls[2:]):
            key_name = f"departure_#{i + 3}"
            self._attributes[key_name] = (
                f"{'' if bool(call.is_realtime) else 'ca. '}"
                f"{call.expected_departure_time.strftime('%H:%M')} {call.front_display}"
            )
