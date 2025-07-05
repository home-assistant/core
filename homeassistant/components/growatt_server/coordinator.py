"""Coordinator module for managing Growatt data fetching."""

import datetime
import json
import logging
from typing import Any

import growattServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEFAULT_URL, DOMAIN

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
        self.config = {**config_entry.data}
        self.username = self.config[CONF_USERNAME]
        self.password = self.config[CONF_PASSWORD]
        self.url = self.config.get(CONF_URL, DEFAULT_URL)
        self.api = growattServer.GrowattApi(
            add_random_user_id=True, agent_identifier=self.username
        )

        # Store the ConfigEntry object
        self.config_entry = config_entry

        # Set server URL
        self.api.server_url = self.url

        self.device_id = device_id
        self.device_type = device_type
        self.plant_id = plant_id

        # Initialize previous_values to store historical data
        self.previous_values: dict[str, Any] = {}

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({device_id})",
            update_interval=SCAN_INTERVAL,
        )

    def _sync_update_data(self) -> dict[str, Any]:
        """Update data via library synchronously."""
        _LOGGER.debug("Updating data for %s (%s)", self.device_id, self.device_type)

        # Login in to the Growatt server
        self.api.login(self.username, self.password)

        if self.device_type == "total":
            total_info = self.api.plant_info(self.device_id)
            del total_info["deviceList"]
            plant_money_text, currency = total_info["plantMoneyText"].split("/")
            total_info["plantMoneyText"] = plant_money_text
            total_info["currency"] = currency
            self.data = total_info
        elif self.device_type == "inverter":
            self.data = self.api.inverter_detail(self.device_id)
        elif self.device_type == "tlx":
            tlx_info = self.api.tlx_detail(self.device_id)
            self.data = tlx_info["data"]
        elif self.device_type == "storage":
            storage_info_detail = self.api.storage_params(self.device_id)
            storage_energy_overview = self.api.storage_energy_overview(
                self.plant_id, self.device_id
            )
            self.data = {
                **storage_info_detail["storageDetailBean"],
                **storage_energy_overview,
            }
        elif self.device_type == "mix":
            mix_info = self.api.mix_info(self.device_id)
            mix_totals = self.api.mix_totals(self.device_id, self.plant_id)
            mix_system_status = self.api.mix_system_status(
                self.device_id, self.plant_id
            )
            mix_detail = self.api.mix_detail(self.device_id, self.plant_id)

            # Get the chart data and work out the time of the last entry
            mix_chart_entries = mix_detail["chartData"]
            sorted_keys = sorted(mix_chart_entries)

            # Create datetime from the latest entry
            date_now = dt_util.now().date()
            last_updated_time = dt_util.parse_time(str(sorted_keys[-1]))
            mix_detail["lastdataupdate"] = datetime.datetime.combine(
                date_now,
                last_updated_time,  # type: ignore[arg-type]
                dt_util.get_default_time_zone(),
            )

            # Dashboard data for mix system
            dashboard_data = self.api.dashboard_data(self.plant_id)
            dashboard_values_for_mix = {
                "etouser_combined": float(dashboard_data["etouser"].replace("kWh", ""))
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
            self.device_type,
        )

        return self.data

    async def _async_update_data(self) -> dict[str, Any]:
        """Asynchronously update data via library."""
        try:
            return await self.hass.async_add_executor_job(self._sync_update_data)
        except json.decoder.JSONDecodeError as err:
            _LOGGER.error("Unable to fetch data from Growatt server: %s", err)
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
