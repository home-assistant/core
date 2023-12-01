import os
from datetime import datetime, timedelta
import logging
from typing import Any
import yaml

import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from datetime import datetime

from .canvas_api import CanvasAPI
from .const import (
    ANNOUNCEMENTS_KEY,
    ASSIGNMENTS_KEY,
    CONVERSATIONS_KEY,
    GRADES_KEY,
    QUICK_LINKS_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class CanvasUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Canvas integration."""

    def __init__(self, hass, entry: ConfigEntry, api: CanvasAPI):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method = self.async_update_data,
            update_interval=timedelta(seconds=30),
        )
        self.config_entry = entry
        self.api = api
        self.update_entities = None
        self.selected_courses = entry.options["courses"]

    async def async_update_data(self):
        """Fetch data from API endpoint."""
        courses = self.selected_courses
        course_ids = courses.keys()
        try:
            async with async_timeout.timeout(10):
                assignments = await self.api.async_get_upcoming_assignments(course_ids)
                announcements = await self.api.async_get_announcements(course_ids)
                conversations = await self.api.async_get_conversations()
                grades = await self.api.async_get_grades(course_ids)
                quick_links = self.get_quick_links()

                new_data = {
                    ASSIGNMENTS_KEY: assignments,
                    ANNOUNCEMENTS_KEY: announcements,
                    CONVERSATIONS_KEY: conversations,
                    GRADES_KEY: grades,
                    QUICK_LINKS_KEY: quick_links,
                }

                if self.update_entities:
                    self.update_entities(new_data)

                return new_data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    def get_quick_links(self):
        config_path = self.hass.config.path("canvas.yaml")

        try:
            with open(config_path, "r") as file:
                config_dict = yaml.safe_load(file)
                links = config_dict["quick_links"]
                return {f"quick_link-{link['name']}": link for link in links}
        except FileNotFoundError:
            print("The YAML file was not found.")
        except yaml.YAMLError as exc:
            print(f"Error in YAML file: {exc}")
        except Exception as e:
            print(f"An error occurred: {e}")

        return {}

