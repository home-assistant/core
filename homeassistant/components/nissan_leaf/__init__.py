"""Support for the Nissan Leaf Carwings/Nissan Connect API."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
import sys
from typing import Any, cast

from pycarwings2 import CarwingsError, Leaf, Session
from pycarwings2.responses import (
    CarwingsLatestBatteryStatusResponse,
    CarwingsLatestClimateControlStatusResponse,
)
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import utcnow

from .const import (
    CONF_CHARGING_INTERVAL,
    CONF_CLIMATE_INTERVAL,
    CONF_FORCE_MILES,
    CONF_INTERVAL,
    CONF_VALID_REGIONS,
    DATA_BATTERY,
    DATA_CHARGING,
    DATA_CLIMATE,
    DATA_LEAF,
    DATA_PLUGGED_IN,
    DATA_RANGE_AC,
    DATA_RANGE_AC_OFF,
    DEFAULT_CHARGING_INTERVAL,
    DEFAULT_CLIMATE_INTERVAL,
    DEFAULT_INTERVAL,
    DOMAIN,
    INITIAL_UPDATE,
    MAX_RESPONSE_ATTEMPTS,
    MIN_UPDATE_INTERVAL,
    PYCARWINGS2_SLEEP,
    RESTRICTED_BATTERY,
    RESTRICTED_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): cv.string,
                        vol.Required(CONF_PASSWORD): cv.string,
                        vol.Required(CONF_REGION): vol.In(CONF_VALID_REGIONS),
                        vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): (
                            vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL))
                        ),
                        vol.Optional(
                            CONF_CHARGING_INTERVAL, default=DEFAULT_CHARGING_INTERVAL
                        ): (
                            vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL))
                        ),
                        vol.Optional(
                            CONF_CLIMATE_INTERVAL, default=DEFAULT_CLIMATE_INTERVAL
                        ): (
                            vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL))
                        ),
                        vol.Optional(CONF_FORCE_MILES, default=False): cv.boolean,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]

SIGNAL_UPDATE_LEAF = "nissan_leaf_update"

SERVICE_UPDATE_LEAF = "update"
SERVICE_START_CHARGE_LEAF = "start_charge"
ATTR_VIN = "vin"

UPDATE_LEAF_SCHEMA = vol.Schema({vol.Required(ATTR_VIN): cv.string})
START_CHARGE_LEAF_SCHEMA = vol.Schema({vol.Required(ATTR_VIN): cv.string})


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Nissan Leaf integration."""

    async def async_handle_update(service: ServiceCall) -> None:
        """Handle service to update leaf data from Nissan servers."""
        vin = service.data[ATTR_VIN]

        if vin in hass.data[DATA_LEAF]:
            data_store = hass.data[DATA_LEAF][vin]
            await data_store.async_update_data(utcnow())
        else:
            _LOGGER.debug("Vin %s not recognised for update", vin)

    async def async_handle_start_charge(service: ServiceCall) -> None:
        """Handle service to start charging."""
        _LOGGER.warning(
            "The 'nissan_leaf.start_charge' service is deprecated and has been"
            "replaced by a dedicated button entity: Please use that to start"
            "the charge instead"
        )
        vin = service.data[ATTR_VIN]

        if vin in hass.data[DATA_LEAF]:
            data_store = hass.data[DATA_LEAF][vin]

            # Send the command to request charging is started to Nissan
            # servers. If that completes OK then trigger a fresh update to
            # pull the charging status from the car after waiting a minute
            # for the charging request to reach the car.
            result = await hass.async_add_executor_job(data_store.leaf.start_charging)
            if result:
                _LOGGER.debug("Start charging sent, request updated data in 1 minute")
                check_charge_at = utcnow() + timedelta(minutes=1)
                data_store.next_update = check_charge_at
                async_track_point_in_utc_time(
                    hass, data_store.async_update_data, check_charge_at
                )

        else:
            _LOGGER.debug("Vin %s not recognised for update", vin)

    def setup_leaf(car_config: dict[str, Any]) -> None:
        """Set up a car."""
        _LOGGER.debug("Logging into You+Nissan")

        username: str = car_config[CONF_USERNAME]
        password: str = car_config[CONF_PASSWORD]
        region: str = car_config[CONF_REGION]

        try:
            # This might need to be made async (somehow) causes
            # homeassistant to be slow to start
            sess = Session(username, password, region)
            leaf = sess.get_leaf()
        except KeyError:
            _LOGGER.error(
                "Unable to fetch car details..."
                " do you actually have a Leaf connected to your account?"
            )
            return
        except CarwingsError:
            _LOGGER.error(
                "An unknown error occurred while connecting to Nissan: %s",
                sys.exc_info()[0],
            )
            return

        _LOGGER.warning(
            "WARNING: This may poll your Leaf too often, and drain the 12V"
            " battery.  If you drain your cars 12V battery it WILL NOT START"
            " as the drive train battery won't connect."
            " Don't set the intervals too low"
        )

        data_store = LeafDataStore(hass, leaf, car_config)
        hass.data[DATA_LEAF][leaf.vin] = data_store

        for platform in PLATFORMS:
            load_platform(hass, platform, DOMAIN, {}, car_config)

        async_track_point_in_utc_time(
            hass, data_store.async_update_data, utcnow() + INITIAL_UPDATE
        )

    hass.data[DATA_LEAF] = {}
    for car in config[DOMAIN]:
        setup_leaf(car)

    hass.services.register(
        DOMAIN, SERVICE_UPDATE_LEAF, async_handle_update, schema=UPDATE_LEAF_SCHEMA
    )
    hass.services.register(
        DOMAIN,
        SERVICE_START_CHARGE_LEAF,
        async_handle_start_charge,
        schema=START_CHARGE_LEAF_SCHEMA,
    )

    return True


