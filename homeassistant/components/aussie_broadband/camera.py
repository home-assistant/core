"""Support for Aussie Broadband CVC graph cameras."""
from __future__ import annotations

from datetime import timedelta

import requests

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from ...util import Throttle
from .const import ATTR_SERVICE_ID


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up Aussie Broadband camera from a config entry."""
    client = hass.data[DOMAIN][entry.entry_id]
    service_id = entry.data[ATTR_SERVICE_ID]

    services = await hass.async_add_executor_job(client.get_services)
    service = next(s for s in services if s["service_id"] == service_id)

    entities_to_add = []

    if service["type"] == "NBN" and "nbnDetails" in service:
        nbn_details = service["nbnDetails"]
        cvc_graph_url = nbn_details["cvcGraph"]
        name = f"{nbn_details['poiName']} POI CVC"
        entities_to_add.append(
            CVCGraphCamera(
                service_id=service_id,
                url=cvc_graph_url,
                name=name,
            )
        )

    async_add_entities(entities_to_add)
    return True


MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)


class CVCGraphCamera(Camera):
    """Representation of a Aussie Broadband CVC graph camera."""

    def __init__(self, service_id: int, name: str, url: str):
        """Initialize the camera."""
        super().__init__()

        self._service_id = service_id
        self._url = url
        self._name = name
        self._last_image: bytes | None = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def _update_image(self):
        response = requests.get(self._url, timeout=10)
        self._last_image = response.content

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        self._update_image()
        return self._last_image

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return str(self._service_id)
