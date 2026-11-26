"""HTTP views for the Nibe Heat Pump integration."""

from http import HTTPStatus

from aiohttp.hdrs import CONTENT_DISPOSITION
from aiohttp.web import Request, Response
from nibe.coil import Coil
from nibe.exceptions import CoilNotFoundException
from nibe.log_set import format_log_set

from homeassistant.components.http import KEY_HASS, KEY_HASS_USER, HomeAssistantView
from homeassistant.config_entries import ConfigEntryState

from .const import CONF_CONNECTION_TYPE, CONF_CONNECTION_TYPE_NIBEGW, DOMAIN
from .coordinator import CoilCoordinator, NibeHeatpumpConfigEntry

LOG_SET_URL = "/api/nibe_heatpump/{entry_id}/log_set"


def supports_log_set(config_entry: NibeHeatpumpConfigEntry) -> bool:
    """Return if the pump of the entry reads LOG.SET to select broadcast coils."""
    return config_entry.data[CONF_CONNECTION_TYPE] == CONF_CONNECTION_TYPE_NIBEGW


def log_set_coils(coordinator: CoilCoordinator) -> list[Coil]:
    """Return the coils the entities listen to, read only coils first.

    MODBUS40 only sends the first MODBUS40_SLOTS slots, the rest are polled.
    """
    coils: list[Coil] = []
    for address in sorted(coordinator.context_callbacks):
        try:
            coils.append(coordinator.heatpump.get_coil_by_address(address))
        except CoilNotFoundException:
            continue
    return sorted(coils, key=lambda coil: coil.is_writable)


class LogSetView(HomeAssistantView):
    """Download a LOG.SET for the coils in use."""

    url = LOG_SET_URL
    name = "api:nibe_heatpump:log_set"

    async def get(self, request: Request, entry_id: str) -> Response:
        """Return the LOG.SET file."""
        if not request[KEY_HASS_USER].is_admin:
            return Response(status=HTTPStatus.UNAUTHORIZED)

        hass = request.app[KEY_HASS]
        entry: NibeHeatpumpConfigEntry | None = hass.config_entries.async_get_entry(
            entry_id
        )
        if (
            entry is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
            or not supports_log_set(entry)
        ):
            return Response(status=HTTPStatus.NOT_FOUND)

        return Response(
            body=format_log_set(log_set_coils(entry.runtime_data)),
            content_type="application/octet-stream",
            headers={CONTENT_DISPOSITION: 'attachment; filename="LOG.SET"'},
        )
