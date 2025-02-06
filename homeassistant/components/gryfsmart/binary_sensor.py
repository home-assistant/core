"""Handle the Gryf Smart binary sensor platform functionality."""

from pygryfsmart.device import _GryfDevice, _GryfInput

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_API,
    CONF_DEVICE_CLASS,
    CONF_DEVICES,
    CONF_EXTRA,
    CONF_ID,
    CONF_NAME,
    CONF_TYPE,
    DOMAIN,
    PLATFORM_BINARY_SENSOR,
)
from .entity import GryfConfigFlowEntity, GryfYamlEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discoveryInfo: DiscoveryInfoType | None,
) -> None:
    """Set up the binary sensor platform."""

    binary_sensors = []

    for conf in hass.data[DOMAIN].get(PLATFORM_BINARY_SENSOR, {}):
        device = _GryfInput(
            conf.get(CONF_NAME),
            conf.get(CONF_ID) // 10,
            conf.get(CONF_ID) % 10,
            hass.data[DOMAIN][CONF_API],
        )
        binary_sensors.append(GryfYamlBinarySensor(device, conf.get(CONF_DEVICE_CLASS)))

    async_add_entities(binary_sensors)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Config flow for binary sensor platform."""

    binary_sensors = []

    for conf in config_entry.data[CONF_DEVICES]:
        if conf.get(CONF_TYPE) == Platform.BINARY_SENSOR:
            device = _GryfInput(
                conf.get(CONF_NAME),
                conf.get(CONF_ID) // 10,
                conf.get(CONF_ID) % 10,
                config_entry.runtime_data[CONF_API],
            )
            binary_sensors.append(
                GryfConfigFlowBinarySensor(
                    device,
                    config_entry,
                    conf.get(CONF_EXTRA),
                )
            )

    async_add_entities(binary_sensors)


class _GryfBinarySensorBase(BinarySensorEntity):
    """Gryf Binary Sensor base."""

    _is_on = False
    _attr_device_class = BinarySensorDeviceClass.OPENING

    @property
    def is_on(self) -> bool:
        return not self._is_on

    async def async_update(self, state):
        if state in [0, 1]:
            self._is_on = state
            self.async_write_ha_state()


class GryfConfigFlowBinarySensor(GryfConfigFlowEntity, _GryfBinarySensorBase):
    """Gryf Smart config flow binary sensor class."""

    def __init__(
        self,
        device: _GryfDevice,
        config_entry: ConfigEntry,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        """Init the gryf binary sensor."""

        super().__init__(config_entry, device)
        device.subscribe(self.async_update)

        if device_class:
            self._attr_device_class = device_class


class GryfYamlBinarySensor(GryfYamlEntity, _GryfBinarySensorBase):
    """Gryf Smart yaml input line class."""

    def __init__(
        self,
        device: _GryfDevice,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        """Init the gryf input line."""

        super().__init__(device)
        device.subscribe(self.async_update)

        if device_class:
            self._attr_device_class = device_class
