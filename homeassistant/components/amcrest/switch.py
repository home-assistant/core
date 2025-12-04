"""Support for Amcrest Switches."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_SWITCHES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DATA_AMCREST, DEVICES
from .models import AmcrestConfiguredDevice

if TYPE_CHECKING:
    from .models import AmcrestDevice

PRIVACY_MODE_KEY = "privacy_mode"
MOTION_RECORDING_ENABLED_KEY = "motion_recording_enabled"
AUDIO_ENABLED_KEY = "audio_enabled"

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key=PRIVACY_MODE_KEY,
        name="Privacy Mode",
        icon="mdi:eye-off",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key=MOTION_RECORDING_ENABLED_KEY,
        name="Record on Motion",
        icon="mdi:record",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key=AUDIO_ENABLED_KEY,
        name="Audio Enabled",
        icon="mdi:microphone",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)

SWITCH_KEYS: list[str] = [desc.key for desc in SWITCH_TYPES]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up amcrest platform switches."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    switches = discovery_info[CONF_SWITCHES]
    async_add_entities(
        [
            AmcrestSwitch(name, device, description)
            for description in SWITCH_TYPES
            if description.key in switches
        ],
        True,
    )


# Platform setup for config flow
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Amcrest switches for a config entry."""
    device = config_entry.runtime_data.device
    coordinator = config_entry.runtime_data.coordinator
    entities = [
        AmcrestCoordinatedSwitch(device.name, device, coordinator, description)
        for description in SWITCH_TYPES
    ]
    async_add_entities(entities, True)


class AmcrestSwitch(SwitchEntity):
    """Representation of an Amcrest Camera Switch."""

    def __init__(
        self,
        name: str,
        device: AmcrestDevice,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize switch."""
        self._api = device.api
        self.entity_description = entity_description
        self._attr_name = f"{name} {entity_description.name}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._api.available

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_turn_switch(True)
        self._attr_is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_turn_switch(False)
        self._attr_is_on = False

    async def _async_turn_switch(self, mode: bool) -> None:
        """Set privacy mode."""
        key = self.entity_description.key
        if key == PRIVACY_MODE_KEY:
            await self._api.async_set_privacy(mode)
        elif key == MOTION_RECORDING_ENABLED_KEY:
            await self._api.async_set_motion_recording(mode)
        elif key == AUDIO_ENABLED_KEY:
            await self._api.async_set_audio_enabled(mode)

    async def async_update(self) -> None:
        """Update switch."""
        io_res = (await self._api.async_privacy_config()).splitlines()[0].split("=")[1]
        self._attr_is_on = io_res == "true"


class AmcrestCoordinatedSwitch(CoordinatorEntity, AmcrestSwitch):
    """Representation of an Amcrest Camera Switch tied to DataUpdateCoordinator."""

    def __init__(
        self,
        name: str,
        device: AmcrestConfiguredDevice,
        coordinator: DataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize switch."""
        CoordinatorEntity.__init__(self, coordinator)
        AmcrestSwitch.__init__(self, name, device, entity_description)
        self._attr_device_info = device.device_info
        # Use serial number for unique ID if available, otherwise fall back to device name
        identifier = device.serial_number if device.serial_number else device.name
        self._attr_unique_id = f"{identifier}_{entity_description.key}"

    async def async_update(self) -> None:
        """Update the switch state using coordinator data."""

        on_value = self.coordinator.data[self.entity_description.key]
        if on_value is not None:
            self._attr_is_on = on_value

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Use coordinator availability
        return self.coordinator.data is not None
