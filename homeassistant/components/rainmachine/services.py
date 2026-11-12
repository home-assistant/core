"""Services for RainMachine."""

from collections.abc import Callable, Coroutine
from enum import StrEnum
from functools import wraps
from typing import TYPE_CHECKING, Any

import probatio
from regenmaschine.controller import Controller
from regenmaschine.errors import RainMachineError

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType
from homeassistant.util.dt import as_timestamp, utcnow

from .const import DATA_PROGRAMS, DATA_ZONES, DEFAULT_ZONE_RUN, DOMAIN

if TYPE_CHECKING:
    from . import RainMachineConfigEntry

API_URL_REFERENCE = (
    "https://rainmachine.docs.apiary.io/#reference/weather-services/parserdata/post"
)


CONF_WEATHER = "weather"


class RainMachineService(StrEnum):
    """Store keys for RainMachine services."""

    PAUSE_WATERING = "pause_watering"
    RESTRICT_WATERING = "restrict_watering"
    START_PROGRAM = "start_program"
    START_ZONE = "start_zone"
    STOP_ALL = "stop_all"
    STOP_PROGRAM = "stop_program"
    STOP_ZONE = "stop_zone"
    UNPAUSE_WATERING = "unpause_watering"
    PUSH_FLOW_METER_DATA = "push_flow_meter_data"
    PUSH_WEATHER_DATA = "push_weather_data"
    UNRESTRICT_WATERING = "unrestrict_watering"


class RainMachineServiceArgument(StrEnum):
    """Store keys for RainMachine service arguments."""

    SECONDS = "seconds"
    DURATION = "duration"
    ZONE_RUN_TIME = "zone_run_time"
    VALUE = "value"
    UNIT_OF_MEASUREMENT = "unit_of_measurement"
    TIMESTAMP = "timestamp"
    MINTEMP = "mintemp"
    MAXTEMP = "maxtemp"
    TEMPERATURE = "temperature"
    WIND = "wind"
    SOLARRAD = "solarrad"
    ET = "et"
    QPF = "qpf"
    RAIN = "rain"
    MINRH = "minrh"
    MAXRH = "maxrh"
    CONDITION = "condition"
    PRESSURE = "pressure"
    DEWPOINT = "dewpoint"


CV_FLOW_METER_VALID_UNITS = {
    "clicks",
    "gal",
    "litre",
    "m3",
}

CV_WX_DATA_VALID_PERCENTAGE = probatio.All(probatio.Coerce(int), probatio.Percentage())
CV_WX_DATA_VALID_TEMP_RANGE = probatio.All(
    probatio.Coerce(float), probatio.Range(min=-40.0, max=40.0)
)
CV_WX_DATA_VALID_RAIN_RANGE = probatio.All(
    probatio.Coerce(float), probatio.Range(min=0.0, max=1000.0)
)
CV_WX_DATA_VALID_WIND_SPEED = probatio.All(
    probatio.Coerce(float), probatio.Range(min=0.0, max=65.0)
)
CV_WX_DATA_VALID_PRESSURE = probatio.All(
    probatio.Coerce(float), probatio.Range(min=60.0, max=110.0)
)
CV_WX_DATA_VALID_SOLARRAD = probatio.All(
    probatio.Coerce(float), probatio.Range(min=0.0, max=100.0)
)


SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
    }
)

SERVICE_PAUSE_WATERING_SCHEMA = SERVICE_SCHEMA.extend(
    {
        probatio.Required(RainMachineServiceArgument.SECONDS): cv.positive_int,
    }
)

SERVICE_PUSH_FLOW_METER_DATA_SCHEMA = SERVICE_SCHEMA.extend(
    {
        probatio.Required(RainMachineServiceArgument.VALUE): cv.positive_float,
        probatio.Optional(RainMachineServiceArgument.UNIT_OF_MEASUREMENT): probatio.All(
            cv.string, probatio.In(CV_FLOW_METER_VALID_UNITS)
        ),
    }
)

