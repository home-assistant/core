"""Coordinator module for managing Growatt data fetching."""

from __future__ import annotations

import datetime
import json
import logging
from typing import TYPE_CHECKING, Any

import growattServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEFAULT_URL, DOMAIN
from .models import GrowattRuntimeData

if TYPE_CHECKING:
    from .sensor.sensor_entity_description import GrowattSensorEntityDescription

type GrowattConfigEntry = ConfigEntry[GrowattRuntimeData]

SCAN_INTERVAL = datetime.timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


class GrowattCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage Growatt data fetching."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GrowattConfigEntry,
        device_id: str,
        device_type: str,
        plant_id: str,
    ) -> None:
        """Initialize the coordinator."""
        self.api_version = (
            "v1" if config_entry.data.get("auth_type") == "api_token" else "classic"
        )
        self.device_id = device_id
        self.device_type = device_type
        self.plant_id = plant_id
        self.previous_values: dict[str, Any] = {}

        if self.api_version == "v1":
            self.username = None
            self.password = None
            self.url = config_entry.data.get(CONF_URL, DEFAULT_URL)
            self.token = config_entry.data["token"]
            self.api = growattServer.OpenApiV1(token=self.token)
        elif self.api_version == "classic":
            self.username = config_entry.data.get(CONF_USERNAME)
            self.password = config_entry.data[CONF_PASSWORD]
            self.url = config_entry.data.get(CONF_URL, DEFAULT_URL)
            self.api = growattServer.GrowattApi(
                add_random_user_id=True, agent_identifier=self.username
            )
            self.api.server_url = self.url
        else:
            raise ValueError(f"Unknown API version: {self.api_version}")

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({device_id})",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

    def _sync_update_data(self) -> dict[str, Any]:
        """Update data via library synchronously."""
        _LOGGER.debug("Updating data for %s (%s)", self.device_id, self.device_type)

        # login only required for classic API
        if self.api_version == "classic":
            self.api.login(self.username, self.password)

        if self.device_type == "total":
            if self.api_version == "v1":
                # The V1 Plant APIs do not provide the same information as the classic plant_info() API
                # More specifically:
                # 1. There is no monetary information to be found, so today and lifetime money is not available
                # 2. There is no nominal power, this is provided by inverter min_energy()
                # This means, for the total coordinator we can only fetch and map the following:
                # todayEnergy -> today_energy
                # totalEnergy -> total_energy
                # invTodayPpv -> current_power
                total_info = self.api.plant_energy_overview(self.plant_id)
                total_info["todayEnergy"] = total_info["today_energy"]
                total_info["totalEnergy"] = total_info["total_energy"]
                total_info["invTodayPpv"] = total_info["current_power"]
            else:
                # Classic API: use plant_info as before
                total_info = self.api.plant_info(self.device_id)
                del total_info["deviceList"]
                plant_money_text, currency = total_info["plantMoneyText"].split("/")
                total_info["plantMoneyText"] = plant_money_text
                total_info["currency"] = currency
            _LOGGER.debug("Total info for plant %s: %r", self.plant_id, total_info)
            self.data = total_info
        elif self.device_type == "inverter":
            self.data = self.api.inverter_detail(self.device_id)
        elif self.device_type == "min":
            # Open API V1: min device
            try:
                min_details = self.api.min_detail(self.device_id)
                min_settings = self.api.min_settings(self.device_id)
                min_energy = self.api.min_energy(self.device_id)
            except growattServer.GrowattV1ApiError as err:
                _LOGGER.error(
                    "Error fetching min device data for %s: %s", self.device_id, err
                )
                raise UpdateFailed(f"Error fetching min device data: {err}") from err

            min_info = {**min_details, **min_settings, **min_energy}
            self.data = min_info
            _LOGGER.debug("min_info for device %s: %r", self.device_id, min_info)
        elif self.device_type == "tlx":
            tlx_info = self.api.tlx_detail(self.device_id)
            self.data = tlx_info["data"]
            _LOGGER.debug("tlx_info for device %s: %r", self.device_id, tlx_info)
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

    def get_data(
        self, entity_description: GrowattSensorEntityDescription
    ) -> str | int | float | None:
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

    async def update_time_segment(
        self, segment_id: int, batt_mode: int, start_time, end_time, enabled: bool
    ) -> None:
        """Update an inverter time segment.

        Args:
            segment_id: Time segment ID (1-9)
            batt_mode: Battery mode (0=load first, 1=battery first, 2=grid first)
            start_time: Start time (datetime.time object)
            end_time: End time (datetime.time object)
            enabled: Whether the segment is enabled
        """
        _LOGGER.debug(
            "Updating time segment %s for device %s",
            segment_id,
            self.device_id,
        )

        if self.api_version != "v1":
            _LOGGER.warning(
                "Updating time segments is only supported with V1 API (token authentication)"
            )
            raise HomeAssistantError(
                "Updating time segments requires token authentication"
            )

        try:
            # Use V1 API for token authentication
            response = await self.hass.async_add_executor_job(
                self.api.min_write_time_segment,
                self.device_id,
                segment_id,
                batt_mode,
                start_time,
                end_time,
                enabled,
            )
        except growattServer.GrowattV1ApiError as err:
            _LOGGER.error(
                "API error updating time segment %s for device %s: %s",
                segment_id,
                self.device_id,
                err,
            )
            raise HomeAssistantError(f"API error updating time segment: {err}") from err

        # Check response error code
        if response.get("error_code", 1) != 0:
            error_msg = response.get("error_msg", "Unknown error")
            _LOGGER.error(
                "Failed to update time segment %s for device %s: %s",
                segment_id,
                self.device_id,
                error_msg,
            )
            raise HomeAssistantError(f"Failed to update time segment: {error_msg}")

        _LOGGER.info(
            "Successfully updated time segment %s for device %s",
            segment_id,
            self.device_id,
        )
        # Trigger a refresh to update the data
        await self.async_refresh()

    async def read_time_segments(self) -> list[dict]:
        """Read time segments from an inverter.

        Returns:
            List of dictionaries containing segment information
        """
        _LOGGER.debug(
            "Reading time segments for device %s",
            self.device_id,
        )

        if self.api_version != "v1":
            _LOGGER.warning(
                "Reading time segments is only supported with V1 API (token authentication)"
            )
            raise HomeAssistantError(
                "Reading time segments requires token authentication"
            )

        # Ensure we have current data
        if not self.data:
            _LOGGER.debug("Triggering refresh to get time segments")
            await self.async_refresh()

        time_segments = []
        mode_names = {0: "Load First", 1: "Battery First", 2: "Grid First"}

        # Extract time segments from coordinator data
        for i in range(1, 10):  # Segments 1-9
            segment = self._parse_time_segment(i, mode_names)
            time_segments.append(segment)

        _LOGGER.debug(
            "Read %d time segments for device %s", len(time_segments), self.device_id
        )
        return time_segments

    def _parse_time_segment(self, segment_id: int, mode_names: dict[int, str]) -> dict:
        """Parse a single time segment from coordinator data."""
        # Get raw time values
        start_time_raw = self.data.get(f"forcedTimeStart{segment_id}", "0:0")
        end_time_raw = self.data.get(f"forcedTimeStop{segment_id}", "0:0")

        # Handle 'null' or empty values
        if start_time_raw in ("null", None, ""):
            start_time_raw = "0:0"
        if end_time_raw in ("null", None, ""):
            end_time_raw = "0:0"

        # Format times with leading zeros (HH:MM)
        start_time = self._format_time(start_time_raw)
        end_time = self._format_time(end_time_raw)

        # Get battery mode
        batt_mode_raw = self.data.get(f"forcedChargeBatMode{segment_id}", 0)
        try:
            batt_mode = int(batt_mode_raw)
        except (ValueError, TypeError):
            batt_mode = 0

        mode_name = mode_names.get(batt_mode, "Unknown")

        # Get enabled status
        enabled_raw = self.data.get(f"forcedChargeFlag{segment_id}", 0)
        try:
            enabled = bool(int(enabled_raw))
        except (ValueError, TypeError):
            enabled = False

        return {
            "segment_id": segment_id,
            "start_time": start_time,
            "end_time": end_time,
            "batt_mode": batt_mode,
            "mode_name": mode_name,
            "enabled": enabled,
        }

    def _format_time(self, time_raw: str) -> str:
        """Format time string to HH:MM format."""
        try:
            parts = str(time_raw).split(":")
            hour = int(parts[0])
            minute = int(parts[1])
        except (ValueError, IndexError):
            return "00:00"
        else:
            return f"{hour:02d}:{minute:02d}"
