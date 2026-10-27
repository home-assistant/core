"""Services for the input_datetime integration."""

import probatio

from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import (
    DATA_INPUT_DATETIME,
    DOMAIN,
    InputDatetimeService,
    InputDatetimeServiceArgument,
)

RELOAD_SERVICE_SCHEMA = probatio.Schema({})


def _validate_set_datetime_attrs(config):
    """Validate set_datetime service attributes."""
    has_date_or_time_attr = any(
        key in config
        for key in (
            InputDatetimeServiceArgument.DATE,
            InputDatetimeServiceArgument.TIME,
        )
    )
    if (
        sum(
            [
                has_date_or_time_attr,
                InputDatetimeServiceArgument.DATETIME in config,
                InputDatetimeServiceArgument.TIMESTAMP in config,
            ]
        )
        > 1
    ):
        raise probatio.Invalid(f"Cannot use together: {', '.join(config.keys())}")
    return config


async def _async_reload_service(service_call: ServiceCall) -> None:
    """Reload yaml entities."""
    hass = service_call.hass
    data = hass.data[DATA_INPUT_DATETIME]
    conf = await data.component.async_prepare_reload(skip_reset=True)
    await data.yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in conf.get(DOMAIN, {}).items()]
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the input_datetime services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        InputDatetimeService.RELOAD,
        _async_reload_service,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    hass.data[DATA_INPUT_DATETIME].component.async_register_entity_service(
        InputDatetimeService.SET,
        probatio.All(
            cv.make_entity_service_schema(
                {
                    probatio.Optional(InputDatetimeServiceArgument.DATE): cv.date,
                    probatio.Optional(InputDatetimeServiceArgument.TIME): cv.time,
                    probatio.Optional(
                        InputDatetimeServiceArgument.DATETIME
                    ): cv.datetime,
                    probatio.Optional(
                        InputDatetimeServiceArgument.TIMESTAMP
                    ): probatio.Coerce(float),
                },
            ),
            probatio.AtLeastOne(
                InputDatetimeServiceArgument.DATE.value,
                InputDatetimeServiceArgument.TIME.value,
                InputDatetimeServiceArgument.DATETIME.value,
                InputDatetimeServiceArgument.TIMESTAMP.value,
            ),
            _validate_set_datetime_attrs,
        ),
        "async_set_datetime",
    )
