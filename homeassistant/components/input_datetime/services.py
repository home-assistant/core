"""Services for the input_datetime integration."""

import probatio

from homeassistant.const import ATTR_DATE, ATTR_TIME, CONF_ID, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import ATTR_DATETIME, ATTR_TIMESTAMP, DATA_INPUT_DATETIME, DOMAIN

RELOAD_SERVICE_SCHEMA = probatio.Schema({})


def _validate_set_datetime_attrs(config):
    """Validate set_datetime service attributes."""
    has_date_or_time_attr = any(key in config for key in (ATTR_DATE, ATTR_TIME))
    if (
        sum([has_date_or_time_attr, ATTR_DATETIME in config, ATTR_TIMESTAMP in config])
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
        SERVICE_RELOAD,
        _async_reload_service,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    hass.data[DATA_INPUT_DATETIME].component.async_register_entity_service(
        "set_datetime",
        probatio.All(
            cv.make_entity_service_schema(
                {
                    probatio.Optional(ATTR_DATE): cv.date,
                    probatio.Optional(ATTR_TIME): cv.time,
                    probatio.Optional(ATTR_DATETIME): cv.datetime,
                    probatio.Optional(ATTR_TIMESTAMP): probatio.Coerce(float),
                },
            ),
            probatio.AtLeastOne(ATTR_DATE, ATTR_TIME, ATTR_DATETIME, ATTR_TIMESTAMP),
            _validate_set_datetime_attrs,
        ),
        "async_set_datetime",
    )
