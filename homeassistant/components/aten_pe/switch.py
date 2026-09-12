"""The ATEN PE switch component."""

from typing import Any

from atenpdu import AtenPE
import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchDeviceClass,
    SwitchEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import AtenPEConfigEntry
from .const import (
    CONF_AUTH_KEY,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
)

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_AUTH_KEY): cv.string,
        vol.Optional(CONF_PRIV_KEY): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import YAML configuration when available."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config)
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtenPEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ATEN PE switch."""
    data = entry.runtime_data

    switches = []
    if data.switchable:
        switches.extend(
            [
                AtenSwitch(
                    data.device, data.device_info, data.mac, outlet.id, outlet.name
                )
                async for outlet in data.device.outlets()
            ]
        )

    async_add_entities(switches, True)


class AtenSwitch(SwitchEntity):
    """Represents an ATEN PE switch."""

    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(
        self, device: AtenPE, info: DeviceInfo, mac: str, outlet: str | int, name: str
    ) -> None:
        """Initialize an ATEN PE switch."""
        self._device = device
        self._outlet = outlet
        self._attr_device_info = info
        self._attr_unique_id = f"{mac}-{outlet}"
        self._attr_name = name or f"Outlet {outlet}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._device.setOutletStatus(self._outlet, "on")
        self._attr_is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._device.setOutletStatus(self._outlet, "off")
        self._attr_is_on = False

    async def async_update(self) -> None:
        """Process update from entity."""
        status = await self._device.displayOutletStatus(self._outlet)
        if status == "on":
            self._attr_is_on = True
        elif status == "off":
            self._attr_is_on = False
