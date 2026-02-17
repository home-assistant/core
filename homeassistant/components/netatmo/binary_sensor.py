"""Support for Netatmo binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import logging
from typing import Any, Final, cast

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
    NETATMO_CREATE_CONNECTIVITY_BINARY_SENSOR,
    NETATMO_CREATE_OPENING_BINARY_SENSOR,
    NETATMO_CREATE_WEATHER_BINARY_SENSOR,
)
from .data_handler import SIGNAL_NAME, NetatmoDevice
from .entity import NetatmoModuleEntity, NetatmoWeatherModuleEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_OPENING_SENSOR_KEY = "opening_sensor"

OPENING_STATUS_TO_BINARY_SENSOR_STATE: Final[dict[str, bool | None]] = {
    DOORTAG_STATUS_NO_NEWS: None,
    DOORTAG_STATUS_CALIBRATING: None,
    DOORTAG_STATUS_UNDEFINED: None,
    DOORTAG_STATUS_CLOSED: False,
    DOORTAG_STATUS_OPEN: True,
    DOORTAG_STATUS_CALIBRATION_FAILED: None,
    DOORTAG_STATUS_MAINTENANCE: None,
    DOORTAG_STATUS_WEAK_SIGNAL: None,
}


OPENING_CATEGORY_TO_DEVICE_CLASS: Final[dict[str | None, BinarySensorDeviceClass]] = {
    DOORTAG_CATEGORY_DOOR: BinarySensorDeviceClass.DOOR,
    DOORTAG_CATEGORY_FURNITURE: BinarySensorDeviceClass.OPENING,
    DOORTAG_CATEGORY_GARAGE: BinarySensorDeviceClass.GARAGE_DOOR,
    DOORTAG_CATEGORY_GATE: BinarySensorDeviceClass.OPENING,
    DOORTAG_CATEGORY_OTHER: BinarySensorDeviceClass.OPENING,
    DOORTAG_CATEGORY_WINDOW: BinarySensorDeviceClass.WINDOW,
}


def get_opening_category(netatmo_device: NetatmoDevice) -> str:
    """Helper function to get opening category from Netatmo API raw data."""

    # Iterate through each home in the raw data.
    for home in netatmo_device.data_handler.account.raw_data["homes"]:
        # Check if the modules list exists for the current home.
        if "modules" in home:
            # Iterate through each module to find a matching ID.
            for module in home["modules"]:
                if module["id"] == netatmo_device.device.entity_id:
                    # We found the matching device. Get its category.
                    if module.get("category") is not None:
                        return cast(str, module["category"])
                    raise ValueError(
                        f"Device {netatmo_device.device.entity_id} found, "
                        "but 'category' is missing in raw data."
                    )

    raise ValueError(
        f"Device {netatmo_device.device.entity_id} not found in Netatmo raw data."
    )


OPENING_CATEGORY_TO_KEY: Final[dict[str, str | None]] = {
    DOORTAG_CATEGORY_DOOR: None,
    DOORTAG_CATEGORY_FURNITURE: DOORTAG_CATEGORY_FURNITURE,
    DOORTAG_CATEGORY_GARAGE: None,
    DOORTAG_CATEGORY_GATE: DOORTAG_CATEGORY_GATE,
    DOORTAG_CATEGORY_OTHER: DEFAULT_OPENING_SENSOR_KEY,
    DOORTAG_CATEGORY_WINDOW: None,
}


@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo binary sensor entity."""

    netatmo_name: str | None = (
        None  # The name used by Netatmo API for this sensor (exposed feature as attribute) if different than key
    )
    value_fn: Callable[[str], str | bool | None] = lambda x: x


