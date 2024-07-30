"""Support for Lutron Caseta Occupancy/Vacancy Sensors."""

from pylutron_caseta import OCCUPANCY_GROUP_OCCUPIED

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import ATTR_SUGGESTED_AREA
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN as CASETA_DOMAIN, LutronCasetaDevice, _area_name_from_id
from .const import ACTION_PRESS, CONFIG_URL, DOMAIN, MANUFACTURER, UNASSIGNED_AREA
from .models import (
    LutronCasetaButtonActionData,
    LutronCasetaButtonDevice,
    LutronCasetaConfigEntry,
    LutronCasetaData,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronCasetaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta binary_sensor platform.

    Adds occupancy groups from the Caseta bridge associated with the
    config_entry as binary_sensor entities.
    """
    data = config_entry.runtime_data
    bridge = data.bridge
    occupancy_groups = bridge.occupancy_groups
    entities: list[BinarySensorEntity] = [
        LutronOccupancySensor(occupancy_group, data)
        for occupancy_group in occupancy_groups.values()
    ]
    entities.extend(
        LutronCasetaButtonBinarySensor(data, button_device, config_entry.entry_id)
        for button_device in data.button_devices
    )
    async_add_entities(entities)


class LutronOccupancySensor(LutronCasetaDevice, BinarySensorEntity):
    """Representation of a Lutron occupancy group."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, device, data):
        """Init an occupancy sensor."""
        super().__init__(device, data)
        area = _area_name_from_id(self._smartbridge.areas, device["area"])
        name = f"{area} {device['device_name']}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(CASETA_DOMAIN, self.unique_id)},
            manufacturer=MANUFACTURER,
            model="Lutron Occupancy",
            name=self.name,
            via_device=(CASETA_DOMAIN, self._bridge_device["serial"]),
            configuration_url=CONFIG_URL,
            entry_type=DeviceEntryType.SERVICE,
        )
        if area != UNASSIGNED_AREA:
            self._attr_device_info[ATTR_SUGGESTED_AREA] = area

    @property
    def is_on(self):
        """Return the brightness of the light."""
        return self._device["status"] == OCCUPANCY_GROUP_OCCUPIED

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._smartbridge.add_occupancy_subscriber(
            self.device_id, self.async_write_ha_state
        )

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["occupancy_group_id"]

    @property
    def unique_id(self):
        """Return a unique identifier."""
        return f"occupancygroup_{self._bridge_unique_id}_{self.device_id}"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"device_id": self.device_id}


class LutronCasetaButtonBinarySensor(LutronCasetaDevice, BinarySensorEntity):
    """Representation of a Lutron pico and keypad button action.

    Lutron buttons send a press and a release action which means
    they have a duration to the press action. Because they have
    a duration, they are represented as binary sensors and not events.
    """

    _attr_has_entity_name = True
    _attr_is_on = False

    def __init__(
        self,
        data: LutronCasetaData,
        button_device: LutronCasetaButtonDevice,
        entry_id: str,
    ) -> None:
        """Init a button binary_sensor entity."""
        super().__init__(button_device.device, data)
        self._attr_name = button_device.button_name
        self._attr_translation_key = button_device.button_key
        self._attr_device_info = button_device.parent_device_info
        self._button_id = button_device.button_id
        self._entry_id = entry_id

    @property
    def serial(self):
        """Buttons shouldn't have serial numbers, Return None."""
        return None

    @callback
    def _async_handle_button_action(self, data: LutronCasetaButtonActionData) -> None:
        """Handle a button event."""
        self._attr_is_on = data["action"] == ACTION_PRESS
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to button actions."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry_id}_button_{self._button_id}",
                self._async_handle_button_action,
            )
        )
        await super().async_added_to_hass()
