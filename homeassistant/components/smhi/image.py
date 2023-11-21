"""Helps expose radar imageEntity."""
import datetime
import logging

import aiohttp

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_SENSOR_FORMAT = "camera.smhi_radar_map_{}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add radar image entity from smhi api."""
    location = config_entry.data
    name = slugify(location[CONF_NAME])

    radarEntity = RadarImage(hass=hass, verify_ssl=False)
    radarEntity.entity_id = ENTITY_ID_SENSOR_FORMAT.format(name)

    async_add_entities([radarEntity], True)


class RadarImage(ImageEntity):
    """Representation of a image entity to display radar images."""

    async def async_image(self) -> bytes | None:
        """Fetch and return bytes of SMHI radar map."""
        try:
            current_date = datetime.datetime.now().strftime("%Y/%m/%d")

            async with get_async_client(hass=self.hass) as client:
                # Replace this URL with the actual SMHI API endpoint for radar map
                response = await client.get(
                    f"https://opendata-download-radar.smhi.se/api/version/latest/area/sweden/product/comp/{current_date}?timeZone=Europe/Stockholm"
                )
                response.raise_for_status()  # Raise an exception for 4xx and 5xx status codes

                # Parse the JSON response
                data = response.json()

                png_links = [
                    format_link["link"]
                    for file in data["files"]
                    if "formats" in file
                    for format_link in file["formats"]
                    if "png" in format_link.get("key", "").lower()
                ]

                # Assuming you want to display the first PNG image, you can modify this logic
                if png_links:
                    self._attr_image_url = png_links[0]

                    # Fetch the PNG image
                    png_response = await client.get(str(self._attr_image_url))
                    png_response.raise_for_status()

                    self._attr_content_type = "image/png"
                    self.async_write_ha_state()

                    return png_response.content
        except aiohttp.ClientError:
            # Handle request errors (e.g., network issues)
            _LOGGER.error("Failed to connect to SMHI API, retry in 5 minutes")
            return None
        return None

    @property
    def name(self) -> str:
        """Name of this entity."""
        return "SMHI Radar Map"

    @property
    def unique_id(self) -> str:
        """Unique entity id."""
        return "smhi_radar_map"
