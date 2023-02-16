"""Read status of SunWEG inverters."""
from __future__ import annotations

import datetime
from decimal import Decimal
import json
import logging

from sunweg.api import APIHelper

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import Throttle

from .const import CONF_PLANT_ID, DEFAULT_PLANT_ID, DOMAIN
from .sensor_types.inverter import INVERTER_SENSOR_TYPES
from .sensor_types.phase import PHASE_SENSOR_TYPES
from .sensor_types.sensor_entity_description import SunWEGSensorEntityDescription
from .sensor_types.string import STRING_SENSOR_TYPES
from .sensor_types.total import TOTAL_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=5)
CACHE_INTERVAL = datetime.timedelta(minutes=1)


def get_device_list(api: APIHelper, config):
    """Retrieve the device list for the selected plant."""
    plant_id = config[CONF_PLANT_ID]

    # Log in to api and fetch first plant if no plant id is defined.
    login_response = api.authenticate()
    if not login_response:
        _LOGGER.error("Username, Password or URL may be incorrect!")
        return
    if plant_id == DEFAULT_PLANT_ID:
        plant_info = api.listPlants()
        plant_id = plant_info[0]

    # Get a list of devices for specified plant to add sensors for.
    devices = api.plant(plant_id).inverters
    return [devices, plant_id]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SunWEG sensor."""
    config = {**config_entry.data}
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    name = config[CONF_NAME]

    # Initialise the library with the username & a random id each time it is started
    api = APIHelper(username, password)

    devices, plant_id = await hass.async_add_executor_job(get_device_list, api, config)

    probe = SunWEGData(api, username, password, plant_id, "total")
    entities = [
        SunWEGInverter(
            probe,
            name=f"{name} Total",
            unique_id=f"{plant_id}-{description.key}",
            description=description,
        )
        for description in TOTAL_SENSOR_TYPES
    ]

    # Add sensors for each device in the specified plant.
    for device in devices:
        probe = SunWEGData(api, username, password, device.id, "inverter")

        entities.extend(
            [
                SunWEGInverter(
                    probe,
                    name=f"{device.name}",
                    unique_id=f"{device.sn}-{description.key}",
                    description=description,
                )
                for description in INVERTER_SENSOR_TYPES
            ]
        )

        for phase in device.phases:
            phase_probe = SunWEGData(
                api, username, password, device.id, "phase", phase.name
            )
            entities.extend(
                [
                    SunWEGInverter(
                        phase_probe,
                        name=f"{device.name} {phase.name}",
                        unique_id=f"{device.sn}-{phase.name}-{description.key}",
                        description=description,
                    )
                    for description in PHASE_SENSOR_TYPES
                ]
            )

        for mppt in device.mppts:
            for string in mppt.strings:
                string_probe = SunWEGData(
                    api, username, password, device.id, "string", string.name
                )
                entities.extend(
                    [
                        SunWEGInverter(
                            string_probe,
                            name=f"{device.name} {string.name}",
                            unique_id=f"{device.sn}-{string.name}-{description.key}",
                            description=description,
                        )
                        for description in STRING_SENSOR_TYPES
                    ]
                )

    async_add_entities(entities, True)


class SunWEGInverter(SensorEntity):
    """Representation of a SunWEG Sensor."""

    entity_description: SunWEGSensorEntityDescription

    def __init__(
        self, probe, name, unique_id, description: SunWEGSensorEntityDescription
    ) -> None:
        """Initialize a PVOutput sensor."""
        self.probe = probe
        self.entity_description = description

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = unique_id
        self._attr_icon = (
            description.icon if description.icon is not None else "mdi:solar-power"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, probe.device_id)},
            manufacturer="SunWEG",
            name=name,
        )

    @property
    def native_value(
        self,
    ) -> (
        StateType
        | str
        | int
        | float
        | None
        | datetime.date
        | datetime.datetime
        | Decimal
    ):
        """Return the state of the sensor."""
        result = self.probe.get_data(self.entity_description)
        if self.entity_description.precision is not None:
            result = round(result, self.entity_description.precision)
        return result

    def update(self) -> None:
        """Get the latest data from the Sun WEG API and updates the state."""
        self.probe.update()


class SunWEGData:
    """The class for handling data retrieval."""

    cache: dict = {}

    def __init__(
        self,
        api: APIHelper,
        username,
        password,
        device_id,
        sunweg_type,
        deep_name: str | None = None,
    ) -> None:
        """Initialize the probe."""

        self.sunweg_type = sunweg_type
        self.api = api
        self.device_id = device_id
        self.data: dict = {}
        self.previous_values: dict = {}
        self.username = username
        self.password = password
        self.deep_name = deep_name

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Update probe data."""
        _LOGGER.debug("Updating data for %s (%s)", self.device_id, self.sunweg_type)
        try:
            if self.sunweg_type == "total":
                total_info = self.api.plant(self.device_id).__dict__
                self.data = total_info
            elif self.sunweg_type == "inverter":
                inverter_info = self.get_inverter_info()
                self.data = inverter_info
            elif self.sunweg_type == "phase":
                inverter_info = self.get_inverter_info()
                for phase in inverter_info["phases"]:
                    if phase.name == self.deep_name:
                        self.data = phase.__dict__
            elif self.sunweg_type == "string":
                inverter_info = self.get_inverter_info()
                for mttp in inverter_info["mppts"]:
                    for string in mttp.strings:
                        if string.name == self.deep_name:
                            self.data = string.__dict__

            _LOGGER.debug(
                "Finished updating data for %s (%s)",
                self.device_id,
                self.sunweg_type,
            )
        except json.decoder.JSONDecodeError:
            _LOGGER.error("Unable to fetch data from SunWEG server")

    def get_inverter_info(self):
        """Get inverter info from cache."""
        data = self.cache.get(self.device_id, None)
        if (
            data is None
            or datetime.datetime.utcnow() - data.get("time") > CACHE_INTERVAL
        ):
            data = {
                "info": self.api.inverter(self.device_id).__dict__,
                "time": datetime.datetime.utcnow(),
            }
            self.cache[self.device_id] = data
        return data.get("info")

    def get_data(self, entity_description):
        """Get the data."""
        _LOGGER.debug(
            "Data request for: %s",
            entity_description.name,
        )
        variable = entity_description.api_key
        api_value = self.data.get(variable)
        previous_value = self.previous_values.get(variable)
        return_value = api_value

        # If we have a 'drop threshold' specified, then check it and correct if needed
        if (
            entity_description.previous_value_drop_threshold is not None
            and previous_value is not None
            and api_value is not None
        ):
            _LOGGER.debug(
                (
                    "%s - Drop threshold specified (%s), checking for drop... API"
                    " Value: %s, Previous Value: %s"
                ),
                entity_description.name,
                entity_description.previous_value_drop_threshold,
                api_value,
                previous_value,
            )
            diff = float(api_value) - float(previous_value)

            # Check if the value has dropped (negative value i.e. < 0) and it has only
            # dropped by a small amount, if so, use the previous value.
            # Note - The energy dashboard takes care of drops within 10%
            # of the current value, however if the value is low e.g. 0.2
            # and drops by 0.1 it classes as a reset.
            if -(entity_description.previous_value_drop_threshold) <= diff < 0:
                _LOGGER.debug(
                    (
                        "Diff is negative, but only by a small amount therefore not a"
                        " nightly reset, using previous value (%s) instead of api value"
                        " (%s)"
                    ),
                    previous_value,
                    api_value,
                )
                return_value = previous_value
            else:
                _LOGGER.debug(
                    "%s - No drop detected, using API value", entity_description.name
                )

        # Lifetime total values should always be increasing, they will never reset,
        # however the API sometimes returns 0 values when the clock turns to 00:00
        # local time in that scenario we should just return the previous value
        # Scenarios:
        # 1 - System has a genuine 0 value when it it first commissioned:
        #        - will return 0 until a non-zero value is registered
        # 2 - System has been running fine but temporarily resets to 0 briefly
        #     at midnight:
        #        - will return the previous value
        # 3 - HA is restarted during the midnight 'outage' - Not handled:
        #        - Previous value will not exist meaning 0 will be returned
        #        - This is an edge case that would be better handled by looking
        #          up the previous value of the entity from the recorder
        if entity_description.never_resets and api_value == 0 and previous_value:
            _LOGGER.debug(
                (
                    "API value is 0, but this value should never reset, returning"
                    " previous value (%s) instead"
                ),
                previous_value,
            )
            return_value = previous_value

        self.previous_values[variable] = return_value

        return return_value
