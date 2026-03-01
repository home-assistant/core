"""Data coordinator for AuroraWatch UK integration."""

import logging
import xml.etree.ElementTree as ET
from datetime import timedelta

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_ACTIVITY_URL, API_TIMEOUT, API_URL, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AurowatchDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching AuroraWatch data from API."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="AuroraWatch",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from AuroraWatch API."""
        try:
            session = async_get_clientsession(self.hass)

            # Fetch both status and activity data
            async with async_timeout.timeout(API_TIMEOUT):
                status_response = await session.get(API_URL)
                status_response.raise_for_status()
                status_xml = await status_response.text()

                activity_response = await session.get(API_ACTIVITY_URL)
                activity_response.raise_for_status()
                activity_xml = await activity_response.text()

            # Parse status XML
            try:
                status_root = ET.fromstring(status_xml)
            except ET.ParseError as err:
                _LOGGER.error("Failed to parse status XML response: %s", err)
                raise UpdateFailed(f"Invalid XML response: {err}") from err

            # Parse activity XML
            try:
                activity_root = ET.fromstring(activity_xml)
            except ET.ParseError as err:
                _LOGGER.error("Failed to parse activity XML response: %s", err)
                raise UpdateFailed(f"Invalid activity XML response: {err}") from err

            # Extract data
            try:
                # Get updated datetime from status
                datetime_element = status_root.find(".//updated/datetime")
                if datetime_element is None or datetime_element.text is None:
                    raise UpdateFailed("Missing 'updated/datetime' element in XML")
                last_updated = datetime_element.text

                # Get site status information
                status_element = status_root.find(".//site_status")
                if status_element is None:
                    raise UpdateFailed("Missing 'site_status' element in XML")

                status_id = status_element.get("status_id")
                if status_id is None:
                    raise UpdateFailed("Missing 'status_id' attribute in site_status")

                project_id = status_element.get("project_id", "Unknown")
                site_id = status_element.get("site_id", "Unknown")
                site_url = status_element.get("site_url", "")

                # Get API version
                api_version = status_root.get("api_version", "Unknown")

                # Get current activity value (most recent in the list)
                activity_elements = activity_root.findall(".//activity")
                activity_value = None
                if activity_elements:
                    # Get the last (most recent) activity reading
                    last_activity = activity_elements[-1]
                    value_element = last_activity.find("value")
                    if value_element is not None and value_element.text is not None:
                        activity_value = float(value_element.text)

                data = {
                    "status": status_id,
                    "last_updated": last_updated,
                    "project_id": project_id,
                    "site_id": site_id,
                    "site_url": site_url,
                    "api_version": api_version,
                    "activity": activity_value,
                }

                _LOGGER.debug("Successfully fetched AuroraWatch data: %s", data)
                return data

            except (AttributeError, KeyError) as err:
                _LOGGER.error("Failed to extract data from XML: %s", err)
                raise UpdateFailed(f"Failed to parse XML structure: {err}") from err

        except Exception as err:
            _LOGGER.error("Error fetching AuroraWatch data: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
