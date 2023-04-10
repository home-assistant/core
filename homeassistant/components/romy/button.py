"""Defines Buttons for your ROMY."""

import json
import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .utils import async_query

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ROMY sensor with config entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    name = config_entry.data[CONF_NAME]
    unique_id = ""
    model = ""
    firmware = ""

    ret, response = await async_query(hass, host, port, "get/robot_id")
    if ret:
        status = json.loads(response)
        unique_id = status["unique_id"]
        model = status["model"]
        firmware = status["firmware"]
    else:
        _LOGGER.error("Error fetching unique_id resp: %s", response)

    device_info = {
        "manufacturer": "ROMY",
        "model": model,
        "sw_version": firmware,
        "identifiers": {"serial": unique_id},
    }

    romy_button_clean = RomyCleanButton(
        host, port, name, unique_id, device_info, "clean", "set/clean_start_or_continue"
    )
    romy_button_go_home = RomyCleanButton(
        host, port, name, unique_id, device_info, "go home", "set/go_home"
    )
    romy_button_stop = RomyCleanButton(
        host, port, name, unique_id, device_info, "stop", "set/stop"
    )

    # add standard sensors
    romy_button_entities = [romy_button_clean, romy_button_go_home, romy_button_stop]

    # fetch rooms(areas) from current map and add for each a button to clean it
    ret, response = await async_query(hass, host, port, "get/areas")
    if ret:
        json_data = json.loads(response)
        map_id = json_data["map_id"]
        for area in json_data["areas"]:
            if area["area_type"] == "room":
                new_romy_button_clean_area = RomyCleanButton(
                    host,
                    port,
                    name,
                    unique_id,
                    device_info,
                    f"clean {area['area_meta_data']}",
                    f"set/clean_map?map_id={map_id}&area_ids={area['id']}",
                )
                _LOGGER.info(
                    "%s: Adding clean button for area %s", name, area["area_meta_data"]
                )
                romy_button_entities.append(new_romy_button_clean_area)
    else:
        _LOGGER.error(
            "ROMY function async_setup_entry get/areas -> async_query response: %s",
            response,
        )

    async_add_entities(romy_button_entities, True)


class RomyCleanButton(ButtonEntity):
    """Class to hold ROMY CleanButton info."""

    def __init__(
        self,
        host: str,
        port: int,
        name: str,
        unique_id: str,
        device_info: dict[str, Any],
        button_name: str,
        button_command: str,
    ) -> None:
        """Initialize ROMYs CleanButton."""
        self._name = name
        self._host = host
        self._port = port
        self._attr_unique_id = unique_id
        self._device_info = device_info

        self._button_name = button_name
        self._button_command = button_command

    @property
    def name(self) -> str:
        """Return the name of the button."""
        return f"{self._name} {self._button_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"button_{self._name}_{self._button_name}_{self._attr_unique_id}"

    async def async_press(self) -> None:
        """Send ROMY a cleaning command."""
        ret, response = await async_query(
            self.hass, self._host, self._port, self._button_command
        )
        if ret:
            _LOGGER.info("%s: Button %s got pressed!", self._name, self._button_name)
        else:
            _LOGGER.error(
                "%s: Button %s async_update -> async_query response: %s",
                self._name,
                self._button_name,
                response,
            )
