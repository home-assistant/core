"""Support for Netatmo binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Final, cast

from pyatmo.modules import Module
from pyatmo.modules.device_types import DeviceCategory as NetatmoDeviceCategory

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_URL_SECURITY,
    DOORTAG_CATEGORY_DOOR,
    DOORTAG_CATEGORY_FURNITURE,
    DOORTAG_CATEGORY_GARAGE,
    DOORTAG_CATEGORY_GATE,
    DOORTAG_CATEGORY_OTHER,
    DOORTAG_CATEGORY_WINDOW,
    DOORTAG_STATUS_CALIBRATING,
    DOORTAG_STATUS_CALIBRATION_FAILED,
    DOORTAG_STATUS_CLOSED,
    DOORTAG_STATUS_MAINTENANCE,
    DOORTAG_STATUS_NO_NEWS,
    DOORTAG_STATUS_OPEN,
    DOORTAG_STATUS_UNDEFINED,
    DOORTAG_STATUS_WEAK_SIGNAL,
    NETATMO_CREATE_BINARY_SENSOR,
    NETATMO_CREATE_WEATHER_BINARY_SENSOR,
)
from .data_handler import NetatmoDevice
from .entity import NetatmoModuleEntity, NetatmoWeatherModuleEntity

_LOGGER = logging.getLogger(__name__)


def process_opening_status_string(status: StateType) -> StateType | None:
    """Process opening status and return bool."""
    _LOGGER.debug(
        "Translated opening status: %s",
        status,
    )
    if status == DOORTAG_STATUS_NO_NEWS:
        return None
    if status == DOORTAG_STATUS_CALIBRATING:
        return None
    if status == DOORTAG_STATUS_UNDEFINED:
        return None
    if status == DOORTAG_STATUS_CLOSED:
        return False
    if status == DOORTAG_STATUS_OPEN:
        return True
    if status == DOORTAG_STATUS_CALIBRATION_FAILED:
        return None
    if status == DOORTAG_STATUS_MAINTENANCE:
        return None
    if status == DOORTAG_STATUS_WEAK_SIGNAL:
        return None
    return None


def process_opening_status(
    netatmo_device: Module, netatmo_name: str
) -> StateType | None:
    """Process opening Module status and return bool."""
    status = getattr(netatmo_device, netatmo_name)
    value = process_opening_status_string(status)

    _LOGGER.debug(
        "Opening status (%s) translating from '%s' to '%s' for module '%s'",
        netatmo_name,
        status,
        value,
        netatmo_device.name,
    )
    return value


def process_opening_category_string(
    category: StateType,
) -> BinarySensorDeviceClass | None:
    """Helper function to map Netatmo opening category to Home Assistant device class."""
    _LOGGER.debug(
        "Translated opening category: %s",
        category,
    )

    # Use a specific device class if we have a match
    if category == DOORTAG_CATEGORY_DOOR:
        return BinarySensorDeviceClass.DOOR
    if category == DOORTAG_CATEGORY_WINDOW:
        return BinarySensorDeviceClass.WINDOW
    if category == DOORTAG_CATEGORY_GARAGE:
        return BinarySensorDeviceClass.GARAGE_DOOR
    if category == DOORTAG_CATEGORY_GATE:
        return BinarySensorDeviceClass.OPENING
    if category == DOORTAG_CATEGORY_FURNITURE:
        return BinarySensorDeviceClass.OPENING
    if category == DOORTAG_CATEGORY_OTHER:
        return BinarySensorDeviceClass.OPENING
    return None


def get_opening_category(netatmo_device: NetatmoDevice) -> StateType | None:
    """Helper function to get opening category from Netatmo API raw data."""

    # First, get the unique ID of the device we are processing.
    device_id_to_find = netatmo_device.device.entity_id

    # Get the raw data containing the full list of homes and modules.
    raw_data = netatmo_device.data_handler.account.raw_data

    # Initialize category as None
    category: StateType = None

    # Iterate through each home in the raw data.
    for home in raw_data["homes"]:
        # Check if the modules list exists for the current home.
        if "modules" in home:
            # Iterate through each module to find a matching ID.
            for module in home["modules"]:
                if module["id"] == device_id_to_find:
                    # We found the matching device. Get its category.
                    if module.get("category") is not None:
                        category = module["category"]

    if category is not None:
        _LOGGER.debug(
            "Found category '%s' for device '%s'",
            category,
            netatmo_device.device.name,
        )
    else:
        _LOGGER.warning(
            "Category not found for device_id: %s in raw data",
            netatmo_device.device.name,
        )

    return category


def process_opening_category(netatmo_device: NetatmoDevice) -> BinarySensorDeviceClass:
    """Helper function to map Netatmo device opening category to Home Assistant device class."""
    category: StateType = get_opening_category(netatmo_device)
    module_binary_sensor_class: BinarySensorDeviceClass | None = (
        process_opening_category_string(category)
    )

    if module_binary_sensor_class is None:
        module_binary_sensor_class = BinarySensorDeviceClass.OPENING

    _LOGGER.debug(
        "Opening category translated from '%s' to '%s' for module '%s'",
        category,
        module_binary_sensor_class,
        netatmo_device.device.name,
    )

    return module_binary_sensor_class


DEVICE_CLASS_TRANSLATIONS: Final[dict[BinarySensorDeviceClass, str]] = {
    BinarySensorDeviceClass.OPENING: "Opening",
    BinarySensorDeviceClass.DOOR: "Door",
    BinarySensorDeviceClass.WINDOW: "Window",
    BinarySensorDeviceClass.GARAGE_DOOR: "Garage Door",
}


def process_opening_name(netatmo_device: NetatmoDevice) -> str:
    """Helper function to map Netatmo device opening category to Home Assistant device name."""
    category: StateType = get_opening_category(netatmo_device)
    module_binary_sensor_class: BinarySensorDeviceClass | None = (
        process_opening_category_string(category)
    )

    if module_binary_sensor_class is None:
        module_binary_sensor_class = BinarySensorDeviceClass.OPENING

    name = DEVICE_CLASS_TRANSLATIONS.get(module_binary_sensor_class, "Opening")
    _LOGGER.debug(
        "Opening name is '%s' for module '%s'",
        name,
        netatmo_device.device.name,
    )
    return name


@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo binary sensor entity."""

    key: str  # The key of the sensor
    name: str | None = None  # The default name of the sensor
    netatmo_name: str | None = (
        None  # The name used by Netatmo API for this sensor (exposed feature as attribute) if different than key
    )
    device_class_fn: Callable[[NetatmoDevice], BinarySensorDeviceClass] | None = (
        None  # This is a value_fn variant to calculate device_class
    )
    device_name_fn: Callable[[NetatmoDevice], str] | None = (
        None  # This is a value_fn variant to calculate name
    )
    value_fn: Callable[[StateType], StateType] = lambda x: x


