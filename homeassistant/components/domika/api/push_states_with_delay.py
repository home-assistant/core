"""Integration push states api."""

import asyncio
from http import HTTPStatus
from typing import Any
import uuid

from aiohttp import web
import domika_ha_framework.database.core as database_core
from domika_ha_framework.errors import DomikaFrameworkBaseError
import domika_ha_framework.push_data.service as push_data_service

from homeassistant.core import async_get_hass
from homeassistant.helpers.http import HomeAssistantView

from ..const import DOMAIN, LOGGER
from ..ha_entity import service as ha_entity_service


class DomikaAPIPushStatesWithDelay(HomeAssistantView):
    """Push state with delay endpoint."""

    url = "/domika/push_states_with_delay"
    name = "domika:push-states-with-delay"

    async def post(self, request: web.Request) -> web.Response:
        """Post method."""
        # Check that integration still loaded.
        hass = async_get_hass()
        if not hass.data.get(DOMAIN):
            return self.json_message("Route not found.", HTTPStatus.NOT_FOUND)

        request_dict: dict[str, Any] = await request.json()

        try:
            app_session_id = uuid.UUID(request.headers.get("X-App-Session-Id"))
        except (TypeError, ValueError):
            return self.json_message(
                "Missing or malformed X-App-Session-Id.",
                HTTPStatus.UNAUTHORIZED,
            )

        entity_id = request_dict.get("entity_id")
        delay = float(request_dict.get("delay", 0))
        ignore_need_push = request_dict.get("ignore_need_push", False)
        need_push = None if ignore_need_push else True

        LOGGER.debug(
            "DomikaAPIPushStatesWithDelay: request_dict: %s, app_session_id: %s",
            request_dict,
            app_session_id,
        )

        await asyncio.sleep(delay)

        try:
            async with database_core.get_session() as session:
                result = await ha_entity_service.get(
                    session,
                    app_session_id,
                    need_push=need_push,
                    entity_id=entity_id,
                )
                await push_data_service.delete_for_app_session(
                    session,
                    app_session_id=app_session_id,
                    entity_id=entity_id,
                )

        except DomikaFrameworkBaseError as e:
            LOGGER.error("DomikaAPIPushStatesWithDelay. Framework error. %s", e)
            return self.json_message(
                "Framework error.", HTTPStatus.INTERNAL_SERVER_ERROR
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("DomikaAPIPushStatesWithDelay. Unhandled error")
            return self.json_message(
                "Internal error.", HTTPStatus.INTERNAL_SERVER_ERROR
            )

        data = {"entities": result}
        LOGGER.debug("DomikaAPIPushStatesWithDelay data: %s", data)

        return self.json(data, HTTPStatus.OK)