NETATMO_CONNECTIVITY_BINARY_SENSOR_DESCRIPTIONS: Final[
    list[NetatmoBinarySensorEntityDescription]
] = [
    NetatmoBinarySensorEntityDescription(
        key="reachable",
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
#  'room_id': 'ZZZZZZZZ',
#  'status': 'open'}

NETATMO_OPENING_BINARY_SENSOR_DESCRIPTIONS: Final[
    list[NetatmoBinarySensorEntityDescription]
] = [
    NetatmoBinarySensorEntityDescription(
        key="opening",
        netatmo_name="status",
        value_fn=OPENING_STATUS_TO_BINARY_SENSOR_STATE.get,
    ),
]

DEVICE_CATEGORY_BINARY_URLS: Final[dict[NetatmoDeviceCategory, str]] = {
    NetatmoDeviceCategory.opening: CONF_URL_SECURITY,
}

DEVICE_CATEGORY_WEATHER_BINARY_SENSORS: Final[
    dict[NetatmoDeviceCategory, list[NetatmoBinarySensorEntityDescription]]
] = {
    NetatmoDeviceCategory.air_care: NETATMO_CONNECTIVITY_BINARY_SENSOR_DESCRIPTIONS,
    NetatmoDeviceCategory.weather: NETATMO_CONNECTIVITY_BINARY_SENSOR_DESCRIPTIONS,
}

DEVICE_CATEGORY_CONNECTIVITY_BINARY_SENSORS: Final[
    dict[NetatmoDeviceCategory, list[NetatmoBinarySensorEntityDescription]]
] = {
    NetatmoDeviceCategory.opening: NETATMO_CONNECTIVITY_BINARY_SENSOR_DESCRIPTIONS,
}

DEVICE_CATEGORY_OPENING_BINARY_SENSORS: Final[
    dict[NetatmoDeviceCategory, list[NetatmoBinarySensorEntityDescription]]
] = {
    NetatmoDeviceCategory.opening: NETATMO_OPENING_BINARY_SENSOR_DESCRIPTIONS,
}

DEVICE_CATEGORY_BINARY_PUBLISHERS: Final[list[NetatmoDeviceCategory]] = [
    NetatmoDeviceCategory.opening,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Netatmo weather binary sensors based on a config entry."""

    @callback
    def _create_binary_sensor_entity(
        binarySensorClass: type[
            NetatmoWeatherBinarySensor
            | NetatmoOpeningBinarySensor
            | NetatmoConnectivityBinarySensor
        ],
        descriptions: dict[
            NetatmoDeviceCategory, list[NetatmoBinarySensorEntityDescription]
        ],
        netatmo_device: NetatmoDevice,
    ) -> None:
        """Create binary sensor entities for a Netatmo device."""

        if netatmo_device.device.device_category is None:
            return

        descriptions_to_add = descriptions.get(
            netatmo_device.device.device_category, []
        )

        entities: list[
            NetatmoWeatherBinarySensor
            | NetatmoOpeningBinarySensor
            | NetatmoConnectivityBinarySensor
        ] = []

        # Create binary sensors for module
        for description in descriptions_to_add:
            if description.netatmo_name is None:
                feature_check = description.key
            else:
                feature_check = description.netatmo_name
            if feature_check in netatmo_device.device.features:
                _LOGGER.debug(
                    'Adding "%s" (native: "%s") binary sensor for device %s',
                    description.key,
                    feature_check,
                    netatmo_device.device.name,
                )
                entities.append(
                    binarySensorClass(
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
            partial(
                _create_binary_sensor_entity,
                NetatmoWeatherBinarySensor,
                DEVICE_CATEGORY_WEATHER_BINARY_SENSORS,
            ),
        )
    )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            NETATMO_CREATE_OPENING_BINARY_SENSOR,
            partial(
                _create_binary_sensor_entity,
                NetatmoOpeningBinarySensor,
                DEVICE_CATEGORY_OPENING_BINARY_SENSORS,
            ),
        )
    )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            NETATMO_CREATE_CONNECTIVITY_BINARY_SENSOR,
            partial(
                _create_binary_sensor_entity,
                NetatmoConnectivityBinarySensor,
                DEVICE_CATEGORY_CONNECTIVITY_BINARY_SENSORS,
            ),
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
        **kwargs: Any,  # Add this to capture extra args from super()
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

        super().__init__(netatmo_device, **kwargs)

        self.entity_description = description
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"

        # Register publishers for the entity if needed (not already done in parent class - weather and air_care)
        # We need to keep this here because we have two classes depending on it and we want to avoid adding publishers for all binary sensors
        if self.device.device_category in DEVICE_CATEGORY_BINARY_PUBLISHERS:
            self._publishers.extend(
                [
                    {
                        "name": self.home.entity_id,
                        "home_id": self.home.entity_id,
                        SIGNAL_NAME: netatmo_device.signal_name,
                    },
                ]
            )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""

        # Should be the connectivity (reachable) sensor only here as we have update for opening in its class

        # Setting reachable sensor, so we just get it directly (backward compatibility to weather binary sensor)
        value = getattr(self.device, self.entity_description.key, None)

        if value is None:
            self._attr_available = False
            self._attr_is_on = False
        else:
            self._attr_available = True
            self._attr_is_on = cast(bool, value)
        self.async_write_ha_state()


class NetatmoWeatherBinarySensor(NetatmoWeatherModuleEntity, NetatmoBinarySensor):
    """Implementation of a Netatmo weather binary sensor."""

    entity_description: NetatmoBinarySensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize a Netatmo weather binary sensor."""

        super().__init__(netatmo_device, description=description)


class NetatmoOpeningBinarySensor(NetatmoBinarySensor):
    """Implementation of a Netatmo opening binary sensor."""

    entity_description: NetatmoBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize a Netatmo binary sensor."""

        super().__init__(netatmo_device, description)

        # Apply Dynamic Device Class override
        self._attr_device_class = OPENING_CATEGORY_TO_DEVICE_CLASS.get(
            get_opening_category(netatmo_device), BinarySensorDeviceClass.OPENING
        )

        # Apply Dynamic Translation Key override if needed
        translation_key = OPENING_CATEGORY_TO_KEY.get(
            get_opening_category(netatmo_device), DEFAULT_OPENING_SENSOR_KEY
        )
        if translation_key is not None:
            self._attr_translation_key = translation_key

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""

        if not self.device.reachable:
            # If reachable is None or False we set availability to False
            self._attr_available = False
            self._attr_is_on = None

        else:
            # If reachable is True, we get the actual value
            if self.entity_description.netatmo_name is None:
                raw_value = getattr(self.device, self.entity_description.key, None)
            else:
                raw_value = getattr(
                    self.device, self.entity_description.netatmo_name, None
                )

            if raw_value is not None:
                value = self.entity_description.value_fn(raw_value)
            else:
                value = None

            # Set sensor state
            self._attr_available = True
            self._attr_is_on = cast(bool, value) if value is not None else None

        self.async_write_ha_state()


class NetatmoConnectivityBinarySensor(NetatmoBinarySensor):
    """Implementation of a Netatmo connectivity binary sensor."""

    entity_description: NetatmoBinarySensorEntityDescription
    _attr_has_entity_name = True
