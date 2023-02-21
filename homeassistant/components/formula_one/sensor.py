"""Support for Formula 1 sensors."""
from __future__ import annotations

import logging
from typing import Any

import ergast_py as ergast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, F1_DISCOVERY_NEW, F1_STATE_MULTIPLE
from .coordinator import F1UpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure sensors from a config entry created in the integrations UI."""

    @callback
    def async_setup_sensors() -> None:
        _LOGGER.debug("Handling new drivers/constructors/races")

        coordinator: F1UpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

        entities: list[F1Sensor] = []

        for standing in coordinator.constructor_standings:
            new_cp_sensor = F1ConstructorPositionSensor(coordinator, standing.position)
            if new_cp_sensor.unique_id not in coordinator.entity_ids:
                entities.append(new_cp_sensor)

            new_cn_sensor = F1ConstructorNameSensor(
                coordinator,
                standing.constructor.constructor_id,
                standing.constructor.name,
            )
            if new_cn_sensor.unique_id not in coordinator.entity_ids:
                entities.append(new_cn_sensor)

        for standing in coordinator.driver_standings:
            new_dp_sensor = F1DriverPositionSensor(coordinator, standing.position)
            if new_dp_sensor.unique_id not in coordinator.entity_ids:
                entities.append(new_dp_sensor)

            new_dn_sensor = F1DriverNameSensor(
                coordinator,
                standing.driver.driver_id,
            )
            if new_dn_sensor.unique_id not in coordinator.entity_ids:
                entities.append(new_dn_sensor)

        for race in coordinator.races:
            new_race_sensor = F1RaceSensor(coordinator, race.round_no)
            if new_race_sensor.unique_id not in coordinator.entity_ids:
                entities.append(new_race_sensor)

        next_race_sensor = F1NextRaceSensor(coordinator)
        if next_race_sensor.unique_id not in coordinator.entity_ids:
            entities.append(next_race_sensor)

        async_add_entities(entities)

    async_setup_sensors()

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, F1_DISCOVERY_NEW, async_setup_sensors)
    )


class F1Sensor(CoordinatorEntity):
    """Base class for a F1 sensor."""

    def _update_value(self) -> None:
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_value()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle event when sensor is added."""
        await super().async_added_to_hass()
        if self.unique_id is not None:
            unique_id: str = self.unique_id
            self.coordinator.entity_ids.append(unique_id)

    async def async_will_remove_from_hass(self) -> None:
        """Handle event when entity is removed."""
        await super().async_will_remove_from_hass()
        if self.unique_id is not None:
            unique_id: str = self.unique_id
            self.coordinator.entity_ids.remove(unique_id)


