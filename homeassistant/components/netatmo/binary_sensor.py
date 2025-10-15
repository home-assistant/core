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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    ATTR_EVENT_TYPE,
    CONF_URL_ENERGY,
    CONF_URL_SECURITY,
    CONF_URL_WEATHER,
    DATA_DEVICE_IDS,
    DOMAIN,
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
    EVENT_TYPE_CAMERA_DISCONNECTION,
    EVENT_TYPE_DOOR_TAG_BIG_MOVE,
    EVENT_TYPE_DOOR_TAG_SMALL_MOVE,
    EVENT_TYPE_MODULE_CONNECT,
    EVENT_TYPE_MODULE_DISCONNECT,
    NETATMO_CREATE_BINARY_SENSOR,
    NETATMO_NAME_OPENING_STATUS,
)
from .data_handler import HOME, SIGNAL_NAME, NetatmoDevice
from .entity import NetatmoModuleEntity

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


def process_opening_status(module: Module, netatmo_name: str) -> StateType | None:
    """Process opening Module status and return bool."""
    status = getattr(module, netatmo_name)
    value = process_opening_status_string(status)

    _LOGGER.debug(
        "Opening status (%s) translating from '%s' to '%s' for module '%s'",
        netatmo_name,
        status,
        value,
        module.name,
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


# Assuming a Module object with the following attributes:
# {'battery_level': 5780,
#  'battery_percent': None,
#  'battery_state': 'full',
#  'bridge': '70:ee:50:31:5a:29',
#  'device_category': <DeviceCategory.opening: 'opening'>,
#  'device_type': <DeviceType.NACamDoorTag: 'NACamDoorTag'>,
#  'entity_id': '70:ee:50:61:1c:b1',
#  'features': {'status', 'battery', 'rf_strength', 'reachable'},
#  'firmware_name': None,
#  'firmware_revision': 58,
#  'history_features': set(),
#  'history_features_values': {},
#  'home': <pyatmo.home.Home object at 0x790e5c3ea660>,
#  'modules': None,
#  'name': 'A East Shade',
#  'reachable': True,
#  'rf_strength': 74,
#  'room_id': '344597214',
#  'status': 'open'}


@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo binary sensor entity."""

    device_class_fn: Callable[[NetatmoDevice], BinarySensorDeviceClass] | None = None
    netatmo_name: str  # The name used by Netatmo API for this sensor
    feature_name: str | None = None  # The feature key in the Module's features set
    value_fn: Callable[[StateType], StateType] = lambda x: x
    device_value_fn: Callable[[Module, str], StateType] | None = None


NETATMO_BINARY_SENSOR_DESCRIPTIONS: Final[
    list[NetatmoBinarySensorEntityDescription]
] = [
    NetatmoBinarySensorEntityDescription(
        key="reachable",
        translation_key="Reachability",
        netatmo_name="reachable",
        feature_name="reachable",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:signal",
    ),
]

OPENING_BINARY_SENSOR_DESCRIPTIONS: Final[
    list[NetatmoBinarySensorEntityDescription]
] = [
    NetatmoBinarySensorEntityDescription(
        key="opening",
        translation_key="Opening",
        device_class=BinarySensorDeviceClass.OPENING,
        netatmo_name="status",
        feature_name="status",
        device_value_fn=process_opening_status,
        device_class_fn=process_opening_category,
    ),
]

DEVICE_CATEGORY_BINARY_SENSORS: Final[
    dict[NetatmoDeviceCategory, list[NetatmoBinarySensorEntityDescription]]
] = {
    NetatmoDeviceCategory.opening: OPENING_BINARY_SENSOR_DESCRIPTIONS,
}

DEVICE_CATEGORY_BINARY_URLS: Final[dict[NetatmoDeviceCategory, str]] = {
    NetatmoDeviceCategory.opening: CONF_URL_SECURITY,
    NetatmoDeviceCategory.weather: CONF_URL_WEATHER,
    NetatmoDeviceCategory.climate: CONF_URL_ENERGY,
}

DEVICE_CLASS_TRANSLATIONS: Final[dict[BinarySensorDeviceClass, str]] = {
    BinarySensorDeviceClass.OPENING: "Opening",
    BinarySensorDeviceClass.DOOR: "Door",
    BinarySensorDeviceClass.WINDOW: "Window",
    BinarySensorDeviceClass.GARAGE_DOOR: "Garage Door",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Netatmo binary sensors based on a config entry."""

    @callback
    def _create_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        """Create new binary sensor entities."""

        if not isinstance(netatmo_device.device, Module):
            _LOGGER.debug(
                "Skipping device that is not a module: %s",
                netatmo_device.device.name,
            )
            return

        if netatmo_device.device.device_category is None:
            _LOGGER.warning(
                "Device %s is missing a device_category, cannot create binary sensors",
                netatmo_device.device.name,
            )
            return

        descriptions_to_add = (
            NETATMO_BINARY_SENSOR_DESCRIPTIONS
            + DEVICE_CATEGORY_BINARY_SENSORS.get(
                netatmo_device.device.device_category, []
            )
        )

        _LOGGER.debug(
            "Descriptions %s to add for module %s, features: %s",
            len(descriptions_to_add),
            netatmo_device.device.name,
            netatmo_device.device.features,
        )

        entities: list[NetatmoBinarySensor] = []

        # Create binary sensors for module
        for description in descriptions_to_add:
            if description.feature_name is None:
                feature_check = description.key
            else:
                feature_check = description.feature_name
            if feature_check in netatmo_device.device.features:
                _LOGGER.debug(
                    "Adding %s binary sensor for device %s",
                    feature_check,
                    netatmo_device.device.name,
                )
                entities.append(
                    NetatmoBinarySensor(
                        netatmo_device,
                        description,
                    )
                )
            else:
                _LOGGER.warning(
                    "Failed to add %s (%s) binary sensor for device %s",
                    feature_check,
                    description.netatmo_name,
                    netatmo_device.device.name,
                )

        if entities:
            _LOGGER.debug(
                "Adding %s entities for device %s",
                len(entities),
                netatmo_device.device.name,
            )
            async_add_entities(entities)
        else:
            _LOGGER.debug(
                "No binary sensor entities created for device %s",
                netatmo_device.device.name,
            )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_BINARY_SENSOR, _create_binary_sensor_entity
        )
    )


