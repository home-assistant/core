import logging

from homeassistant.helpers import area_registry

_LOGGER = logging.getLogger(__name__)


class AreaManager:
    def __init__(self, hass, area_names):
        """Initialize the AreaManager.

        :param hass: Home Assistant instance
        :param area_names: List of area names to ensure exist
        """
        self.hass = hass
        self.area_names = area_names

    async def ensure_areas_exist(self):
        """Ensure all specified areas exist in Home Assistant."""
        # Get area registry instance
        area_reg = area_registry.async_get(self.hass)

        # Collect existing area names
        existing_areas = {area.name for area in area_reg.areas.values()}

        # Create any areas that are missing
        for area_name in self.area_names:
            if area_name not in existing_areas:
                area_reg.async_create(area_name)
                _LOGGER.info(f"Created new area: {area_name}")
            else:
                _LOGGER.info(f"Area '{area_name}' already exists.")
