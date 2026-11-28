"""Actions for the CalDAV integration."""

from enum import StrEnum
from http import HTTPStatus
from typing import TYPE_CHECKING

from caldav.lib.error import DAVError, ReportError
from caldav.lib.http_sync import requests as caldav_requests
import probatio

from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.util import dt as dt_util

from .api import get_busy_periods
from .const import DOMAIN

if TYPE_CHECKING:
    from .calendar import WebDavCalendarEntity


class CalDavService(StrEnum):
    """CalDAV actions."""

    GET_FREE_BUSY = "get_free_busy"


class CalDavServiceArgument(StrEnum):
    """CalDAV action fields."""

    START = "start"
    END = "end"


async def _async_get_free_busy(
    entity: WebDavCalendarEntity, call: ServiceCall
) -> ServiceResponse:
    """Return the busy periods of a calendar in local time."""
    start = dt_util.as_utc(call.data[CalDavServiceArgument.START])
    end = dt_util.as_utc(call.data[CalDavServiceArgument.END])
    if end <= start:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="end_not_after_start"
        )
    if entity.coordinator.search is not None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="free_busy_search_not_supported",
            translation_placeholders={"calendar": entity.entity_id},
        )
    try:
        periods = await entity.hass.async_add_executor_job(
            get_busy_periods, entity.coordinator.calendar, start, end
        )
    except (caldav_requests.exceptions.RequestException, DAVError) as err:
        translation_key = "free_busy_request_failed"
        if isinstance(err, ReportError) and err.status in (
            HTTPStatus.METHOD_NOT_ALLOWED,
            HTTPStatus.NOT_IMPLEMENTED,
        ):
            translation_key = "free_busy_query_not_supported"
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"calendar": entity.entity_id},
        ) from err
    return {
        "periods": [
            {
                "start": dt_util.as_local(period.start).isoformat(),
                "end": dt_util.as_local(period.end).isoformat(),
            }
            for period in periods
        ]
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the CalDAV actions."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        CalDavService.GET_FREE_BUSY,
        entity_domain=CALENDAR_DOMAIN,
        schema={
            probatio.Required(CalDavServiceArgument.START): cv.datetime,
            probatio.Required(CalDavServiceArgument.END): cv.datetime,
        },
        func=_async_get_free_busy,
        supports_response=SupportsResponse.ONLY,
    )
