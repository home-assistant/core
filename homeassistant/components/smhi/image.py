"""Helps expose radar imageEntity."""
import datetime
from io import BytesIO
import logging

import aiohttp
from PIL import Image, UnidentifiedImageError

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
        """Fetch and return bytes of SMHI radar image and corresponding map combined."""
        try:
            # Get the current date in Y/M/D format
            current_date = datetime.datetime.now().strftime("%Y/%m/%d")

            async with get_async_client(hass=self.hass) as client:
                # Get response from smhi API with radar png links
                response = await client.get(
                    f"https://opendata-download-radar.smhi.se/api/version/latest/area/sweden/product/comp/{current_date}?timeZone=Europe/Stockholm"
                )
                response.raise_for_status()  # Raise an exception for 4xx and 5xx status codes

                # Parse the JSON response
                data = response.json()

                # Find the png links
                png_links = [
                    format_link["link"]
                    for file in data["files"]
                    if "formats" in file
                    for format_link in file["formats"]
                    if "png" in format_link.get("key", "").lower()
                ]

                # Use the last link in the list as that is the latest radar, image
                if png_links:
                    self._attr_image_url = png_links[-1]

                    # Fetch Radar PNG image
                    png_response = await client.get(str(self._attr_image_url))
                    png_response.raise_for_status()

                    # Fetch the map
                    actual_map_response = await client.get(
                        "https://sid-proxy.smhi.se/radar/assets/basemap.53dbcde3.png"
                    )
                    actual_map_response.raise_for_status()

                    # Open the radar and map image to combine them
                    radar_image_content = png_response.read()
                    radar_image_io = BytesIO(radar_image_content)
                    radar_image = Image.open(radar_image_io)

                    actual_map_content = actual_map_response.read()
                    actual_map_io = BytesIO(actual_map_content)
                    actual_map_image = Image.open(actual_map_io)

                    # Resize radar image to match actual map dimensions (adjust as needed)
                    radar_image = radar_image.resize(actual_map_image.size)

                    # Combine the actual map and radar images using alpha compositing
                    combined_image = Image.alpha_composite(
                        actual_map_image.convert("RGBA"), radar_image.convert("RGBA")
                    )

                    # Convert the combined image to bytes and set entity attributes
                    output_bytes = BytesIO()
                    combined_image.save(output_bytes, format="PNG")
                    self._attr_content_type = "image/png"

                    return output_bytes.getvalue()
        except aiohttp.ClientError:
            _LOGGER.error("Failed to connect to SMHI API")
            return None
        except UnidentifiedImageError as img_err:
            _LOGGER.error("Error opening image retrieved from SMHI API: %s", img_err)
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
