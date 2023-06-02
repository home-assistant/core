"""Event parser and human readable log generator."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from http import HTTPStatus
from typing import Any, cast

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.filters import Filters
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import InvalidEntityFormatError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .helpers import async_determine_event_types
from .processor import EventProcessor


@callback
def async_setup(
    hass: HomeAssistant,
    conf: ConfigType,
    filters: Filters | None,
    entities_filter: Callable[[str], bool] | None,
) -> None:
    """Set up the logbook rest API."""
    hass.http.register_view(LogbookView(conf, filters, entities_filter))


class LogbookView(HomeAssistantView):
    """Handle logbook view requests."""

    url = "/api/logbook"
    name = "api:logbook"
    extra_urls = ["/api/logbook/{datetime}"]

    def __init__(
        self,
        config: dict[str, Any],
        filters: Filters | None,
        entities_filter: Callable[[str], bool] | None,
    ) -> None:
        """Initialize the logbook view."""
        self.config = config
        self.filters = filters
        self.entities_filter = entities_filter

    async def get(
        self, request: web.Request, datetime: str | None = None
    ) -> web.Response:
        """Retrieve logbook entries."""
        if datetime:
            if (datetime_dt := dt_util.parse_datetime(datetime)) is None:
                return self.json_message("Invalid datetime", HTTPStatus.BAD_REQUEST)
        else:
            datetime_dt = dt_util.start_of_local_day()

        if (period_str := request.query.get("period")) is None:
            period: int = 1
        else:
            period = int(period_str)

        if entity_ids_str := request.query.get("entity"):
            try:
                entity_ids = cv.entity_ids(entity_ids_str)
            except vol.Invalid:
                raise InvalidEntityFormatError(
                    f"Invalid entity id(s) encountered: {entity_ids_str}. "
                    "Format should be <domain>.<object_id>"
                ) from vol.Invalid
        else:
            entity_ids = None

        if (end_time_str := request.query.get("end_time")) is None:
            start_day = dt_util.as_utc(datetime_dt) - timedelta(days=period - 1)
            end_day = start_day + timedelta(days=period)
        else:
            start_day = datetime_dt
            if (end_day_dt := dt_util.parse_datetime(end_time_str)) is None:
                return self.json_message("Invalid end_time", HTTPStatus.BAD_REQUEST)
            end_day = end_day_dt

        hass = request.app["hass"]

        context_id = request.query.get("context_id")

        if entity_ids and context_id:
            return self.json_message(
                "Can't combine entity with context_id", HTTPStatus.BAD_REQUEST
            )

        event_types = async_determine_event_types(hass, entity_ids, None)
        event_processor = EventProcessor(
            hass,
            event_types,
            entity_ids,
            None,
            context_id,
            timestamp=False,
            include_entity_name=True,
        )

        def json_events() -> web.Response:
            """Fetch events and generate JSON."""
            return self.json(
                event_processor.get_events(
                    start_day,
                    end_day,
                )
            )

        return cast(
            web.Response, await get_instance(hass).async_add_executor_job(json_events)
        )
