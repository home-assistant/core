"""Support for Formula 1 sensors."""
from __future__ import annotations

import logging
from typing import Any

import ergast_py as ergast

from homeassistant.components.sensor import RestoreSensor
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import F1Data, F1UpdateCoordinator
from .const import (
    DOMAIN,
    F1_CONSTRUCTOR_ATTRIBS_UNAVAILABLE,
    F1_DISCOVERY_NEW,
    F1_DRIVER_ATTRIBS_UNAVAILABLE,
    F1_RACE_ATTRIBS_UNAVAILABLE,
    F1_STATE_MULTIPLE,
    F1_STATE_UNAVAILABLE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure sensors from a config entry created in the integrations UI."""

    @callback
    def async_setup_sensors() -> None:
        _LOGGER.info("Handling new drivers/constructors/races")

        coordinator: F1UpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

        entities: list[F1Sensor] = []

        for standing in coordinator.f1_data.constructor_standings:
            new_cp_sensor = F1ConstructorPositionSensor(coordinator, standing.position)
            if new_cp_sensor.unique_id not in coordinator.f1_data.entity_ids:
                entities.append(new_cp_sensor)

            new_cn_sensor = F1ConstructorNameSensor(
                coordinator,
                standing.constructor.constructor_id,
                standing.constructor.name,
            )
            if new_cn_sensor.unique_id not in coordinator.f1_data.entity_ids:
                entities.append(new_cn_sensor)

        for standing in coordinator.f1_data.driver_standings:
            new_dp_sensor = F1DriverPositionSensor(coordinator, standing.position)
            if new_dp_sensor.unique_id not in coordinator.f1_data.entity_ids:
                entities.append(new_dp_sensor)

            new_dn_sensor = F1DriverNameSensor(
                coordinator,
                standing.driver.driver_id,
            )
            if new_dn_sensor.unique_id not in coordinator.f1_data.entity_ids:
                entities.append(new_dn_sensor)

        for race in coordinator.f1_data.races:
            new_race_sensor = F1RaceSensor(coordinator, race.round_no)
            if new_race_sensor.unique_id not in coordinator.f1_data.entity_ids:
                entities.append(new_race_sensor)

        next_race_sensor = F1NextRaceSensor(coordinator)
        if next_race_sensor.unique_id not in coordinator.f1_data.entity_ids:
            entities.append(next_race_sensor)

        async_add_entities(entities)

    async_setup_sensors()

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, F1_DISCOVERY_NEW, async_setup_sensors)
    )


class F1Sensor(CoordinatorEntity, RestoreSensor):
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
        f1_data: F1Data = self.coordinator.f1_data
        if self.unique_id is not None:
            unique_id: str = self.unique_id
            f1_data.entity_ids.append(unique_id)

    async def async_will_remove_from_hass(self) -> None:
        """Handle event when entity is removed."""
        await super().async_will_remove_from_hass()
        f1_data: F1Data = self.coordinator.f1_data
        if self.unique_id is not None:
            unique_id: str = self.unique_id
            f1_data.entity_ids.remove(unique_id)


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
        standing_info = self.coordinator.f1_data.get_constructor_standing_by_position(
            self.position
        )

        if standing_info is None:
            self._attr_native_value = F1_STATE_UNAVAILABLE
            self._attr_available = False
        else:
            self._attr_native_value = standing_info.constructor.name
            self._attr_available = False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        standing_info = self.coordinator.f1_data.get_constructor_standing_by_position(
            self.position
        )

        if standing_info is None:
            return F1_CONSTRUCTOR_ATTRIBS_UNAVAILABLE

        ret = {}
        ret["points"] = standing_info.points
        ret["nationality"] = standing_info.constructor.nationality
        ret["constructor_id"] = standing_info.constructor.constructor_id
        ret["season"] = self.coordinator.f1_data.season
        ret["round"] = self.coordinator.f1_data.round
        ret["position"] = standing_info.position

        return ret

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self.position < 10:
            return f"f1-constructor-0{self.position}"

        return f"f1-constructor-{self.position}"

    @property
    def name(self) -> str:
        """Return a friendly name."""
        if self.position < 10:
            return f"F1 Constructor 0{self.position}"

        return f"F1 Constructor {self.position}"


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
        standing_info = self.coordinator.f1_data.get_constructor_standing_by_id(
            self.constructor_id
        )

        if standing_info is None:
            self._attr_native_value = F1_STATE_UNAVAILABLE
            self._attr_available = False
        else:
            self._attr_native_value = standing_info.position
            self._attr_available = True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        standing_info = self.coordinator.f1_data.get_constructor_standing_by_id(
            self.constructor_id
        )

        if standing_info is None:
            return F1_CONSTRUCTOR_ATTRIBS_UNAVAILABLE

        ret = {}

        ret["points"] = standing_info.points
        ret["nationality"] = standing_info.constructor.nationality
        ret["constructor_id"] = standing_info.constructor.constructor_id
        ret["season"] = self.coordinator.f1_data.season
        ret["round"] = self.coordinator.f1_data.round
        ret["position"] = standing_info.position

        return ret

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
        standing_info = self.coordinator.f1_data.get_driver_standing_by_position(
            self.position
        )

        if standing_info is None:
            self._attr_native_value = F1_STATE_UNAVAILABLE
            self._attr_available = False
        else:
            self._attr_native_value = self.coordinator.f1_data.get_driver_name(
                standing_info.driver.driver_id
            )
            self._attr_available = True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""

        standing_info = self.coordinator.f1_data.get_driver_standing_by_position(
            self.position
        )

        if standing_info is None:
            return F1_DRIVER_ATTRIBS_UNAVAILABLE

        ret = {}
        ret["points"] = standing_info.points
        ret["nationality"] = standing_info.driver.nationality
        if len(standing_info.constructors) > 1:
            ret["team"] = F1_STATE_MULTIPLE
        else:
            ret["team"] = standing_info.constructors[0].name
        ret["driver_id"] = standing_info.driver.driver_id
        ret["season"] = self.coordinator.f1_data.season
        ret["round"] = self.coordinator.f1_data.round
        ret["position"] = standing_info.position

        return ret

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self.position < 10:
            return f"f1-driver-0{self.position}"

        return f"f1-driver-{self.position}"

    @property
    def name(self) -> str:
        """Return a friendly name."""
        if self.position < 10:
            return f"F1 Driver 0{self.position}"

        return f"F1 Driver {self.position}"


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
        standing_info = self.coordinator.f1_data.get_driver_standing_by_id(
            self.driver_id
        )

        if standing_info is None:
            self._attr_native_value = F1_STATE_UNAVAILABLE
            self._attr_available = False
        else:
            self._attr_native_value = standing_info.position
            self._attr_available = True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        standing_info = self.coordinator.f1_data.get_driver_standing_by_id(
            self.driver_id
        )

        if standing_info is None:
            return F1_DRIVER_ATTRIBS_UNAVAILABLE

        ret = {}
        ret["points"] = standing_info.points
        ret["nationality"] = standing_info.driver.nationality
        if len(standing_info.constructors) > 1:
            ret["team"] = F1_STATE_MULTIPLE
        else:
            ret["team"] = standing_info.constructors[0].name
        ret["driver_id"] = standing_info.driver.driver_id
        ret["season"] = self.coordinator.f1_data.season
        ret["round"] = self.coordinator.f1_data.round
        ret["position"] = standing_info.position

        return ret

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"f1_driver_{self.driver_id}"

    @property
    def name(self) -> str:
        """Return a friendly name."""
        ret = "F1 Driver"
        driver_name = self.coordinator.f1_data.get_driver_name(self.driver_id)
        if driver_name is not None:
            ret += " " + driver_name
        return ret


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
        race_info = self.coordinator.f1_data.get_race_by_round(self.round_no)

        if race_info is None:
            self._attr_native_value = F1_STATE_UNAVAILABLE
            self._attr_available = False
        else:
            self._attr_native_value = race_info.race_name
            self._attr_available = True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        race_info: ergast.Race = self.coordinator.f1_data.get_race_by_round(
            self.round_no
        )

        if race_info is None:
            return F1_RACE_ATTRIBS_UNAVAILABLE

        ret = {}
        ret["season"] = race_info.season
        ret["round"] = self.round_no
        ret["start"] = race_info.date
        ret["fp1_start"] = race_info.first_practice
        ret["fp2_start"] = race_info.second_practice
        if race_info.third_practice is not None:
            ret["fp3_start"] = race_info.third_practice
        ret["quali_start"] = race_info.qualifying
        if race_info.sprint is not None:
            ret["sprint_start"] = race_info.sprint

        return ret

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self.round_no < 10:
            return f"f1-race-0{self.round_no}"

        return f"f1-race-{self.round_no}"

    @property
    def name(self) -> str:
        """Return a friendly name."""
        if self.round_no < 10:
            return f"F1 Race 0{self.round_no}"

        return f"F1 Race {self.round_no}"


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
        race_info = self.coordinator.f1_data.get_next_race()

        if race_info is None:
            self._attr_native_value = F1_STATE_UNAVAILABLE
            self._attr_available = False
        else:
            self._attr_native_value = race_info.race_name
            self._attr_available = True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        race_info = self.coordinator.f1_data.get_next_race()

        if race_info is None:
            return F1_RACE_ATTRIBS_UNAVAILABLE

        ret = {}
        ret["season"] = race_info.season
        ret["round"] = race_info.round_no
        ret["start"] = race_info.date
        ret["fp1_start"] = race_info.first_practice
        ret["fp2_start"] = race_info.second_practice
        if race_info.third_practice is not None:
            ret["fp3_start"] = race_info.third_practice
        ret["quali_start"] = race_info.qualifying
        if race_info.sprint is not None:
            ret["sprint_start"] = race_info.sprint

        return ret

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "f1-next-race"

    @property
    def name(self) -> str:
        """Return a friendly name."""
        return "F1 Next Race"
