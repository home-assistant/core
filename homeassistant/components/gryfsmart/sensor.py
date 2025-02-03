"""Handle the Gryf Smart light platform functionality."""

from pygryfsmart.device import _GryfDevice, _GryfInput, _GryfInputLine, _GryfOutputLine

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_API, CONF_DEVICES, CONF_ID, CONF_NAME, CONF_TYPE, DOMAIN
from .entity import GryfConfigFlowEntity, GryfYamlEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up the Sensor platform."""

    async_add_entities(
        [
            GryfYamlLine(
                _GryfInputLine(
                    "Gryf IN",
                    hass.data[DOMAIN][CONF_API],
                ),
                True,
            )
        ]
    )
    async_add_entities(
        [
            GryfYamlLine(
                _GryfOutputLine(
                    "Gryf OUT",
                    hass.data[DOMAIN][CONF_API],
                ),
                False,
            )
        ]
    )

    inputs = []

    for conf in hass.data[DOMAIN].get("input", {}):
        device = _GryfInput(
            conf.get(CONF_NAME),
            conf.get(CONF_ID) // 10,
            conf.get(CONF_ID) % 10,
            hass.data[DOMAIN][CONF_API],
        )
        inputs.append(GryfYamlInput(device))

    async_add_entities(inputs)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Config flow for Sensor platform."""
    async_add_entities(
        [
            GryfConfigFlowLine(
                _GryfInputLine(
                    "Gryf IN",
                    config_entry.runtime_data[CONF_API],
                ),
                config_entry,
                True,
            )
        ]
    )
    async_add_entities(
        [
            GryfConfigFlowLine(
                _GryfOutputLine(
                    "Gryf OUT",
                    config_entry.runtime_data[CONF_API],
                ),
                config_entry,
                False,
            )
        ]
    )

    inputs = []

    for conf in config_entry.data[CONF_DEVICES]:
        if conf.get(CONF_TYPE) == "input":
            device = _GryfInput(
                conf.get(CONF_NAME),
                conf.get(CONF_ID) // 10,
                conf.get(CONF_ID) % 10,
                config_entry.runtime_data[CONF_API],
            )
            inputs.append(GryfConfigFlowInput(device, config_entry))

    async_add_entities(inputs)


class _GryfLineSensorBase(SensorEntity):
    """Gryf line sensor base."""

    _state = ""
    _last_icon = False
    _attr_icon = "mdi:message-arrow-right-outline"
    _input: bool

    @property
    def native_value(self) -> str:
        """Return state."""
        return self._state

    async def async_update(self, state):
        """Update state."""

        self._state = state
        self._last_icon = not self._last_icon
        self.async_write_ha_state()

    @property
    def icon(self) -> str:
        """Property icon."""

        if self._input:
            return (
                "mdi:message-arrow-right-outline"
                if self._last_icon
                else "mdi:message-arrow-right"
            )
        return (
            "mdi:message-arrow-left-outline"
            if self._last_icon
            else "mdi:message-arrow-left"
        )


class GryfConfigFlowLine(GryfConfigFlowEntity, _GryfLineSensorBase):
    """Gryf Smart config flow input line class."""

    def __init__(
        self,
        device: _GryfDevice,
        config_entry: ConfigEntry,
        input: bool,
    ) -> None:
        """Init the gryf input line."""

        self._input = input
        super().__init__(config_entry, device)
        device.subscribe(self.async_update)


class GryfYamlLine(GryfYamlEntity, _GryfLineSensorBase):
    """Gryf Smart yaml input line class."""

    def __init__(self, device: _GryfDevice, input: bool) -> None:
        """Init the gryf input line."""

        self._input = input
        super().__init__(device)
        device.subscribe(self.async_update)


class _GryfInputSensorBase(SensorEntity):
    """Gryf smart input sensor Base."""

    _state = 0
    _device: _GryfDevice
    _attr_icon = "mdi:light-switch-off"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["0", "1", "2", "3"]

    async def async_update(self, data):
        """Update state."""

        self._state = data
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        """Property state."""

        return self._state

    @property
    def icon(self) -> str:
        """Property icon."""

        icon_mapper = {
            0: "mdi:light-switch-off",
            1: "mdi:light-switch",
            2: "mdi:gesture-tap",
            3: "mdi:gesture-tap-hold",
        }

        return icon_mapper[self._state]


class GryfConfigFlowInput(GryfConfigFlowEntity, _GryfInputSensorBase):
    """Gryf Smart config flow input line class."""

    def __init__(
        self,
        device: _GryfDevice,
        config_entry: ConfigEntry,
    ) -> None:
        """Init the gryf input line."""

        super().__init__(config_entry, device)
        device.subscribe(self.async_update)


class GryfYamlInput(GryfYamlEntity, _GryfInputSensorBase):
    """Gryf Smart config flow input line class."""

    def __init__(
        self,
        device: _GryfDevice,
    ) -> None:
        """Init the gryf input line."""

        super().__init__(device)
        device.subscribe(self.async_update)
