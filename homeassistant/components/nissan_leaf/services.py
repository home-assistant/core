"""Services for the Nissan Leaf integration."""

from datetime import timedelta
import logging

import probatio

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from .const import DATA_LEAF, DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_UPDATE_LEAF = "update"
SERVICE_START_CHARGE_LEAF = "start_charge"
ATTR_VIN = "vin"

UPDATE_LEAF_SCHEMA = probatio.Schema({probatio.Required(ATTR_VIN): cv.string})
START_CHARGE_LEAF_SCHEMA = probatio.Schema({probatio.Required(ATTR_VIN): cv.string})


async def _async_handle_update(service: ServiceCall) -> None:
    """Handle service to update leaf data from Nissan servers."""
    hass = service.hass
    vin = service.data[ATTR_VIN]

    if vin in hass.data[DATA_LEAF]:
        data_store = hass.data[DATA_LEAF][vin]
        await data_store.async_update_data(utcnow())
    else:
        _LOGGER.debug("Vin %s not recognised for update", vin)


async def _async_handle_start_charge(service: ServiceCall) -> None:
    """Handle service to start charging."""
    _LOGGER.warning(
        "The 'nissan_leaf.start_charge' service is deprecated and has been"
        "replaced by a dedicated button entity: Please use that to start"
        "the charge instead"
    )
    hass = service.hass
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


def setup_services(hass: HomeAssistant) -> None:
    """Register the Nissan Leaf services."""
    hass.services.register(
        DOMAIN, SERVICE_UPDATE_LEAF, _async_handle_update, schema=UPDATE_LEAF_SCHEMA
    )
    hass.services.register(
        DOMAIN,
        SERVICE_START_CHARGE_LEAF,
        _async_handle_start_charge,
        schema=START_CHARGE_LEAF_SCHEMA,
    )