def _extract_start_date(
    battery_info: CarwingsLatestBatteryStatusResponse,
) -> datetime | None:
    """Extract the server date from the battery response."""
    try:
        return cast(
            datetime,
            battery_info.answer["BatteryStatusRecords"]["OperationDateAndTime"],
        )
    except KeyError:
        return None


class LeafDataStore:
    """Nissan Leaf Data Store."""

    def __init__(
        self, hass: HomeAssistant, leaf: Leaf, car_config: dict[str, Any]
    ) -> None:
        """Initialise the data store."""
        self.hass = hass
        self.leaf = leaf
        self.car_config = car_config
        self.force_miles = car_config[CONF_FORCE_MILES]
        self.data: dict[str, Any] = {}
        self.data[DATA_CLIMATE] = None
        self.data[DATA_BATTERY] = None
        self.data[DATA_CHARGING] = None
        self.data[DATA_RANGE_AC] = None
        self.data[DATA_RANGE_AC_OFF] = None
        self.data[DATA_PLUGGED_IN] = None
        self.next_update: datetime | None = None
        self.last_check: datetime | None = None
        self.request_in_progress: bool = False
        # Timestamp of last successful response from battery or climate.
        self.last_battery_response: datetime | None = None
        self.last_climate_response: datetime | None = None
        self._remove_listener: CALLBACK_TYPE | None = None

    async def async_update_data(self, now: datetime) -> None:
        """Update data from nissan leaf."""
        # Prevent against a previously scheduled update and an ad-hoc update
        # started from an update from both being triggered.
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

        # Clear next update whilst this update is underway
        self.next_update = None

        await self.async_refresh_data(now)
        self.next_update = self.get_next_interval()
        _LOGGER.debug("Next update=%s", self.next_update)

        if self.next_update is not None:
            self._remove_listener = async_track_point_in_utc_time(
                self.hass, self.async_update_data, self.next_update
            )

    def get_next_interval(self) -> datetime:
        """Calculate when the next update should occur."""
        base_interval = self.car_config[CONF_INTERVAL]
        climate_interval = self.car_config[CONF_CLIMATE_INTERVAL]
        charging_interval = self.car_config[CONF_CHARGING_INTERVAL]

        # The 12V battery is used when communicating with Nissan servers.
        # The 12V battery is charged from the traction battery when not
        # connected and when the traction battery has enough charge. To
        # avoid draining the 12V battery we shall restrict the update
        # frequency if low battery detected.
        if (
            self.last_battery_response is not None
            and self.data[DATA_CHARGING] is False
            and self.data[DATA_BATTERY] <= RESTRICTED_BATTERY
        ):
            _LOGGER.debug(
                "Low battery so restricting refresh frequency (%s)", self.leaf.nickname
            )
            interval = RESTRICTED_INTERVAL
        else:
            intervals = [base_interval]

            if self.data[DATA_CHARGING]:
                intervals.append(charging_interval)

            if self.data[DATA_CLIMATE]:
                intervals.append(climate_interval)

            interval = min(intervals)

        return utcnow() + interval

    async def async_refresh_data(self, now: datetime) -> None:
        """Refresh the leaf data and update the datastore."""
        if self.request_in_progress:
            _LOGGER.debug("Refresh currently in progress for %s", self.leaf.nickname)
            return

        _LOGGER.debug("Updating Nissan Leaf Data")

        self.last_check = datetime.today()
        self.request_in_progress = True

        server_response = await self.async_get_battery()

        if server_response is not None:
            _LOGGER.debug("Server Response: %s", server_response.__dict__)

            if server_response.answer["status"] == HTTPStatus.OK:
                self.data[DATA_BATTERY] = server_response.battery_percent

                # pycarwings2 library doesn't always provide cruising rnages
                # so we have to check if they exist before we can use them.
                # Root cause: the nissan servers don't always send the data.
                if hasattr(server_response, "cruising_range_ac_on_km"):
                    self.data[DATA_RANGE_AC] = server_response.cruising_range_ac_on_km
                else:
                    self.data[DATA_RANGE_AC] = None

                if hasattr(server_response, "cruising_range_ac_off_km"):
                    self.data[DATA_RANGE_AC_OFF] = (
                        server_response.cruising_range_ac_off_km
                    )
                else:
                    self.data[DATA_RANGE_AC_OFF] = None

                self.data[DATA_PLUGGED_IN] = server_response.is_connected
                self.data[DATA_CHARGING] = server_response.is_charging
                async_dispatcher_send(self.hass, SIGNAL_UPDATE_LEAF)
                self.last_battery_response = utcnow()

        # Climate response only updated if battery data updated first.
        if server_response is not None:
            try:
                climate_response = await self.async_get_climate()
                if climate_response is not None:
                    _LOGGER.debug(
                        "Got climate data for Leaf: %s", climate_response.__dict__
                    )
                    self.data[DATA_CLIMATE] = climate_response.is_hvac_running
                    self.last_climate_response = utcnow()
            except CarwingsError:
                _LOGGER.error("Error fetching climate info")

        self.request_in_progress = False
        async_dispatcher_send(self.hass, SIGNAL_UPDATE_LEAF)

    async def async_get_battery(
        self,
    ) -> CarwingsLatestBatteryStatusResponse:
        """Request battery update from Nissan servers."""
        try:
            # Request battery update from the car
            _LOGGER.debug("Requesting battery update, %s", self.leaf.vin)
            start_date: datetime | None = None
            try:
                start_server_info = await self.hass.async_add_executor_job(
                    self.leaf.get_latest_battery_status
                )
            except TypeError:  # pycarwings2 can fail if Nissan returns nothing
                _LOGGER.debug("Battery status check returned nothing")
            else:
                if not start_server_info:
                    _LOGGER.debug("Battery status check failed")
                else:
                    start_date = _extract_start_date(start_server_info)
            await asyncio.sleep(1)  # Critical sleep
            request = await self.hass.async_add_executor_job(self.leaf.request_update)
            if not request:
                _LOGGER.error("Battery update request failed")
                return None

            for attempt in range(MAX_RESPONSE_ATTEMPTS):
                _LOGGER.debug(
                    "Waiting %s seconds for battery update (%s) (%s)",
                    PYCARWINGS2_SLEEP,
                    self.leaf.vin,
                    attempt,
                )
                await asyncio.sleep(PYCARWINGS2_SLEEP)

                # We don't use the response from get_status_from_update
                # apart from knowing that the car has responded saying it
                # has given the latest battery status to Nissan.
                check_result_info = await self.hass.async_add_executor_job(
                    self.leaf.get_status_from_update, request
                )

                if check_result_info is not None:
                    # Get the latest battery status from Nissan servers.
                    # This has the SOC in it.
                    server_info = await self.hass.async_add_executor_job(
                        self.leaf.get_latest_battery_status
                    )
                    if not start_date or (
                        server_info and start_date != _extract_start_date(server_info)
                    ):
                        return server_info
                    # get_status_from_update returned {"resultFlag": "1"}
                    # but the data didn't change, make a fresh request.
                    await asyncio.sleep(1)  # Critical sleep
                    request = await self.hass.async_add_executor_job(
                        self.leaf.request_update
                    )
                    if not request:
                        _LOGGER.error("Battery update request failed")
                        return None

            _LOGGER.debug(
                "%s attempts exceeded return latest data from server",
                MAX_RESPONSE_ATTEMPTS,
            )
            # Get the latest data from the nissan servers, even though
            # it may be out of date, it's better than nothing.
            server_info = await self.hass.async_add_executor_job(
                self.leaf.get_latest_battery_status
            )
        except CarwingsError:
            _LOGGER.error("An error occurred getting battery status")
            return None
        except (KeyError, TypeError):
            _LOGGER.error("An error occurred parsing response from server")
            return None
        return server_info

    async def async_get_climate(
        self,
    ) -> CarwingsLatestClimateControlStatusResponse:
        """Request climate data from Nissan servers."""
        try:
            return await self.hass.async_add_executor_job(
                self.leaf.get_latest_hvac_status
            )
        except CarwingsError:
            _LOGGER.error(
                "An error occurred communicating with the car %s", self.leaf.vin
            )
            return None

    async def async_set_climate(self, toggle: bool) -> bool:
        """Set climate control mode via Nissan servers."""
        climate_result = None
        if toggle:
            _LOGGER.debug("Requesting climate turn on for %s", self.leaf.vin)
            set_function = self.leaf.start_climate_control
            result_function = self.leaf.get_start_climate_control_result
        else:
            _LOGGER.debug("Requesting climate turn off for %s", self.leaf.vin)
            set_function = self.leaf.stop_climate_control
            result_function = self.leaf.get_stop_climate_control_result

        request = await self.hass.async_add_executor_job(set_function)
        for attempt in range(MAX_RESPONSE_ATTEMPTS):
            if attempt > 0:
                _LOGGER.debug(
                    "Climate data not in yet (%s) (%s). Waiting (%s) seconds",
                    self.leaf.vin,
                    attempt,
                    PYCARWINGS2_SLEEP,
                )
                await asyncio.sleep(PYCARWINGS2_SLEEP)

            climate_result = await self.hass.async_add_executor_job(
                result_function, request
            )

            if climate_result is not None:
                break

        if climate_result is not None:
            _LOGGER.debug("Climate result: %s", climate_result.__dict__)
            async_dispatcher_send(self.hass, SIGNAL_UPDATE_LEAF)
            return bool(climate_result.is_hvac_running) == toggle

        _LOGGER.debug("Climate result not returned by Nissan servers")
        return False

    async def async_start_charging(self) -> None:
        """Request to start charging the car. Used by the button platform."""
        await self.hass.async_add_executor_job(self.leaf.start_charging)
        self.schedule_update()

    def schedule_update(self) -> None:
        """Set the next update to be triggered in a minute."""

        # Remove any future updates that may be scheduled
        if self._remove_listener:
            self._remove_listener()
        # Schedule update for one minute in the future - so that previously sent
        # requests can be processed by Nissan servers or the car.
        update_at = utcnow() + timedelta(minutes=1)
        self.next_update = update_at
        self._remove_listener = async_track_point_in_utc_time(
            self.hass, self.async_update_data, update_at
        )


class LeafEntity(Entity):
    """Base class for Nissan Leaf entity."""

    def __init__(self, car: LeafDataStore) -> None:
        """Store LeafDataStore upon init."""
        self.car = car

    def log_registration(self) -> None:
        """Log registration."""
        _LOGGER.debug(
            "Registered %s integration for VIN %s",
            self.__class__.__name__,
            self.car.leaf.vin,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return default attributes for Nissan leaf entities."""
        return {
            "next_update": self.car.next_update,
            "last_attempt": self.car.last_check,
            "updated_on": self.car.last_battery_response,
            "update_in_progress": self.car.request_in_progress,
            "vin": self.car.leaf.vin,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.log_registration()
        self.async_on_remove(
            async_dispatcher_connect(
                self.car.hass, SIGNAL_UPDATE_LEAF, self._update_callback
            )
        )

    @callback
    def _update_callback(self) -> None:
        """Update the state."""
        self.async_schedule_update_ha_state(True)
