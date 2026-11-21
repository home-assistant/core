"""Demo platform that has some fake switches."""

from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .device import async_create_device


@dataclass(frozen=True, kw_only=True)
class DemoSwitchEntityDescription(SwitchEntityDescription):
    """Describes a demo switch."""

    device_name: str
    state: bool


POWER_STRIP_SWITCHES = (
    DemoSwitchEntityDescription(
        key="outlet_1", name=None, device_name="Outlet 1", state=False
    ),
    DemoSwitchEntityDescription(
        key="outlet_2", name=None, device_name="Outlet 2", state=True
    ),
)

HUB_SWITCHES = (
    DemoSwitchEntityDescription(
        key="hub_switch", name=None, device_name="Hub switch", state=False
    ),
)

HUB_POWER_STRIP_SWITCHES = (
    DemoSwitchEntityDescription(
        key="outlet_3", name=None, device_name="Outlet 3", state=False
    ),
    DemoSwitchEntityDescription(
        key="outlet_4", name=None, device_name="Outlet 4", state=True
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo switch platform."""
    async_create_device(
        hass,
        config_entry.entry_id,
        None,
        "n_ch_power_strip",
        {"number_of_sockets": "2"},
        "2_ch_power_strip",
    )

    parent_device_id = dr.async_get_device_id_by_identifier(
        hass, (DOMAIN, "2_ch_power_strip"), config_entry_id=config_entry.entry_id
    )

    # A hub with a switch device linked to it via its via device.
    hub = async_create_device(hass, config_entry.entry_id, "Hub", None, None, "hub")

    # A second hub with a power strip linked to it via its via device; the power
    # strip in turn has its own child devices (outlets).
    power_strip_hub = async_create_device(
        hass, config_entry.entry_id, "Power strip hub", None, None, "power_strip_hub"
    )
    power_strip_via_hub = async_create_device(
        hass,
        config_entry.entry_id,
        None,
        "n_ch_power_strip",
        {"number_of_sockets": "2"},
        "2_ch_power_strip_via_hub",
        via_device_id=power_strip_hub.id,
    )

    async_add_entities(
        [
            *(
                DemoSwitch(description, parent_device_id=parent_device_id)
                for description in POWER_STRIP_SWITCHES
            ),
            *(
                DemoSwitch(description, via_device_id=hub.id)
                for description in HUB_SWITCHES
            ),
            *(
                DemoSwitch(description, parent_device_id=power_strip_via_hub.id)
                for description in HUB_POWER_STRIP_SWITCHES
            ),
        ]
    )


class DemoSwitch(SwitchEntity):
    """Representation of a demo switch."""

    entity_description: DemoSwitchEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_info: DeviceInfo | ChildDeviceInfo

    def __init__(
        self,
        description: DemoSwitchEntityDescription,
        *,
        parent_device_id: str | None = None,
        via_device_id: str | None = None,
    ) -> None:
        """Initialize the Demo switch."""
        self.entity_description = description
        self._attr_is_on = description.state
        self._attr_unique_id = description.key
        if parent_device_id is not None:
            self._attr_device_info = ChildDeviceInfo(
                identifiers={(DOMAIN, description.key)},
                name=description.device_name,
                parent_device_id=parent_device_id,
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, description.key)},
                name=description.device_name,
            )
            if via_device_id is not None:
                self._attr_device_info.via_device_id = via_device_id

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._attr_is_on = True
        self.schedule_update_ha_state()

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._attr_is_on = False
        self.schedule_update_ha_state()