NETATMO_WEATHER_BINARY_SENSOR_DESCRIPTIONS: Final[
    list[NetatmoBinarySensorEntityDescription]
] = [
    NetatmoBinarySensorEntityDescription(
        key="reachable",
        name="Connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
]

# Assuming a Module object with the following attributes:
# {'battery_level': 5780,
#  'battery_percent': None,
#  'battery_state': 'full',
#  'bridge': 'XX:XX:XX:XX:XX:XX',
#  'device_category': <DeviceCategory.opening: 'opening'>,
#  'device_type': <DeviceType.NACamDoorTag: 'NACamDoorTag'>,
#  'entity_id': 'NN:NN:NN:NN:NN:NN',
#  'features': {'status', 'battery', 'rf_strength', 'reachable'},
#  'firmware_name': None,
#  'firmware_revision': 58,
#  'history_features': set(),
#  'history_features_values': {},
#  'home': <pyatmo.home.Home object at 0x790e5c3ea660>,
#  'modules': None,
#  'name': 'YYYYYY',
#  'reachable': True,
#  'rf_strength': 74,
#  'room_id': '344597214',
#  'status': 'open'}

NETATMO_OPENING_BINARY_SENSOR_DESCRIPTIONS: Final[
    list[NetatmoBinarySensorEntityDescription]
] = [
    NetatmoBinarySensorEntityDescription(
        key="reachable",
        name="Connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    NetatmoBinarySensorEntityDescription(
        key="opening",
        name="Opening",
        device_class=BinarySensorDeviceClass.OPENING,
        netatmo_name="status",
        device_class_fn=process_opening_category,
        device_name_fn=process_opening_name,
        value_fn=process_opening_status_string,
    ),
]

DEVICE_CATEGORY_BINARY_URLS: Final[dict[NetatmoDeviceCategory, str]] = {
    NetatmoDeviceCategory.opening: CONF_URL_SECURITY,
}

DEVICE_CATEGORY_BINARY_SENSORS: Final[
    dict[NetatmoDeviceCategory, list[NetatmoBinarySensorEntityDescription]]
] = {
    NetatmoDeviceCategory.opening: NETATMO_OPENING_BINARY_SENSOR_DESCRIPTIONS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Netatmo weather binary sensors based on a config entry."""

    @callback
    def _create_weather_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        """Create weather binary sensor entities for a Netatmo weather device."""

        descriptions_to_add = NETATMO_WEATHER_BINARY_SENSOR_DESCRIPTIONS

        entities: list[NetatmoWeatherBinarySensor] = []

        # Create binary sensors for module
        for description in descriptions_to_add:
            # Actual check is simple for reachable
            feature_check = description.key
            if feature_check in netatmo_device.device.features:
                _LOGGER.debug(
                    'Adding "%s" weather binary sensor for device %s',
                    feature_check,
                    netatmo_device.device.name,
                )
                entities.append(
                    NetatmoWeatherBinarySensor(
                        netatmo_device,
                        description,
                    )
                )

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            NETATMO_CREATE_WEATHER_BINARY_SENSOR,
            _create_weather_binary_sensor_entity,
        )
    )

    @callback
    def _create_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        """Create binary sensor entities for a Netatmo device."""

        if netatmo_device.device.device_category is None:
            return

        descriptions_to_add = DEVICE_CATEGORY_BINARY_SENSORS.get(
            netatmo_device.device.device_category, []
        )

        entities: list[NetatmoBinarySensor] = []

        # Create binary sensors for module
        for description in descriptions_to_add:
            if description.netatmo_name is None:
                feature_check = description.key
            else:
                feature_check = description.netatmo_name
            if feature_check in netatmo_device.device.features:
                _LOGGER.debug(
                    'Adding "%s" (native: "%s") binary sensor for device %s',
                    description.name,
                    feature_check,
                    netatmo_device.device.name,
                )
                entities.append(
                    NetatmoBinarySensor(
                        netatmo_device,
                        description,
                    )
                )

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            NETATMO_CREATE_BINARY_SENSOR,
            _create_binary_sensor_entity,
        )
    )


class NetatmoWeatherBinarySensor(NetatmoWeatherModuleEntity, BinarySensorEntity):
    """Implementation of a Netatmo weather binary sensor."""

    entity_description: NetatmoBinarySensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize a Netatmo weather binary sensor."""

        super().__init__(netatmo_device)

        self.entity_description = description
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""

        value: StateType | None = None

        value = getattr(self.device, self.entity_description.key, None)

        if value is None:
            self._attr_available = False
            self._attr_is_on = False
        else:
            self._attr_available = True
            self._attr_is_on = cast(bool, value)

        self.async_write_ha_state()


class NetatmoBinarySensor(NetatmoModuleEntity, BinarySensorEntity):
    """Implementation of a Netatmo binary sensor."""

    entity_description: NetatmoBinarySensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize a Netatmo binary sensor."""

        # To prevent exception about missing URL we need to set it explicitly
        if netatmo_device.device.device_category is not None:
            if (
                DEVICE_CATEGORY_BINARY_URLS.get(netatmo_device.device.device_category)
                is not None
            ):
                self._attr_configuration_url = DEVICE_CATEGORY_BINARY_URLS[
                    netatmo_device.device.device_category
                ]

        super().__init__(netatmo_device)

        self.entity_description = description
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"
        if description.device_class_fn:
            self._attr_device_class = description.device_class_fn(netatmo_device)
        else:
            self._attr_device_class = description.device_class

        # Name override if function provided (e.g. more specific Door instead of generic Opening)
        if description.device_name_fn:
            self._attr_name = description.device_name_fn(netatmo_device)

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""

        raw_value: StateType | None = None
        value: StateType | None = None

        # First we check if device reachable. If not, we set available to False
        if not self.device.reachable:
            self._attr_available = False
            self._attr_is_on = None
            self.async_write_ha_state()
            return

        if self.entity_description.netatmo_name is None:
            raw_value = getattr(self.device, self.entity_description.key, None)
        else:
            raw_value = getattr(self.device, self.entity_description.netatmo_name, None)

        if raw_value is not None:
            value = self.entity_description.value_fn(raw_value)
        else:
            value = None

        if value is None:
            self._attr_available = False
            self._attr_is_on = False
        else:
            self._attr_available = True
            self._attr_is_on = cast(bool, value)

        self.async_write_ha_state()
