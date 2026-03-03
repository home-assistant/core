"""Sensor platform for NSW Fuel Check Integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PRICE_UNIT
from .coordinator import NSWFuelCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .data import NSWFuelConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NSWFuelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for NSW Fuel Check from a config entry."""
    coordinator: NSWFuelCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady from err

    nicknames = config_entry.data.get("nicknames", {})

    sensors: list[SensorEntity] = []

    sensors.extend(create_favorite_station_sensors(coordinator, nicknames))

    sensors.extend(create_cheapest_fuel_sensors(coordinator))

    if sensors:
        async_add_entities(sensors)


class FuelPriceSensor(CoordinatorEntity[NSWFuelCoordinator], SensorEntity):
    """Sensor for user's selected favorite stations and fuel type."""

    _attr_native_unit_of_measurement = PRICE_UNIT
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NSWFuelCoordinator,
        nickname: str,
        station_code: int,
        au_state: str,
        station_name: str,
        fuel_type: str,
    ) -> None:
        """Initialise favorite fuel price sensor."""
        super().__init__(coordinator)

        self._nickname = nickname
        self._station_code = station_code
        self._au_state = au_state
        self._station_name = station_name
        self._fuel_type = fuel_type
        self._attr_unique_id = f"{DOMAIN}_{station_code}_{au_state}_{fuel_type}"
        self._attr_attribution = _attribution_for_state(au_state)

    @property
    def device_info(self) -> DeviceInfo:
        """Device/Service/Location information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"location_{self._nickname}")},
            name=self._nickname,
            manufacturer=self._attr_attribution,
            model="Fuel Location",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state/value of the sensor."""
        if not self.coordinator.data:
            return None

        p = (
            self.coordinator.data.get("favorites", {})
            .get((self._station_code, self._au_state), {})
            .get(self._fuel_type)
        )
        return p.price if p else None

    @property
    def name(self) -> str:
        """Return human-readable sensor name."""
        return f"{self._station_name} {self._fuel_type}"

    @property
    def icon(self) -> str | None:
        """Return icon for user interface."""
        return "mdi:gas-station"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Label the sensor with fuel station numeric identifier."""
        attrs = {}

        if self._station_code is not None:
            attrs["station_code"] = self._station_code

        return attrs


class CheapestFuelPriceSensor(CoordinatorEntity[NSWFuelCoordinator], SensorEntity):
    """Cheapest fuel price sensors for a nickname, fuel type."""

    _attr_native_unit_of_measurement = PRICE_UNIT
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NSWFuelCoordinator,
        nickname: str,
        rank: int,
        au_state: str | None = None,
    ) -> None:
        """Initialise cheapest fuel price sensor."""
        super().__init__(coordinator)

        self._nickname = nickname
        self._rank = rank
        self._index = rank - 1

        # Use nickname in unique id & name (therefore entity id) so user can distinguish
        self._attr_unique_id = f"{DOMAIN}_cheapest_{nickname}_{rank}"
        self._attr_name = f"Cheapest {nickname} #{rank}"

        self._au_state = au_state
        self._attr_attribution = _attribution_for_state(au_state)

        _LOGGER.debug(
            "Creating %s with unique_id=%s",
            self.entity_id,
            self._attr_unique_id,
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Device/Service/Location information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"location_{self._nickname}")},
            name=self._nickname,
            manufacturer=self._attr_attribution,
            model="Fuel Station Prices",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state/value of the sensor."""
        cd = self.coordinator.data or {}
        pd = cd.get("cheapest", {}).get(self._nickname, [])

        if len(pd) <= self._index:
            return None

        return pd[self._index]["price"]

    @property
    def icon(self) -> str | None:
        """Return icon for user interface."""
        if self._rank == 1:
            return "mdi:gas-station-in-use"
        return "mdi:gas-station"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Add attributes for display in the user interface.

        Station name and fuel type are dynamic (as well as sensor value/price).
        User needs a way of identifying which fuel station this sensor refers to.
        """
        cd = self.coordinator.data or {}
        pd = cd.get("cheapest", {}).get(self._nickname, [])

        if len(pd) <= self._index:
            return None

        station_price = pd[self._index]

        return {
            "station_code": station_price["station_code"],
            "station_name": station_price["station_name"],
            "rank": self._rank,
            "fuel_type": station_price["fuel_type"],
            "price": station_price["price"],
        }


def create_favorite_station_sensors(
    coordinator: NSWFuelCoordinator,
    nicknames: dict[str, dict[str, Any]],
) -> list[FuelPriceSensor]:
    """Create FuelPriceSensor entities for user's favorites from config entry data."""
    sensors: list[FuelPriceSensor] = []

    for nickname, nickname_data in nicknames.items():
        for station in nickname_data.get("stations", []):
            station_code = station["station_code"]
            au_state = station["au_state"]
            station_name = station["station_name"]
            fuel_types = station.get("fuel_types", [])

            if not fuel_types:
                _LOGGER.warning(
                    "Station %s (%s) has no fuel_types configured",
                    station_name,
                    au_state,
                )
                continue

            _LOGGER.debug(
                "Creating favorite sensors for station %s (%s)",
                station_name,
                station_code,
            )

            sensors.extend(
                FuelPriceSensor(
                    coordinator=coordinator,
                    nickname=nickname,
                    station_code=station_code,
                    au_state=au_state,
                    station_name=station_name,
                    fuel_type=fuel_type,
                )
                for fuel_type in fuel_types
            )

    return sensors


def create_cheapest_fuel_sensors(
    coordinator: NSWFuelCoordinator,
) -> list[CheapestFuelPriceSensor]:
    """Create CheapestFuelPriceSensor entities for all nicknames.

    Always create 2 sensors per nickname for rank 1 and 2.
    """
    sensors: list[CheapestFuelPriceSensor] = []

    cd = coordinator.data or {}

    for nickname in coordinator.nicknames:
        entries = cd.get("cheapest", {}).get(nickname, [])

        for rank in (1, 2):
            au_state = None
            if len(entries) >= rank:
                entry = entries[rank - 1]
                au_state = entry.get("au_state")

            sensors.append(
                CheapestFuelPriceSensor(
                    coordinator=coordinator,
                    nickname=nickname,
                    rank=rank,
                    au_state=au_state,
                )
            )

    return sensors


def _attribution_for_state(au_state: str | None) -> str:
    """Return the appropriate attribution string for Australian state."""
    return "FuelCheck TAS" if au_state == "TAS" else "NSW Government FuelCheck"
