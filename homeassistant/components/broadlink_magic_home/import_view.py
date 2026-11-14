"""HTTP endpoint used by the Magic Home app to import a family."""

from contextlib import suppress
import logging

from aiohttp import web
from broadlink_magic import ImportDataError, parse_import_payload

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.util.hass_dict import HassKey

from .const import IMPORT_PATH
from .import_session import get_import_manager

_LOGGER = logging.getLogger(__name__)
MAX_IMPORT_SIZE = 4 * 1024 * 1024
READ_CHUNK_SIZE = 64 * 1024
DATA_IMPORT_VIEW_REGISTERED: HassKey[bool] = HassKey(
    "broadlink_magic_import_view_registered"
)


def _response(status: int, msg: str) -> web.Response:
    return web.json_response({"error": status, "status": status, "msg": msg})


class FamilyImportView(HomeAssistantView):
    """Receive one-time family imports from Magic Home."""

    url = IMPORT_PATH
    name = "api:broadlink:magic_family_import"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        """Receive and validate a Magic Home family snapshot."""
        project_id = request.query.get("projectid", "")
        if not project_id:
            return _response(-1, "invalid import session")

        hass = request.app[KEY_HASS]
        manager = get_import_manager(hass)
        session = manager.get(project_id)
        if session is None or session.consumed:
            return _response(-1, "invalid or expired import session")

        if (request.content_length or 0) > MAX_IMPORT_SIZE:
            return _response(-1, "family data too large")
        body = bytearray()
        async for chunk in request.content.iter_chunked(READ_CHUNK_SIZE):
            body.extend(chunk)
            if len(body) > MAX_IMPORT_SIZE:
                return _response(-1, "family data too large")

        try:
            families = parse_import_payload(bytes(body))
        except ImportDataError as err:
            _LOGGER.warning("Rejected invalid BroadLink Magic family import: %s", err)
            return _response(-1, "invalid family data")

        if not session.complete(families):
            return _response(-1, "import session already consumed")
        if (flow_id := session.flow_id) is not None:

            async def _async_continue_flow() -> None:
                with suppress(UnknownFlow):
                    await hass.config_entries.flow.async_configure(flow_id, {})

            hass.async_create_task(_async_continue_flow())
        return _response(0, "success")


@callback
def async_register_import_view(hass: HomeAssistant) -> None:
    """Register the import view exactly once, including during config flow."""
    if hass.data.get(DATA_IMPORT_VIEW_REGISTERED):
        return
    hass.http.register_view(FamilyImportView())
    hass.data[DATA_IMPORT_VIEW_REGISTERED] = True