SERVICE_PUSH_WEATHER_DATA_SCHEMA = SERVICE_SCHEMA.extend(
    {
        probatio.Optional(RainMachineServiceArgument.TIMESTAMP): cv.positive_float,
        probatio.Optional(
            RainMachineServiceArgument.MINTEMP
        ): CV_WX_DATA_VALID_TEMP_RANGE,
        probatio.Optional(
            RainMachineServiceArgument.MAXTEMP
        ): CV_WX_DATA_VALID_TEMP_RANGE,
        probatio.Optional(
            RainMachineServiceArgument.TEMPERATURE
        ): CV_WX_DATA_VALID_TEMP_RANGE,
        probatio.Optional(RainMachineServiceArgument.WIND): CV_WX_DATA_VALID_WIND_SPEED,
        probatio.Optional(
            RainMachineServiceArgument.SOLARRAD
        ): CV_WX_DATA_VALID_SOLARRAD,
        probatio.Optional(RainMachineServiceArgument.QPF): CV_WX_DATA_VALID_RAIN_RANGE,
        probatio.Optional(RainMachineServiceArgument.RAIN): CV_WX_DATA_VALID_RAIN_RANGE,
        probatio.Optional(RainMachineServiceArgument.ET): CV_WX_DATA_VALID_RAIN_RANGE,
        probatio.Optional(
            RainMachineServiceArgument.MINRH
        ): CV_WX_DATA_VALID_PERCENTAGE,
        probatio.Optional(
            RainMachineServiceArgument.MAXRH
        ): CV_WX_DATA_VALID_PERCENTAGE,
        probatio.Optional(RainMachineServiceArgument.CONDITION): cv.string,
        probatio.Optional(
            RainMachineServiceArgument.PRESSURE
        ): CV_WX_DATA_VALID_PRESSURE,
        probatio.Optional(
            RainMachineServiceArgument.DEWPOINT
        ): CV_WX_DATA_VALID_TEMP_RANGE,
    }
)

SERVICE_RESTRICT_WATERING_SCHEMA = SERVICE_SCHEMA.extend(
    {
        probatio.Required(RainMachineServiceArgument.DURATION): cv.time_period,
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
    config_entry: RainMachineConfigEntry
    _, config_entry = service.async_get_device_and_config_entry(
        hass, DOMAIN, call.data[CommonServiceArgument.DEVICE_ID]
    )
    return config_entry


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
                        translation_domain=DOMAIN,
                        translation_key="action_failed",
                        translation_placeholders={"action": call.service},
                    ) from err

                if update_programs_and_zones:
                    await async_update_programs_and_zones(hass, entry)

            return wrapper

        return decorator

    @call_with_controller()
    async def async_pause_watering(call: ServiceCall, controller: Controller) -> None:
        """Pause watering for a set number of seconds."""
        await controller.watering.pause_all(
            call.data[RainMachineServiceArgument.SECONDS]
        )

    @call_with_controller(update_programs_and_zones=False)
    async def async_push_flow_meter_data(
        call: ServiceCall, controller: Controller
    ) -> None:
        """Push flow meter data to the device."""
        value = call.data[RainMachineServiceArgument.VALUE]
        if units := call.data.get(RainMachineServiceArgument.UNIT_OF_MEASUREMENT):
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
                        if key != CommonServiceArgument.DEVICE_ID
                    }
                ]
            }
        )

    @call_with_controller()
    async def async_restrict_watering(
        call: ServiceCall, controller: Controller
    ) -> None:
        """Restrict watering for a time period."""
        duration = call.data[RainMachineServiceArgument.DURATION]
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
            RainMachineService.PAUSE_WATERING,
            SERVICE_PAUSE_WATERING_SCHEMA,
            async_pause_watering,
        ),
        (
            RainMachineService.PUSH_FLOW_METER_DATA,
            SERVICE_PUSH_FLOW_METER_DATA_SCHEMA,
            async_push_flow_meter_data,
        ),
        (
            RainMachineService.PUSH_WEATHER_DATA,
            SERVICE_PUSH_WEATHER_DATA_SCHEMA,
            async_push_weather_data,
        ),
        (
            RainMachineService.RESTRICT_WATERING,
            SERVICE_RESTRICT_WATERING_SCHEMA,
            async_restrict_watering,
        ),
        (RainMachineService.STOP_ALL, SERVICE_SCHEMA, async_stop_all),
        (RainMachineService.UNPAUSE_WATERING, SERVICE_SCHEMA, async_unpause_watering),
        (
            RainMachineService.UNRESTRICT_WATERING,
            SERVICE_SCHEMA,
            async_unrestrict_watering,
        ),
    ):
        hass.services.async_register(
            DOMAIN,
            service_name,
            method,
            schema=schema,
            description_placeholders={
                "api_url": API_URL_REFERENCE,
            },
        )

    entity_services: tuple[tuple[RainMachineService, VolDictType | None, str], ...] = (
        (RainMachineService.START_PROGRAM, None, "async_start_program"),
        (
            RainMachineService.START_ZONE,
            {
                probatio.Optional(
                    RainMachineServiceArgument.ZONE_RUN_TIME, default=DEFAULT_ZONE_RUN
                ): cv.positive_int
            },
            "async_start_zone",
        ),
        (RainMachineService.STOP_PROGRAM, None, "async_stop_program"),
        (RainMachineService.STOP_ZONE, None, "async_stop_zone"),
    )
    for service_name, entity_schema, func in entity_services:
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            service_name,
            entity_domain=SWITCH_DOMAIN,
            func=func,
            schema=entity_schema,
        )
