"""Handle Home Assistant Devices for the KNX integration."""

from typing import TYPE_CHECKING

from xknx import XKNX
from xknx.core import XknxConnectionState
from xknx.io.gateway_scanner import GatewayDescriptor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import Undefined
from homeassistant.util.ulid import ulid_now

from .const import DOMAIN, UI_DEVICE_ID_PREFIX

if TYPE_CHECKING:
    from .knx_module import KNXModule


@callback
def async_create_ui_device(
    hass: HomeAssistant, entry: ConfigEntry, name: str, area_id: str | None = None
) -> dr.DeviceEntry:
    """Create a device UI entities can be assigned to.

    Raise ValueError if the area does not exist.
    """
    if area_id and ar.async_get(hass).async_get_area(area_id) is None:
        raise ValueError(f"Area {area_id} not found")
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        manufacturer="KNX",
        name=name,
        identifiers={(DOMAIN, f"{UI_DEVICE_ID_PREFIX}{ulid_now()}")},
    )
    updated = device_registry.async_update_device(
        device.id,
        area_id=area_id or Undefined,
        configuration_url=f"homeassistant://knx/entities/view?device_id={device.id}",
    )
    if TYPE_CHECKING:
        assert updated is not None
    return updated


async def async_remove_ui_entities_of_device(
    hass: HomeAssistant, knx_module: KNXModule, device_entry: dr.AnyDeviceEntry
) -> bool:
    """Remove the UI entities of a device so that the device can be removed.

    Return False - without removing anything - if the device has to stay.
    """
    if device_entry.id == knx_module.interface_device.device.id:
        # can not remove interface device
        return False
    ui_unique_ids = knx_module.config_store.get_entity_uids()
    entity_registry = er.async_get(hass)
    if any(
        entity.config_entry_id == knx_module.entry.entry_id
        and entity.unique_id not in ui_unique_ids
        for entity in er.async_entries_for_device(entity_registry, device_entry.id)
    ):
        # device still has YAML-configured KNX entities; it would be recreated after reload
        return False
    for entity in knx_module.config_store.get_entity_entries():
        if entity.device_id == device_entry.id:
            await knx_module.config_store.delete_entity(entity.entity_id)
    return True


class KNXInterfaceDevice:
    """Class for KNX Interface Device handling."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, xknx: XKNX) -> None:
        """Initialize interface device class."""
        self.hass = hass
        self.device_registry = dr.async_get(hass)
        self.gateway_descriptor: GatewayDescriptor | None = None
        self.xknx = xknx

        _device_id = (DOMAIN, f"_{entry.entry_id}_interface")
        self.device = self.device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            name="KNX Interface",
            identifiers={_device_id},
        )
        self.device_info = DeviceInfo(identifiers={_device_id})

        self.xknx.connection_manager.register_connection_state_changed_cb(
            self.connection_state_changed_cb
        )

    async def update(self) -> None:
        """Update interface properties on new connection."""
        self.gateway_descriptor = await self.xknx.knxip_interface.gateway_info()

        self.device_registry.async_update_device(
            device_id=self.device.id,
            model=str(self.gateway_descriptor.name)
            if self.gateway_descriptor
            else None,
        )

    def connection_state_changed_cb(self, state: XknxConnectionState) -> None:
        """Call invoked after a KNX connection state change was received."""
        if state is XknxConnectionState.CONNECTED:
            self.hass.async_create_task(self.update())
