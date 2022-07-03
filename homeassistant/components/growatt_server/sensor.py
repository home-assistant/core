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
from homeassistant.util import Throttle, dt

from .const import (
    CONF_PLANT_ID,
    DEFAULT_PLANT_ID,
    DEFAULT_URL,
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

SCAN_INTERVAL = datetime.timedelta(minutes=1)


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
    config = config_entry.data
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    url = config.get(CONF_URL, DEFAULT_URL)
    name = config[CONF_NAME]

    api = growattServer.GrowattApi()
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

    entity_description: GrowattSensorEntityDescription

    def __init__(
        self, probe, name, unique_id, description: GrowattSensorEntityDescription
    ):
        """Initialize a PVOutput sensor."""
        self.probe = probe
        self.entity_description = description

        self._attr_name = f"{name} {description.name}"
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
        result = self.probe.get_data(self.entity_description.api_key)
        if self.entity_description.precision is not None:
            result = round(result, self.entity_description.precision)
        return result

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.entity_description.currency:
            return self.probe.get_data("currency")
        return super().native_unit_of_measurement

    def update(self):
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
                # Get the chart data and work out the time of the last entry, use this as the last time data was published to the Growatt Server
                mix_chart_entries = mix_detail["chartData"]
                sorted_keys = sorted(mix_chart_entries)

                # Create datetime from the latest entry
                date_now = dt.now().date()
                last_updated_time = dt.parse_time(str(sorted_keys[-1]))
                mix_detail["lastdataupdate"] = datetime.datetime.combine(
                    date_now, last_updated_time, dt.DEFAULT_TIME_ZONE
                )

                # Dashboard data is largely inaccurate for mix system but it is the only call with the ability to return the combined
                # imported from grid value that is the combination of charging AND load consumption
                dashboard_data = self.api.dashboard_data(self.plant_id)
                # Dashboard values have units e.g. "kWh" as part of their returned string, so we remove it
                dashboard_values_for_mix = {
                    # etouser is already used by the results from 'mix_detail' so we rebrand it as 'etouser_combined'
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
        except json.decoder.JSONDecodeError:
            _LOGGER.error("Unable to fetch data from Growatt server")

    def get_data(self, variable):
        """Get the data."""
        return self.data.get(variable)
