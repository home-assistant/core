"""Support for OpenUV binary sensors."""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import as_local, parse_datetime, utcnow

from . import OpenUvEntity
from .const import DATA_PROTECTION_WINDOW, DOMAIN, LOGGER, TYPE_PROTECTION_WINDOW

ATTR_PROTECTION_WINDOW_ENDING_TIME = "end_time"
ATTR_PROTECTION_WINDOW_ENDING_UV = "end_uv"
ATTR_PROTECTION_WINDOW_STARTING_TIME = "start_time"
ATTR_PROTECTION_WINDOW_STARTING_UV = "start_uv"

BINARY_SENSOR_DESCRIPTION_PROTECTION_WINDOW = BinarySensorEntityDescription(
    key=TYPE_PROTECTION_WINDOW,
    name="Protection Window",
    icon="mdi:sunglasses",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up an OpenUV sensor based on a config entry."""
    openuv = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [OpenUvBinarySensor(openuv, BINARY_SENSOR_DESCRIPTION_PROTECTION_WINDOW)]
    )


class OpenUvBinarySensor(OpenUvEntity, BinarySensorEntity):
    """Define a binary sensor for OpenUV."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if not (data := self.openuv.data[DATA_PROTECTION_WINDOW]):
            self._attr_available = False
            return

        self._attr_available = True

        for key in ("from_time", "to_time", "from_uv", "to_uv"):
            if not data.get(key):
                LOGGER.info("Skipping update due to missing data: %s", key)
                return

        if self.entity_description.key == TYPE_PROTECTION_WINDOW:
            from_dt = parse_datetime(data["from_time"])
            to_dt = parse_datetime(data["to_time"])

            if not from_dt or not to_dt:
                LOGGER.warning(
                    "Unable to parse protection window datetimes: %s, %s",
                    data["from_time"],
                    data["to_time"],
                )
                self._attr_is_on = False
                return

            self._attr_is_on = from_dt <= utcnow() <= to_dt
            self._attr_extra_state_attributes.update(
                {
                    ATTR_PROTECTION_WINDOW_ENDING_TIME: as_local(to_dt),
                    ATTR_PROTECTION_WINDOW_ENDING_UV: data["to_uv"],
                    ATTR_PROTECTION_WINDOW_STARTING_UV: data["from_uv"],
                    ATTR_PROTECTION_WINDOW_STARTING_TIME: as_local(from_dt),
                }
            )
