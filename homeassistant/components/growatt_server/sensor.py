"""Read status of growatt inverters."""
from __future__ import annotations

import datetime
import json
import logging

import growattServer

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle, dt as dt_util

from .const import (
    CONF_PLANT_ID,
    DEFAULT_PLANT_ID,
    DEFAULT_URL,
    DEPRECATED_URLS,
    DOMAIN,
    LOGIN_INVALID_AUTH_CODE,
)
from .sensor_types.inverter import INVERTER_SENSOR_TYPES
from .sensor_types.mix import MIX_SENSOR_TYPES
from .sensor_types.sensor_entity_description import GrowattSensorEntityDescription
from .sensor_types.storage import STORAGE_SENSOR_TYPES
from .sensor_types.tlx import TLX_SENSOR_TYPES
from .sensor_types.total import TOTAL_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=5)


def get_device_list(api, config):
    """Retrieve the device list for the selected plant."""
    plant_id = config[CONF_PLANT_ID]

    # Log in to api and fetch first plant if no plant id is defined.
    login_response = api.login(config[CONF_USERNAME], config[CONF_PASSWORD])
    if (
        not login_response["success"]
        and login_response["msg"] == LOGIN_INVALID_AUTH_CODE
    ):
        _LOGGER.error("Username, Password or URL may be incorrect!")
        return
    user_id = login_response["user"]["id"]
    if plant_id == DEFAULT_PLANT_ID:
        plant_info = api.plant_list(user_id)
        plant_id = plant_info["data"][0]["plantId"]

    # Get a list of devices for specified plant to add sensors for.
    devices = api.device_list(plant_id)
    return [devices, plant_id]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Growatt sensor."""
    config = {**config_entry.data}
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    url = config.get(CONF_URL, DEFAULT_URL)
    name = config[CONF_NAME]

    # If the URL has been deprecated then change to the default instead
    if url in DEPRECATED_URLS:
        _LOGGER.info(
            "URL: %s has been deprecated, migrating to the latest default: %s",
            url,
            DEFAULT_URL,
        )
        url = DEFAULT_URL
        config[CONF_URL] = url
        hass.config_entries.async_update_entry(config_entry, data=config)

    # Initialise the library with the username & a random id each time it is started
    api = growattServer.GrowattApi(add_random_user_id=True, agent_identifier=username)
    api.server_url = url

    devices, plant_id = await hass.async_add_executor_job(get_device_list, api, config)

    probe = GrowattData(api, username, password, plant_id, "total")
    entities = [
        GrowattInverter(
            probe,
            name=f"{name} Total",
            unique_id=f"{plant_id}-{description.key}",
            description=description,
        )
        for description in TOTAL_SENSOR_TYPES
    ]

    # Add sensors for each device in the specified plant.
    for device in devices:
        probe = GrowattData(
            api, username, password, device["deviceSn"], device["deviceType"]
        )
        sensor_descriptions: tuple[GrowattSensorEntityDescription, ...] = ()
        if device["deviceType"] == "inverter":
            sensor_descriptions = INVERTER_SENSOR_TYPES
        elif device["deviceType"] == "tlx":
            probe.plant_id = plant_id
            sensor_descriptions = TLX_SENSOR_TYPES
        elif device["deviceType"] == "storage":
            probe.plant_id = plant_id
            sensor_descriptions = STORAGE_SENSOR_TYPES
        elif device["deviceType"] == "mix":
            probe.plant_id = plant_id
            sensor_descriptions = MIX_SENSOR_TYPES
        else:
            _LOGGER.debug(
                "Device type %s was found but is not supported right now",
                device["deviceType"],
            )

        entities.extend(
            [
                GrowattInverter(
                    probe,
                    name=f"{device['deviceAilas']}",
                    unique_id=f"{device['deviceSn']}-{description.key}",
                    description=description,
                )
                for description in sensor_descriptions
            ]
        )

    async_add_entities(entities, True)


class GrowattInverter(SensorEntity):
    """Representation of a Growatt Sensor."""

    _attr_has_entity_name = True

    entity_description: GrowattSensorEntityDescription

    def __init__(
        self, probe, name, unique_id, description: GrowattSensorEntityDescription
    ) -> None:
        """Initialize a PVOutput sensor."""
        self.probe = probe
        self.entity_description = description

        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:solar-power"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, probe.device_id)},
            manufacturer="Growatt",
            name=name,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        result = self.probe.get_data(self.entity_description)
        if self.entity_description.precision is not None:
            result = round(result, self.entity_description.precision)
        return result

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.entity_description.currency:
            return self.probe.get_currency()
        return super().native_unit_of_measurement

    def update(self) -> None:
        """Get the latest data from the Growat API and updates the state."""
        self.probe.update()


class GrowattData:
    """The class for handling data retrieval."""

    def __init__(self, api, username, password, device_id, growatt_type):
        """Initialize the probe."""

        self.growatt_type = growatt_type
        self.api = api
        self.device_id = device_id
        self.plant_id = None
        self.data = {}
        self.previous_values = {}
        self.username = username
        self.password = password

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Update probe data."""
        self.api.login(self.username, self.password)
        _LOGGER.debug("Updating data for %s (%s)", self.device_id, self.growatt_type)
        try:
            if self.growatt_type == "total":
                total_info = self.api.plant_info(self.device_id)
                del total_info["deviceList"]
                # PlantMoneyText comes in as "3.1/€" split between value and currency
                plant_money_text, currency = total_info["plantMoneyText"].split("/")
                total_info["plantMoneyText"] = plant_money_text
                total_info["currency"] = currency
                self.data = total_info
            elif self.growatt_type == "inverter":
                inverter_info = self.api.inverter_detail(self.device_id)
                self.data = inverter_info
            elif self.growatt_type == "tlx":
                tlx_info = self.api.tlx_detail(self.device_id)
                self.data = tlx_info["data"]
            elif self.growatt_type == "storage":
                storage_info_detail = self.api.storage_params(self.device_id)[
                    "storageDetailBean"
                ]
                storage_energy_overview = self.api.storage_energy_overview(
                    self.plant_id, self.device_id
                )
                self.data = {**storage_info_detail, **storage_energy_overview}
            elif self.growatt_type == "mix":
                mix_info = self.api.mix_info(self.device_id)
                mix_totals = self.api.mix_totals(self.device_id, self.plant_id)
                mix_system_status = self.api.mix_system_status(
                    self.device_id, self.plant_id
                )

                mix_detail = self.api.mix_detail(self.device_id, self.plant_id)
                # Get the chart data and work out the time of the last entry, use this
                # as the last time data was published to the Growatt Server
                mix_chart_entries = mix_detail["chartData"]
                sorted_keys = sorted(mix_chart_entries)

                # Create datetime from the latest entry
                date_now = dt_util.now().date()
                last_updated_time = dt_util.parse_time(str(sorted_keys[-1]))
                mix_detail["lastdataupdate"] = datetime.datetime.combine(
                    date_now, last_updated_time, dt_util.DEFAULT_TIME_ZONE
                )

                # Dashboard data is largely inaccurate for mix system but it is the only
                # call with the ability to return the combined imported from grid value
                # that is the combination of charging AND load consumption
                dashboard_data = self.api.dashboard_data(self.plant_id)
                # Dashboard values have units e.g. "kWh" as part of their returned
                # string, so we remove it
                dashboard_values_for_mix = {
                    # etouser is already used by the results from 'mix_detail' so we
                    # rebrand it as 'etouser_combined'
                    "etouser_combined": float(
                        dashboard_data["etouser"].replace("kWh", "")
                    )
                }
                self.data = {
                    **mix_info,
                    **mix_totals,
                    **mix_system_status,
                    **mix_detail,
                    **dashboard_values_for_mix,
                }
            _LOGGER.debug(
                "Finished updating data for %s (%s)",
                self.device_id,
                self.growatt_type,
            )
        except json.decoder.JSONDecodeError:
            _LOGGER.error("Unable to fetch data from Growatt server")

    def get_currency(self):
        """Get the currency."""
        return self.data.get("currency")

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
