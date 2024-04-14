"""The Sun WEG inverter sensor integration."""

import datetime
import json
import logging

from sunweg.api import APIHelper
from sunweg.plant import Plant

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.typing import StateType, UndefinedType
from homeassistant.util import Throttle

from .const import CONF_PLANT_ID, DOMAIN, PLATFORMS, DeviceType

SCAN_INTERVAL = datetime.timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Load the saved entities."""
    api = APIHelper(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    if not await hass.async_add_executor_job(api.authenticate):
        raise ConfigEntryAuthFailed("Username or Password may be incorrect!")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = SunWEGData(
        api, entry.data[CONF_PLANT_ID]
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    if len(hass.data[DOMAIN]) == 0:
        hass.data.pop(DOMAIN)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class SunWEGData:
    """The class for handling data retrieval."""

    def __init__(
        self,
        api: APIHelper,
        plant_id: int,
    ) -> None:
        """Initialize the probe."""

        self.api = api
        self.plant_id = plant_id
        self.data: Plant = None
        self.previous_values: dict = {}

    @Throttle(SCAN_INTERVAL)
    def update(self) -> None:
        """Update probe data."""
        _LOGGER.debug("Updating data for plant %s", self.plant_id)
        try:
            self.data = self.api.plant(self.plant_id)
            for inverter in self.data.inverters:
                self.api.complete_inverter(inverter)
        except json.decoder.JSONDecodeError:
            _LOGGER.error("Unable to fetch data from SunWEG server")
        _LOGGER.debug("Finished updating data for plant %s", self.plant_id)

    def get_api_value(
        self,
        variable: str,
        device_type: DeviceType,
        inverter_id: int = 0,
        deep_name: str | None = None,
    ):
        """Retrieve from a Plant the desired variable value."""
        if device_type == DeviceType.TOTAL:
            return self.data.__dict__.get(variable)

        inverter_list = [i for i in self.data.inverters if i.id == inverter_id]
        if len(inverter_list) == 0:
            return None
        inverter = inverter_list[0]

        if device_type == DeviceType.INVERTER:
            return inverter.__dict__.get(variable)
        if device_type == DeviceType.PHASE:
            for phase in inverter.phases:
                if phase.name == deep_name:
                    return phase.__dict__.get(variable)
        elif device_type == DeviceType.STRING:
            for mppt in inverter.mppts:
                for string in mppt.strings:
                    if string.name == deep_name:
                        return string.__dict__.get(variable)
        return None

    def get_data(
        self,
        *,
        api_variable_key: str,
        api_variable_unit: str | None,
        deep_name: str | None,
        device_type: DeviceType,
        inverter_id: int,
        name: str | UndefinedType | None,
        native_unit_of_measurement: str | None,
        never_resets: bool,
        previous_value_drop_threshold: float | None,
    ) -> tuple[StateType | datetime.datetime, str | None]:
        """Get the data."""
        _LOGGER.debug(
            "Data request for: %s",
            name,
        )
        variable = api_variable_key
        previous_unit = native_unit_of_measurement
        api_value = self.get_api_value(variable, device_type, inverter_id, deep_name)
        previous_value = self.previous_values.get(variable)
        return_value = api_value
        if api_variable_unit is not None:
            native_unit_of_measurement = self.get_api_value(
                api_variable_unit,
                device_type,
                inverter_id,
                deep_name,
            )

        # If we have a 'drop threshold' specified, then check it and correct if needed
        if (
            previous_value_drop_threshold is not None
            and previous_value is not None
            and api_value is not None
            and previous_unit == native_unit_of_measurement
        ):
            _LOGGER.debug(
                (
                    "%s - Drop threshold specified (%s), checking for drop... API"
                    " Value: %s, Previous Value: %s"
                ),
                name,
                previous_value_drop_threshold,
                api_value,
                previous_value,
            )
            diff = float(api_value) - float(previous_value)

            # Check if the value has dropped (negative value i.e. < 0) and it has only
            # dropped by a small amount, if so, use the previous value.
            # Note - The energy dashboard takes care of drops within 10%
            # of the current value, however if the value is low e.g. 0.2
            # and drops by 0.1 it classes as a reset.
            if -(previous_value_drop_threshold) <= diff < 0:
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
                _LOGGER.debug("%s - No drop detected, using API value", name)

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
        if never_resets and api_value == 0 and previous_value:
            _LOGGER.debug(
                (
                    "API value is 0, but this value should never reset, returning"
                    " previous value (%s) instead"
                ),
                previous_value,
            )
            return_value = previous_value

        self.previous_values[variable] = return_value

        return (return_value, native_unit_of_measurement)