class NetatmoBinarySensor(NetatmoModuleEntity, BinarySensorEntity):
    """Implementation of a Netatmo binary sensor."""

    entity_description: NetatmoBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize a Netatmo binary sensor."""

        if not isinstance(netatmo_device.device, Module):
            return

        if description.device_class_fn:
            self._attr_device_class = description.device_class_fn(netatmo_device)
        else:
            self._attr_device_class = description.device_class
        if self._attr_device_class is None:
            return
        name_suffix = DEVICE_CLASS_TRANSLATIONS.get(self._attr_device_class)
        if not name_suffix:
            name_suffix = (
                description.translation_key
                if description.translation_key
                else description.key.replace("_", " ").title()
            )

        self._attr_unique_id = f"{netatmo_device.device.entity_id}-{description.key}"
        self._attr_name = name_suffix
        if netatmo_device.device.device_category:
            self._attr_configuration_url = DEVICE_CATEGORY_BINARY_URLS.get(
                netatmo_device.device.device_category, None
            )
        else:
            self._attr_configuration_url = None

        super().__init__(netatmo_device)
        self.entity_description = description

        publisher_name = HOME
        self._publishers.extend(
            [
                {
                    "name": publisher_name,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: netatmo_device.signal_name,
                },
            ]
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        if self.device.device_type == "NACamDoorTag":
            for event_type in (
                EVENT_TYPE_CAMERA_DISCONNECTION,
                EVENT_TYPE_DOOR_TAG_BIG_MOVE,
                EVENT_TYPE_DOOR_TAG_SMALL_MOVE,
                EVENT_TYPE_MODULE_CONNECT,
                EVENT_TYPE_MODULE_DISCONNECT,
            ):
                _LOGGER.debug(
                    "Subscribing to event %s for module %s",
                    event_type,
                    self.device.name,
                )
                self.async_on_remove(
                    async_dispatcher_connect(
                        self.hass,
                        f"signal-{DOMAIN}-webhook-{event_type}",
                        self.handle_event,
                    )
                )

        self.hass.data[DOMAIN][DATA_DEVICE_IDS][self.device.entity_id] = (
            self.device.name
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._attr_is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (self.device.reachable is True) and (
            getattr(self.device, self.entity_description.netatmo_name) is not None
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        value: StateType = None
        raw_value: StateType = None
        module = self.device

        if not module:
            return

        if not self.device.reachable:
            self._attr_available = False
            self._attr_is_on = None
            _LOGGER.debug(
                "Module %s is not reachable (%s), cannot update %s (%s) sensor",
                module.name,
                module.reachable,
                self.entity_description.key,
                self.entity_description.netatmo_name,
            )
            self.async_write_ha_state()
            return

        raw_value = cast(
            StateType, getattr(module, self.entity_description.netatmo_name, None)
        )

        if raw_value is not None:
            if self.entity_description.device_value_fn is None:
                value = self.entity_description.value_fn(raw_value)

                _LOGGER.debug(
                    "%s (%s) translated from '%s' to '%s' for module '%s'",
                    self.entity_description.translation_key,
                    self.entity_description.netatmo_name,
                    raw_value,
                    value,
                    module.name,
                )
            else:
                value = self.entity_description.device_value_fn(
                    module, self.entity_description.netatmo_name
                )
        else:
            _LOGGER.warning(
                "No value can be found for %s (%s) for module '%s'",
                self.entity_description.translation_key,
                self.entity_description.netatmo_name,
                module.name,
            )

        _LOGGER.debug(
            "Updating sensor '%s' for module '%s' with status: %s",
            self.entity_description.key,
            module.name,
            value,
        )

        if value is None:
            self._attr_available = False
            self._attr_is_on = False
        else:
            self._attr_available = True
            self._attr_is_on = cast(bool, value)

        self.async_write_ha_state()

    def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        data = event["data"]
        event_type = data.get(ATTR_EVENT_TYPE)

        if not event_type:
            _LOGGER.warning("Event has no type, returning")
            return

        if not data.get("device_id"):
            _LOGGER.warning("Event %s has no device ID, returning", event_type)
            return
        device_id = data["device_id"]
        module_id = device_id  # For safety, in case of direct module event

        if not data.get("home_id"):
            _LOGGER.warning(
                "Event %s for device %s has no home ID, returning",
                event_type,
                data["device_id"],
            )
            return
        home_id = data["home_id"]

        # Door tag related direct events (where we need module_id)
        if event_type in [
            EVENT_TYPE_MODULE_CONNECT,
            EVENT_TYPE_MODULE_DISCONNECT,
            EVENT_TYPE_DOOR_TAG_SMALL_MOVE,
            EVENT_TYPE_DOOR_TAG_BIG_MOVE,
        ]:
            if not data.get("module_id"):
                _LOGGER.warning("Event %s has no module ID, returning", event_type)
                return
            module_id = data["module_id"]

        if self.device.device_type == "NACamDoorTag":
            # Bridge related events (where we need device_id)
            if (
                home_id == self.home.entity_id
                and device_id == self.device.bridge
                and event_type in [EVENT_TYPE_CAMERA_DISCONNECTION]
            ):
                # Event for the bridge of this module
                if event_type in [EVENT_TYPE_CAMERA_DISCONNECTION]:
                    _LOGGER.debug(
                        "Bridge (camera) %s has disconnect event",
                        device_id,
                    )

                    if self.entity_description.key == "reachable":
                        self._attr_is_on = False
                    else:
                        self._attr_is_on = None
                    self._attr_available = False
                    setattr(
                        self.device,
                        NETATMO_NAME_OPENING_STATUS,
                        DOORTAG_STATUS_UNDEFINED,
                    )
                    self.device.reachable = False
                    _LOGGER.debug(
                        "Toggling %s binary sensor state to unavailable",
                        self.device.entity_id,
                    )
                    self.schedule_update_ha_state(True)
                else:
                    _LOGGER.warning(
                        "Binary sensor's bridge %s has received unexpected event as type %s",
                        device_id,
                        event_type,
                    )
            # Module related events (where we need module_id)
            elif home_id == self.home.entity_id and module_id == self.device.entity_id:
                # Event for this module
                if event_type in [
                    EVENT_TYPE_DOOR_TAG_SMALL_MOVE,
                    EVENT_TYPE_DOOR_TAG_BIG_MOVE,
                ]:
                    # Movement events for opening sensor only
                    if self.entity_description.key == "opening":
                        _LOGGER.debug(
                            "Module %s has detected %s event",
                            module_id,
                            event_type,
                        )

                        # Interpret as open event if closed only
                        if (
                            self.available
                            and self._attr_is_on is not None
                            and not self._attr_is_on
                        ):
                            self._attr_is_on = True
                            self._attr_available = True
                            setattr(
                                self.device,
                                NETATMO_NAME_OPENING_STATUS,
                                DOORTAG_STATUS_OPEN,
                            )
                            _LOGGER.debug(
                                "Toggling %s binary sensor state to open",
                                self.device.entity_id,
                            )
                            self.schedule_update_ha_state(True)
                        else:
                            _LOGGER.debug(
                                "Skipping event processing as binary sensor %s either unavailable/unknown state or already open (should be closed)",
                                self.device.entity_id,
                            )

                elif event_type in [EVENT_TYPE_MODULE_DISCONNECT]:
                    # Disconnection of module
                    _LOGGER.debug(
                        "Module %s has detected disconnect event",
                        module_id,
                    )

                    if self.entity_description.key == "reachable":
                        self._attr_is_on = False
                    else:
                        self._attr_is_on = None
                    self._attr_available = False
                    setattr(
                        self.device,
                        NETATMO_NAME_OPENING_STATUS,
                        DOORTAG_STATUS_UNDEFINED,
                    )
                    setattr(
                        self.device,
                        NETATMO_NAME_OPENING_STATUS,
                        DOORTAG_STATUS_UNDEFINED,
                    )
                    self.device.reachable = False
                    _LOGGER.debug(
                        "Toggling %s binary sensor state to unavailable",
                        self.device.entity_id,
                    )
                    self.schedule_update_ha_state(True)
                elif event_type in [EVENT_TYPE_MODULE_CONNECT]:
                    # Connection of module
                    _LOGGER.debug(
                        "Module %s has detected connect event",
                        module_id,
                    )

                    if self.entity_description.key == "reachable":
                        self._attr_is_on = True
                    else:
                        self._attr_is_on = None
                    self._attr_available = True
                    setattr(
                        self.device,
                        NETATMO_NAME_OPENING_STATUS,
                        DOORTAG_STATUS_UNDEFINED,
                    )
                    self.device.reachable = True
                    _LOGGER.debug(
                        "Toggling %s binary sensor state to available (%s = %s)",
                        self.device.entity_id,
                        self.entity_description.key,
                        self._attr_is_on,
                    )
                    self.schedule_update_ha_state(True)
                else:
                    _LOGGER.warning(
                        "Binary sensor %s has received unexpected event as type %s",
                        module_id,
                        event_type,
                    )
            else:
                _LOGGER.warning(
                    "Binary sensor %s of type %s has unexpectedly received event as type %s",
                    self.device.entity_id,
                    self.device.device_type,
                    event_type,
                )
        else:
            _LOGGER.warning(
                "Binary sensor %s of type %s has unexpectedly received any event as type %s",
                self.device.entity_id,
                self.device.device_type,
                event_type,
            )
        return
