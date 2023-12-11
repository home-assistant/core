"""Helps expose radar imageEntity."""
import datetime
from io import BytesIO
import logging

from PIL import Image, UnidentifiedImageError

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .downloader import SmhiDownloader  # Import the SmhiDownloader class

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_SENSOR_FORMAT = "camera.smhi_radar_map_{}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an SMHI radar image entity in Home Assistant.

    Args:
        hass: HomeAssistant instance.
        config_entry: Configuration entry for this entity.
        async_add_entities: Callback to add entities to Home Assistant.

    This function creates a RadarImage entity based on the provided configuration entry and adds it to Home Assistant.
    """
    location = config_entry.data
    name = slugify(location[CONF_NAME])

    radarEntity = RadarImage(hass=hass, verify_ssl=False)
    radarEntity.entity_id = ENTITY_ID_SENSOR_FORMAT.format(name)

    async_add_entities([radarEntity], True)


class RadarImage(ImageEntity):
    """Represents an image entity to display radar images from SMHI.

    This entity fetches and combines radar imagery and map data to provide a visual representation of weather radar data.
    """

    async def async_image(self) -> bytes | None:
        """Fetch and return the combined image of SMHI radar data and a map.

        Returns:
            Bytes of the combined radar and map image or None if an error occurs.

        This method fetches the latest radar image from SMHI API, combines it with a map background, and returns the resulting image as bytes. In case of errors, it logs the issue and returns None.
        """
        try:
            current_date = datetime.datetime.now().strftime("%Y/%m/%d")
            url = f"https://opendata-download-radar.smhi.se/api/version/latest/area/sweden/product/comp/{current_date}?timeZone=Europe/Stockholm"
            downloader = SmhiDownloader()
            # Use the downloader to get the JSON data
            data = await downloader.download_json(url)
            if data is None:
                _LOGGER.error("Failed to fetch radar data from SMHI API")
                return None

            # Find the png links
            png_links = [
                format_link["link"]
                for file in data["files"]
                if "formats" in file
                for format_link in file["formats"]
                if "png" in format_link.get("key", "").lower()
            ]

            # Use the last link in the list as that is the latest radar image
            if png_links:
                self._attr_image_url = png_links[-1]

                # Use the downloader to fetch the radar PNG image
                radar_image_content = await downloader.fetch_binary(
                    self.hass.helpers.aiohttp_client.async_get_clientsession(self.hass),
                    str(self._attr_image_url),
                )
                if radar_image_content is None:
                    _LOGGER.error("Failed to fetch radar image from SMHI API")
                    return None

                # Fetch the map
                actual_map_content = await downloader.fetch_binary(
                    self.hass.helpers.aiohttp_client.async_get_clientsession(self.hass),
                    "https://sid-proxy.smhi.se/radar/assets/basemap.53dbcde3.png",
                )
                if actual_map_content is None:
                    _LOGGER.error("Failed to fetch map from SMHI API")
                    return None

                combined_image: Image.Image = self.combine_radar_images(
                    radar_image_content, actual_map_content
                )
                # Convert the combined image to bytes and set entity attributes
                output_bytes = BytesIO()
                combined_image.save(output_bytes, format="PNG")
                self._attr_content_type = "image/png"

                return output_bytes.getvalue()
            return None

        except UnidentifiedImageError as img_err:
            _LOGGER.error("Error opening image retrieved from SMHI API: %s", img_err)
            return None

    @staticmethod
    def combine_radar_images(
        radar_image_content: bytes, map_image_content: bytes
    ) -> Image.Image:
        """Combine the radar image with the map.

        Args:
            radar_image_content: The content of the radar image as bytes.
            map_image_content: The content of the map image as bytes.

        Returns:
            Image: The combined image.

        This method opens the radar and map images, resizes the radar image to match the map dimensions, and combines them using alpha compositing.
        """
        # Open the radar and map image to combine them
        radar_image_io = BytesIO(radar_image_content)
        radar_image = Image.open(radar_image_io)

        actual_map_io = BytesIO(map_image_content)
        actual_map_image = Image.open(actual_map_io)

        # Resize radar image to match actual map dimensions
        radar_image = radar_image.resize(actual_map_image.size)

        combined_image: Image.Image = Image.alpha_composite(
            actual_map_image.convert("RGBA"), radar_image.convert("RGBA")
        )
        # Combine the actual map and radar images using alpha compositing
        return combined_image

    @property
    def name(self) -> str:
        """Name of this entity."""
        return "SMHI Radar Map"

    @property
    def unique_id(self) -> str:
        """Unique entity id."""
        return "smhi_radar_map"
