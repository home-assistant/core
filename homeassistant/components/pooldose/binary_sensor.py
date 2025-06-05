"""Binary sensors for Pooldose integration."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BINARY_SENSOR_MAP, device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pooldose binary sensor entities from a config entry."""
    data = hass.data["pooldose"][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    serialnumber = entry.data["serialnumber"]
    device_info_dict = data.get("device_info", {})

    entities = []
    for uid, (
        translation_key,
        key,
        entity_category,
        device_class,
        enabled_by_default,
    ) in BINARY_SENSOR_MAP.items():
        entities.append(
            PooldoseBinarySensor(
                coordinator,
                api,
                translation_key,
                uid,
                key,
                serialnumber,
                entity_category,
                device_class,
                device_info_dict,
                enabled_by_default,
            )
        )
    async_add_entities(entities)


class PooldoseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor entity for Pooldose API."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        api,
        translation_key,
        uid,
        key,
        serialnumber,
        entity_category,
        device_class,
        device_info_dict,
        enabled_by_default: bool = True,
    ) -> None:
        """Initialize a PooldoseBinarySensor entity."""
        super().__init__(coordinator)
        self._api = api
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{serialnumber}_{key}"
        self._key = key
        self._attr_entity_category = entity_category
        self._attr_device_class = device_class
        self._attr_device_info = device_info(device_info_dict)
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        try:
            value = self.coordinator.data["devicedata"][self._api.serial_key][self._key]
            # Case 1: direct bool
            if isinstance(value, bool):
                return value
            # Case 2: dict with 'current' field
            if isinstance(value, dict) and "current" in value:
                # Example: "F" (False), "O" (On/True)
                return value["current"] == "F"
            return None  # noqa: TRY300
        except (KeyError, TypeError):
            return None
