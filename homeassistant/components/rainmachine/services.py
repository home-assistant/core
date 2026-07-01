"""Services for Rainmachine."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import TYPE_CHECKING, Any

from regenmaschine.controller import Controller
from regenmaschine.errors import RainMachineError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_CONDITION, CONF_DEVICE_ID, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util.dt import as_timestamp, utcnow

from .const import CONF_DURATION, DATA_PROGRAMS, DATA_ZONES, DOMAIN

if TYPE_CHECKING:
    from . import RainMachineConfigEntry

API_URL_REFERENCE = (
    "https://rainmachine.docs.apiary.io/#reference/weather-services/parserdata/post"
)


CONF_DEWPOINT = "dewpoint"
CONF_ET = "et"
CONF_MAXRH = "maxrh"
CONF_MAXTEMP = "maxtemp"
CONF_MINRH = "minrh"
CONF_MINTEMP = "mintemp"
CONF_PRESSURE = "pressure"
CONF_QPF = "qpf"
CONF_RAIN = "rain"
CONF_SECONDS = "seconds"
CONF_SOLARRAD = "solarrad"
CONF_TEMPERATURE = "temperature"
CONF_TIMESTAMP = "timestamp"
CONF_VALUE = "value"
CONF_WEATHER = "weather"
CONF_WIND = "wind"

CV_FLOW_METER_VALID_UNITS = {
    "clicks",
    "gal",
    "litre",
    "m3",
}

CV_WX_DATA_VALID_PERCENTAGE = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))
CV_WX_DATA_VALID_TEMP_RANGE = vol.All(vol.Coerce(float), vol.Range(min=-40.0, max=40.0))
CV_WX_DATA_VALID_RAIN_RANGE = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1000.0))
CV_WX_DATA_VALID_WIND_SPEED = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=65.0))
CV_WX_DATA_VALID_PRESSURE = vol.All(vol.Coerce(float), vol.Range(min=60.0, max=110.0))
CV_WX_DATA_VALID_SOLARRAD = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=100.0))

SERVICE_NAME_PAUSE_WATERING = "pause_watering"
SERVICE_NAME_PUSH_FLOW_METER_DATA = "push_flow_meter_data"
SERVICE_NAME_PUSH_WEATHER_DATA = "push_weather_data"
SERVICE_NAME_RESTRICT_WATERING = "restrict_watering"
SERVICE_NAME_STOP_ALL = "stop_all"
SERVICE_NAME_UNPAUSE_WATERING = "unpause_watering"
SERVICE_NAME_UNRESTRICT_WATERING = "unrestrict_watering"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
    }
)

SERVICE_PAUSE_WATERING_SCHEMA = SERVICE_SCHEMA.extend(
    {
        vol.Required(CONF_SECONDS): cv.positive_int,
    }
)

SERVICE_PUSH_FLOW_METER_DATA_SCHEMA = SERVICE_SCHEMA.extend(
    {
        vol.Required(CONF_VALUE): cv.positive_float,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): vol.All(
            cv.string, vol.In(CV_FLOW_METER_VALID_UNITS)
        ),
    }
)

SERVICE_PUSH_WEATHER_DATA_SCHEMA = SERVICE_SCHEMA.extend(
    {
        vol.Optional(CONF_TIMESTAMP): cv.positive_float,
        vol.Optional(CONF_MINTEMP): CV_WX_DATA_VALID_TEMP_RANGE,
        vol.Optional(CONF_MAXTEMP): CV_WX_DATA_VALID_TEMP_RANGE,
        vol.Optional(CONF_TEMPERATURE): CV_WX_DATA_VALID_TEMP_RANGE,
        vol.Optional(CONF_WIND): CV_WX_DATA_VALID_WIND_SPEED,
        vol.Optional(CONF_SOLARRAD): CV_WX_DATA_VALID_SOLARRAD,
        vol.Optional(CONF_QPF): CV_WX_DATA_VALID_RAIN_RANGE,
        vol.Optional(CONF_RAIN): CV_WX_DATA_VALID_RAIN_RANGE,
        vol.Optional(CONF_ET): CV_WX_DATA_VALID_RAIN_RANGE,
        vol.Optional(CONF_MINRH): CV_WX_DATA_VALID_PERCENTAGE,
        vol.Optional(CONF_MAXRH): CV_WX_DATA_VALID_PERCENTAGE,
        vol.Optional(CONF_CONDITION): cv.string,
        vol.Optional(CONF_PRESSURE): CV_WX_DATA_VALID_PRESSURE,
        vol.Optional(CONF_DEWPOINT): CV_WX_DATA_VALID_TEMP_RANGE,
    }
)

SERVICE_RESTRICT_WATERING_SCHEMA = SERVICE_SCHEMA.extend(
    {
        vol.Required(CONF_DURATION): cv.time_period,
    }
)


async def async_update_programs_and_zones(
    hass: HomeAssistant, entry: RainMachineConfigEntry
) -> None:
    """Update program and zone DataUpdateCoordinators.

    Program and zone updates always go together because of how linked they are:
    programs affect zones and certain combinations of zones affect programs.
    """
    data = entry.runtime_data
    # No gather here to allow http keep-alive to reuse
    # the connection for each coordinator.
    await data.coordinators[DATA_PROGRAMS].async_refresh()
    await data.coordinators[DATA_ZONES].async_refresh()


@callback
def async_get_entry_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> RainMachineConfigEntry:
    """Get the controller related to a service call (by device ID)."""
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(hass)

    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ValueError(f"Invalid RainMachine device ID: {device_id}")

    entry: RainMachineConfigEntry | None
    for entry_id in device_entry.config_entries:
        if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        if entry.domain == DOMAIN and entry.state is ConfigEntryState.LOADED:
            return entry

    raise ValueError(f"No controller for device ID: {device_id}")


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    def call_with_controller(
        update_programs_and_zones: bool = True,
    ) -> Callable[
        [Callable[[ServiceCall, Controller], Coroutine[Any, Any, None]]],
        Callable[[ServiceCall], Coroutine[Any, Any, None]],
    ]:
        """Hydrate a service call with the appropriate controller."""

        def decorator(
            func: Callable[[ServiceCall, Controller], Coroutine[Any, Any, None]],
        ) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
            """Define the decorator."""

            @wraps(func)
            async def wrapper(call: ServiceCall) -> None:
                """Wrap the service function."""
                entry = async_get_entry_for_service_call(hass, call)
                data = entry.runtime_data

                try:
                    await func(call, data.controller)
                except RainMachineError as err:
                    raise HomeAssistantError(
                        f"Error while executing {func.__name__}: {err}"
                    ) from err

                if update_programs_and_zones:
                    await async_update_programs_and_zones(hass, entry)

            return wrapper

        return decorator

    @call_with_controller()
    async def async_pause_watering(call: ServiceCall, controller: Controller) -> None:
        """Pause watering for a set number of seconds."""
        await controller.watering.pause_all(call.data[CONF_SECONDS])

    @call_with_controller(update_programs_and_zones=False)
    async def async_push_flow_meter_data(
        call: ServiceCall, controller: Controller
    ) -> None:
        """Push flow meter data to the device."""
        value = call.data[CONF_VALUE]
        if units := call.data.get(CONF_UNIT_OF_MEASUREMENT):
            await controller.watering.post_flowmeter(value=value, units=units)
        else:
            await controller.watering.post_flowmeter(value=value)

    @call_with_controller(update_programs_and_zones=False)
    async def async_push_weather_data(
        call: ServiceCall, controller: Controller
    ) -> None:
        """Push weather data to the device."""
        await controller.parsers.post_data(
            {
                CONF_WEATHER: [
                    {
                        key: value
                        for key, value in call.data.items()
                        if key != CONF_DEVICE_ID
                    }
                ]
            }
        )

    @call_with_controller()
    async def async_restrict_watering(
        call: ServiceCall, controller: Controller
    ) -> None:
        """Restrict watering for a time period."""
        duration = call.data[CONF_DURATION]
        await controller.restrictions.set_universal(
            {
                "rainDelayStartTime": round(as_timestamp(utcnow())),
                "rainDelayDuration": duration.total_seconds(),
            },
        )

    @call_with_controller()
    async def async_stop_all(call: ServiceCall, controller: Controller) -> None:
        """Stop all watering."""
        await controller.watering.stop_all()

    @call_with_controller()
    async def async_unpause_watering(call: ServiceCall, controller: Controller) -> None:
        """Unpause watering."""
        await controller.watering.unpause_all()

    @call_with_controller()
    async def async_unrestrict_watering(
        call: ServiceCall, controller: Controller
    ) -> None:
        """Unrestrict watering."""
        await controller.restrictions.set_universal(
            {
                "rainDelayStartTime": round(as_timestamp(utcnow())),
                "rainDelayDuration": 0,
            },
        )

    for service_name, schema, method in (
        (
            SERVICE_NAME_PAUSE_WATERING,
            SERVICE_PAUSE_WATERING_SCHEMA,
            async_pause_watering,
        ),
        (
            SERVICE_NAME_PUSH_FLOW_METER_DATA,
            SERVICE_PUSH_FLOW_METER_DATA_SCHEMA,
            async_push_flow_meter_data,
        ),
        (
            SERVICE_NAME_PUSH_WEATHER_DATA,
            SERVICE_PUSH_WEATHER_DATA_SCHEMA,
            async_push_weather_data,
        ),
        (
            SERVICE_NAME_RESTRICT_WATERING,
            SERVICE_RESTRICT_WATERING_SCHEMA,
            async_restrict_watering,
        ),
        (SERVICE_NAME_STOP_ALL, SERVICE_SCHEMA, async_stop_all),
        (SERVICE_NAME_UNPAUSE_WATERING, SERVICE_SCHEMA, async_unpause_watering),
        (
            SERVICE_NAME_UNRESTRICT_WATERING,
            SERVICE_SCHEMA,
            async_unrestrict_watering,
        ),
    ):
        if hass.services.has_service(DOMAIN, service_name):
            continue
        hass.services.async_register(
            DOMAIN,
            service_name,
            method,
            schema=schema,
            description_placeholders={
                "api_url": API_URL_REFERENCE,
            },
        )
