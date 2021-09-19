"""Switch support for the Skybell HD Doorbell."""
from __future__ import annotations

from skybellpy.device import SkybellDevice
import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import SkybellEntity
from .const import DATA_COORDINATOR, DATA_DEVICES, DOMAIN

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="do_not_disturb",
        name="Do Not Disturb",
    ),
    SwitchEntityDescription(
        key="motion_sensor",
        name="Motion Sensor",
    ),
)

# Deprecated in Home Assistant 2021.10
PLATFORM_SCHEMA = cv.deprecated(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Optional(CONF_ENTITY_NAMESPACE, default=DOMAIN): cv.string,
                vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
                    cv.ensure_list, [vol.In(SWITCH_TYPES)]
                ),
            }
        )
    )
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SkyBell switch."""
    skybell = hass.data[DOMAIN][entry.entry_id]
    switches = []
    for switch in SWITCH_TYPES:
        for device in skybell[DATA_DEVICES]:
            switches.append(
                SkybellSwitch(
                    skybell[DATA_COORDINATOR],
                    device,
                    switch,
                    entry.entry_id,
                )
            )

    switches = [
        SkybellSwitch(skybell[DATA_COORDINATOR], device, description, entry.entry_id)
        for device in skybell[DATA_DEVICES]
        for description in SWITCH_TYPES
    ]

    async_add_entities(switches, True)


class SkybellSwitch(SkybellEntity, SwitchEntity):
    """A switch implementation for Skybell devices."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: SkybellDevice,
        description: SwitchEntityDescription,
        server_unique_id: str,
    ) -> None:
        """Initialize a light for a Skybell device."""
        super().__init__(coordinator, device, description, server_unique_id)
        self.entity_description = description
        self._attr_name = f"{device.name} {description.name}"
        self._attr_unique_id = f"{server_unique_id}/{description.key}"

    def turn_on(self, **kwargs) -> None:
        """Turn on the switch."""
        setattr(self._device, self.entity_description.key, True)

    def turn_off(self, **kwargs) -> None:
        """Turn off the switch."""
        setattr(self._device, self.entity_description.key, False)

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        return getattr(self._device, self.entity_description.key)