class F1ConstructorPositionSensor(F1Sensor):
    """Representation of a F1 sensor."""

    def __init__(
        self,
        coordinator: F1UpdateCoordinator,
        position: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.position = position
        self._update_value()

    def _update_value(self) -> None:
        for standing in self.coordinator.constructor_standings:
            if standing.position == self.position:
                self._attr_state = standing.constructor.name
                self._attr_available = True
                return

        self._attr_available = False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        for standing in self.coordinator.constructor_standings:
            if standing.position == self.position:
                return {
                    "points": standing.points,
                    "nationality": standing.constructor.nationality,
                    "constructor_id": standing.constructor.constructor_id,
                    "season": self.coordinator.season,
                    "round": self.coordinator.round,
                    "position": standing.position,
                }

        return None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"f1-constructor-{self.position}"

    @property
    def name(self) -> str:
        """Return a friendly name."""
        return f"F1 Constructor {self.position:02}"


class F1ConstructorNameSensor(F1Sensor):
    """Representation of a F1 sensor."""

    def __init__(
        self,
        coordinator: F1UpdateCoordinator,
        constructor_id: str,
        constructor_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.constructor_id = constructor_id
        self.constructor_name = constructor_name
        self._update_value()

    def _update_value(self) -> None:
        for standing in self.coordinator.constructor_standings:
            if standing.constructor.constructor_id == self.constructor_id:
                self._attr_state = standing.position
                self._attr_available = True
                return

        self._attr_available = False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        for standing in self.coordinator.constructor_standings:
            if standing.constructor.constructor_id == self.constructor_id:
                return {
                    "points": standing.points,
                    "nationality": standing.constructor.nationality,
                    "constructor_id": standing.constructor.constructor_id,
                    "season": self.coordinator.season,
                    "round": self.coordinator.round,
                    "position": standing.position,
                }

        return None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"f1-constructor-{self.constructor_id}"

    @property
    def name(self) -> str:
        """Return a friendly name."""
        return f"F1 Constructor {self.constructor_name}"


class F1DriverPositionSensor(F1Sensor):
    """Representation of a F1 sensor."""

    def __init__(
        self,
        coordinator: F1UpdateCoordinator,
        position: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.position = position
        self._update_value()

    def _update_value(self) -> None:
        for standing in self.coordinator.driver_standings:
            if standing.position == self.position:
                self._attr_state = self.coordinator.get_driver_name(
                    standing.driver.driver_id
                )
                self._attr_available = True
                return

        self._attr_available = False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        for standing in self.coordinator.driver_standings:
            if standing.position == self.position:
                return {
                    "points": standing.points,
                    "nationality": standing.driver.nationality,
                    "team": standing.constructors[0].name
                    if len(standing.constructors) == 1
                    else F1_STATE_MULTIPLE,
                    "driver_id": standing.driver.driver_id,
                    "season": self.coordinator.season,
                    "round": self.coordinator.round,
                    "position": standing.position,
                }

        return None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"f1-driver-{self.position}"

    @property
    def name(self) -> str:
        """Return a friendly name."""
        return f"F1 Driver {self.position:02}"


class F1DriverNameSensor(F1Sensor):
    """Representation of a F1 sensor."""

    def __init__(
        self,
        coordinator: F1UpdateCoordinator,
        driver_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.driver_id = driver_id
        self._update_value()

    def _update_value(self) -> None:
        for standing in self.coordinator.driver_standings:
            if standing.driver.driver_id == self.driver_id:
                self._attr_state = standing.position
                self._attr_available = True
                return

        self._attr_available = False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        for standing in self.coordinator.driver_standings:
            if standing.driver.driver_id == self.driver_id:
                return {
                    "points": standing.points,
                    "nationality": standing.driver.nationality,
                    "team": standing.constructors[0].name
                    if len(standing.constructors) == 1
                    else F1_STATE_MULTIPLE,
                    "driver_id": standing.driver.driver_id,
                    "season": self.coordinator.season,
                    "round": self.coordinator.round,
                    "position": standing.position,
                }

        return None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"f1_driver_{self.driver_id}"

    @property
    def name(self) -> str:
        """Return a friendly name."""
        return f"F1 Driver {self.coordinator.get_driver_name(self.driver_id)}"


class F1RaceSensor(F1Sensor):
    """Representation of an F1 race sensor."""

    def __init__(
        self,
        coordinator: F1UpdateCoordinator,
        round_no: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.round_no = round_no
        self._update_value()

    def _update_value(self) -> None:
        race_info = self.coordinator.get_race_by_round(self.round_no)

        if race_info is None:
            self._attr_available = False
        else:
            self._attr_state = race_info.race_name
            self._attr_available = True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        race_info: ergast.Race = self.coordinator.get_race_by_round(self.round_no)

        return (
            {
                "season": race_info.season,
                "round": self.round_no,
                "start": race_info.date,
                "fp1_start": race_info.first_practice,
                "fp2_start": race_info.second_practice,
                "fp3_start": race_info.third_practice,
                "sprint_start": race_info.sprint,
                "quali_start": race_info.qualifying,
            }
            if race_info is not None
            else None
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"f1-race-{self.round_no}"

    @property
    def name(self) -> str:
        """Return a friendly name."""
        return f"F1 Race {self.round_no:02}"


class F1NextRaceSensor(F1Sensor):
    """Representation of an F1 race sensor."""

    def __init__(
        self,
        coordinator: F1UpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._update_value()

    def _update_value(self) -> None:
        race_info = self.coordinator.get_next_race()

        if race_info is None:
            self._attr_available = False
        else:
            self._attr_state = race_info.race_name
            self._attr_available = True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        race_info = self.coordinator.get_next_race()

        return (
            {
                "season": race_info.season,
                "round": race_info.round_no,
                "start": race_info.date,
                "fp1_start": race_info.first_practice,
                "fp2_start": race_info.second_practice,
                "fp3_start": race_info.third_practice,
                "quali_start": race_info.qualifying,
                "sprint_start": race_info.sprint,
            }
            if race_info is not None
            else None
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "f1-next-race"

    @property
    def name(self) -> str:
        """Return a friendly name."""
        return "F1 Next Race"
