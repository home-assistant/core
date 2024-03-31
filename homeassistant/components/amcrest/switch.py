"""Support for Amcrest Switches."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import CONF_NAME, CONF_SWITCHES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DATA_AMCREST, DEVICES

if TYPE_CHECKING:
    from . import AmcrestDevice

PRIVACY_MODE_KEY = "privacy_mode"

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key=PRIVACY_MODE_KEY,
        name="Privacy Mode",
        icon="mdi:eye-off",
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

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_turn_switch(False)

    async def _async_turn_switch(self, mode: bool) -> None:
        """Set privacy mode."""
        lower_str = str(mode).lower()
        await self._api.async_command(
            f"configManager.cgi?action=setConfig&LeLensMask[0].Enable={lower_str}"
        )

    async def async_update(self) -> None:
        """Update switch."""
        io_res = (await self._api.async_privacy_config()).splitlines()[0].split("=")[1]
        self._attr_is_on = io_res == "true"
