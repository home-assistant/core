"""Demo platform that has some fake switches."""

from typing import Any, override

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN
from .device import async_create_device


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
            DemoSwitch(
                unique_id="outlet_1",
                device_name="Outlet 1",
                entity_name=None,
                state=False,
                assumed=False,
                parent_device_id=parent_device_id,
            ),
            DemoSwitch(
                unique_id="outlet_2",
                device_name="Outlet 2",
                entity_name=None,
                state=True,
                assumed=False,
                parent_device_id=parent_device_id,
            ),
            DemoSwitch(
                unique_id="hub_switch",
                device_name="Hub switch",
                entity_name=None,
                state=False,
                assumed=False,
                via_device_id=hub.id,
            ),
            DemoSwitch(
                unique_id="outlet_3",
                device_name="Outlet 3",
                entity_name=None,
                state=False,
                assumed=False,
                parent_device_id=power_strip_via_hub.id,
            ),
            DemoSwitch(
                unique_id="outlet_4",
                device_name="Outlet 4",
                entity_name=None,
                state=True,
                assumed=False,
                parent_device_id=power_strip_via_hub.id,
            ),
        ]
    )


class DemoSwitch(SwitchEntity):
    """Representation of a demo switch."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_info: DeviceInfo | ChildDeviceInfo

    def __init__(
        self,
        *,
        unique_id: str,
        device_name: str,
        entity_name: str | None,
        state: bool,
        assumed: bool,
        translation_key: str | None = None,
        device_class: SwitchDeviceClass | None = None,
        parent_device_id: str | None = None,
        via_device_id: str | None = None,
    ) -> None:
        """Initialize the Demo switch."""
        self._attr_assumed_state = assumed
        self._attr_device_class = device_class
        self._attr_translation_key = translation_key
        self._attr_is_on = state
        self._attr_unique_id = unique_id
        if parent_device_id is not None:
            self._attr_device_info = ChildDeviceInfo(
                identifiers={(DOMAIN, unique_id)},
                name=device_name,
                parent_device_id=parent_device_id,
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, unique_id)},
                name=device_name,
            )
            if via_device_id is not None:
                self._attr_device_info["via_device_id"] = via_device_id
        self._attr_name = entity_name

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
