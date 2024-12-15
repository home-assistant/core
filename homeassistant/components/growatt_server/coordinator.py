"""Coordinator module for managing Growatt data fetching."""

import datetime
import logging
from typing import Any

import growattServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEFAULT_URL, DEPRECATED_URLS, DOMAIN

SCAN_INTERVAL = datetime.timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


class GrowattCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Growatt data fetching."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device_id: str,
        device_type: str,
        plant_id: str,
    ) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry
        self.config = {**config_entry.data}
        self.username = self.config[CONF_USERNAME]
        self.password = self.config[CONF_PASSWORD]
        self.url = self.config.get(CONF_URL, DEFAULT_URL)
        self.api = growattServer.GrowattApi(
            add_random_user_id=True, agent_identifier=self.username
        )
        self.device_id = device_id
        self.device_type = device_type
        self.plant_id = plant_id
        self.data = {}
        self.previous_values: dict[str, Any] = {}

        # Handle URL deprecation
        if self.url in DEPRECATED_URLS:
            _LOGGER.warning(
                "URL: %s has been deprecated, migrating to the latest default: %s",
                self.url,
                DEFAULT_URL,
            )
            self.url = DEFAULT_URL
            self.config[CONF_URL] = self.url
            hass.config_entries.async_update_entry(config_entry, data=self.config)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            update_method=self._async_update_data,
            update_interval=SCAN_INTERVAL,
        )

    async def _make_api_call(self, api_method, *args):
        """In order to handle the case where the API token expires, we will try to re-login and retry the API call."""
        try:
            return await self.hass.async_add_executor_job(api_method, *args)
        except ValueError as err:
            _LOGGER.debug("make_api_call failed, trying to re-login: %s", err)
            login_response = await self.hass.async_add_executor_job(
                self.api.login, self.username, self.password
            )
            if not login_response["success"]:
                _LOGGER.error(
                    "Failed to log in, msg: %s, error: %s",
                    login_response["msg"],
                    login_response["error"],
                )
                return None
            _LOGGER.debug("make_api_call: login success")
            return await self.hass.async_add_executor_job(api_method, *args)

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""
        try:
            _LOGGER.debug("Updating data for %s (%s)", self.device_id, self.device_type)

            if self.device_type == "total":
                total_info = await self._make_api_call(
                    self.api.plant_info, self.device_id
                )
                del total_info["deviceList"]
                plant_money_text, currency = total_info["plantMoneyText"].split("/")
                total_info["plantMoneyText"] = plant_money_text
                total_info["currency"] = currency
                self.data = total_info
            elif self.device_type == "inverter":
                inverter_info = await self._make_api_call(
                    self.api.inverter_detail, self.device_id
                )
                self.data = inverter_info
            elif self.device_type == "tlx":
                tlx_system_status = await self._make_api_call(
                    self.api.tlx_system_status, self.plant_id, self.device_id
                )
                # the following values are returned in kW, but we want them in W
                tlx_system_status["chargePower"] = (
                    float(tlx_system_status["chargePower"]) * 1000
                )
                tlx_system_status["pdisCharge"] = (
                    float(tlx_system_status["pdisCharge"]) * 1000
                )
                tlx_energy_overview = await self._make_api_call(
                    self.api.tlx_energy_overview, self.plant_id, self.device_id
                )
                tlx_details = await self._make_api_call(
                    self.api.tlx_detail, self.device_id
                )
                all_settings = await self._make_api_call(
                    self.api.tlx_all_settings, self.device_id
                )
                enabled_settings = await self._make_api_call(
                    self.api.tlx_enabled_settings, self.device_id
                )
                # Present in web UI, but not returned in enabled_settings for some reason
                # The shinePhone UI only shows one value and probably updates bot discharge_stop_soc and on_grid_discharge_stop_soc
                enabled_settings["enable"]["on_grid_discharge_stop_soc"] = "1"
                enabled_keys = enabled_settings["enable"].keys()
                tlx_settings = {
                    k: v for k, v in all_settings.items() if k in enabled_keys
                }
                self.data = {
                    **tlx_system_status,
                    **tlx_energy_overview,
                    **tlx_details["data"],
                    **tlx_settings,
                }
                # chargePower, pdisCharge
            elif self.device_type == "storage":
                storage_info_detail = await self._make_api_call(
                    self.api.storage_params, self.device_id
                )
                storage_energy_overview = await self._make_api_call(
                    self.api.storage_energy_overview, self.plant_id, self.device_id
                )
                self.data = {
                    **storage_info_detail["storageDetailBean"],
                    **storage_energy_overview,
                }
            elif self.device_type == "mix":
                mix_info = await self._make_api_call(self.api.mix_info, self.device_id)
                mix_totals = await self._make_api_call(
                    self.api.mix_totals, self.device_id, self.plant_id
                )
                mix_system_status = await self._make_api_call(
                    self.api.mix_system_status, self.device_id, self.plant_id
                )
                mix_detail = await self._make_api_call(
                    self.api.mix_detail, self.device_id, self.plant_id
                )

                # Get the chart data and work out the time of the last entry, use this
                # as the last time data was published to the Growatt Server
                mix_chart_entries = mix_detail["chartData"]
                sorted_keys = sorted(mix_chart_entries)

                # Create datetime from the latest entry
                date_now = dt_util.now().date()
                last_updated_time = dt_util.parse_time(str(sorted_keys[-1]))
                if last_updated_time is not None:
                    mix_detail["lastdataupdate"] = datetime.datetime.combine(
                        date_now, last_updated_time, dt_util.DEFAULT_TIME_ZONE
                    )

                # We calculate this value dynamically based on the returned chart data.
                # There is no value available on the API that provides the combined
                # value of: charging + load consumption
                # For each time entry convert it's wattage into kWh, this assumes that
                # the wattage value is the same for the whole X minute window (it's the
                # only assumption we can make)
                # We Multiply the wattage by <TIME PERIOD>/<HOUR>
                # (the number of minutes of the time window divided by the number of minutes in an hour)
                # to give us the equivalent kWh reading for that X minute window
                pac_to_user_today = 0.0
                hour_secs = datetime.timedelta(hours=1).total_seconds()
                previous_time_val = datetime.time(0, 0, 0)  # Start at midnight
                for key in sorted_keys:
                    time_val = datetime.datetime.strptime(key, "%H:%M").time()
                    # Calculate the difference between this and the previous timestamp
                    # to determine how long this rate has been used for
                    timediff_secs = (
                        datetime.datetime.combine(datetime.date.min, time_val)
                        - datetime.datetime.combine(
                            datetime.date.min, previous_time_val
                        )
                    ).total_seconds()
                    multiplier = timediff_secs / hour_secs
                    data_points = mix_chart_entries[key]
                    pac_to_user_today += float(data_points["pacToUser"]) * multiplier
                    previous_time_val = time_val

                mix_detail["etouser_combined"] = round(pac_to_user_today, 2)

                self.data = {
                    **mix_info,
                    **mix_totals,
                    **mix_system_status,
                    **mix_detail,
                }
            _LOGGER.debug(
                "Finished updating data for %s (%s)",
                self.device_id,
                self.device_type,
            )
            return self.data  # noqa: TRY300
        except Exception as err:
            _LOGGER.error("Error fetching data: %s", err)
            raise UpdateFailed(f"Error fetching data: {err}") from err

    def get_currency(self):
        """Get the currency."""
        return self.data.get("currency")

    def get_data(self, entity_description):
        """Get the data."""

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

        _LOGGER.debug(
            "Data request for: %s: res=%s", entity_description.key, str(return_value)
        )

        return return_value

    def get_value(self, entity_description):
        """Get the raw parameter value."""
        return_value = self.data.get(entity_description.api_key)
        _LOGGER.debug(
            "Get parameter value for: %s, res=%s",
            entity_description.key,
            str(return_value),
        )
        return return_value

    def set_value(self, entity_description, value):
        """Set value of the parameter."""
        _LOGGER.debug(
            "Set parameter value %s for: %s",
            value,
            entity_description.key,
        )
        self.data[entity_description.api_key] = value

    async def update_tlx_inverter_time_segment(
        self, segment_id, batt_mode, start_time, end_time, enabled
    ):
        """Update a TLX inverter time segment."""
        response = await self.hass.async_add_executor_job(
            self.api.update_tlx_inverter_time_segment,
            self.device_id,
            segment_id,
            batt_mode,
            start_time,
            end_time,
            enabled,
        )
        if response.get("success"):
            _LOGGER.info(
                "Successfully updated TLX inverter time segment %s for serial number %s",
                segment_id,
                self.device_id,
            )
        else:
            _LOGGER.error(
                "Failed to update TLX inverter time segment %s for serial number %s: %s",
                segment_id,
                self.device_id,
                response.get("msg"),
            )
