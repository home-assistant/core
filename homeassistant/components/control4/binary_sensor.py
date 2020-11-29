"""Platform for Control4 Alarm Control Panel."""
from datetime import timedelta
import json
import logging

from pyControl4.error_handling import C4Exception

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_WINDOW,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import Control4Entity, get_items_of_category
from .const import CONF_DIRECTOR, CONTROL4_ENTITY_TYPE, DOMAIN
from .director_utils import director_update_data

_LOGGER = logging.getLogger(__name__)

CONTROL4_CATEGORY = "sensors"
CONTROL4_CONTROL_TYPE = "control4_contactsingle"
CONTROL4_SENSOR_VAR = "ContactState"

CONTROL4_DOOR_PROXY = "contactsingle_doorcontactsensor_c4"
CONTROL4_WINDOW_PROXY = "contactsingle_windowcontactsensor_c4"
CONTROL4_MOTION_PROXY = "contactsingle_motionsensor_c4"

CONTROL4_PROXY_MAPPING = {
    CONTROL4_DOOR_PROXY: DEVICE_CLASS_DOOR,
    CONTROL4_WINDOW_PROXY: DEVICE_CLASS_WINDOW,
    CONTROL4_MOTION_PROXY: DEVICE_CLASS_MOTION,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Control4 alarm control panels from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    scan_interval = entry_data[CONF_SCAN_INTERVAL]
    _LOGGER.debug(
        "Scan interval = %s",
        scan_interval,
    )

    async def async_update_data():
        """Fetch data from Control4 director for alarm control panels."""
        try:
            return await director_update_data(hass, entry, CONTROL4_SENSOR_VAR)
        except C4Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="binary_sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    items_of_category = await get_items_of_category(hass, entry, CONTROL4_CATEGORY)
    director = entry_data[CONF_DIRECTOR]
    for item in items_of_category:
        if (
            item["type"] == CONTROL4_ENTITY_TYPE
            and item["control"] == CONTROL4_CONTROL_TYPE
        ):
            item_name = item["name"]
            item_id = item["id"]
            item_parent_id = item["parentId"]
            item_coordinator = coordinator

            item_manufacturer = None
            item_device_name = None
            item_model = None

            item_device_class = DEVICE_CLASS_OPENING
            for proxy_type in [
                CONTROL4_DOOR_PROXY,
                CONTROL4_WINDOW_PROXY,
                CONTROL4_MOTION_PROXY,
            ]:
                if item["proxy"] == proxy_type:
                    item_device_class = CONTROL4_PROXY_MAPPING[proxy_type]
                    break

            item_setup_info = await director.getItemSetup(item_id)
            item_setup_info = json.loads(item_setup_info)
            item_alarm_zone_id = None
            if "panel_setup" in item_setup_info:
                for key in item_setup_info["panel_setup"]["all_zones"]["zone_info"]:
                    if key["name"] == item_name:
                        item_alarm_zone_id = key["id"]
                        break

            async_add_entities(
                [
                    Control4BinarySensor(
                        entry_data,
                        entry,
                        item_coordinator,
                        item_name,
                        item_id,
                        item_device_name,
                        item_manufacturer,
                        item_model,
                        item_parent_id,
                        item_device_class,
                        item_alarm_zone_id,
                    )
                ],
                True,
            )


class Control4BinarySensor(Control4Entity, BinarySensorEntity):
    """Control4 alarm control panel entity."""

    def __init__(
        self,
        entry_data: dict,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        name: str,
        idx: int,
        device_name: str,
        device_manufacturer: str,
        device_model: str,
        device_id: int,
        device_class: str,
        alarm_zone_id: int,
    ):
        """Initialize Control4 light entity."""
        super().__init__(
            entry_data,
            entry,
            coordinator,
            name,
            idx,
            device_name,
            device_manufacturer,
            device_model,
            device_id,
        )
        self._device_class = device_class
        self._alarm_zone_id = alarm_zone_id

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        # In Control4, True = closed/clear and False = open/not clear
        return not bool(self.coordinator.data[self._idx]["value"])

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def device_info(self):
        """Return info of parent Control4 device of entity."""
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._alarm_zone_id is not None:
            return {"alarm_zone_id": self._alarm_zone_id}
        return None
