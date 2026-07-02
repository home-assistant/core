"""The Duco integration."""

import logging
import re

from duco_connectivity import DucoClient, PatchConfigNodeStruct, PatchConfigNodeValue
from duco_connectivity.exceptions import DucoError

from homeassistant.const import CONF_HOST
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import EventDeviceRegistryUpdatedData

from .const import PLATFORMS
from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import get_duco_node_id, get_duco_node_identifiers

_REMOVED_SENSOR_RE = re.compile(r"_\d+_(box_)?temperature$")
_LOGGER = logging.getLogger(__name__)


@callback
def _async_clear_node_name_override(
    hass: HomeAssistant, device_id: str, name: str
) -> None:
    """Clear a transient HA rename override when it matches the attempted name."""
    device_registry = dr.async_get(hass)
    if (
        device := device_registry.async_get(device_id)
    ) is not None and device.name_by_user == name:
        device_registry.async_update_device(device.id, name_by_user=None)


async def _async_set_node_name(
    hass: HomeAssistant,
    coordinator: DucoCoordinator,
    device_id: str,
    node_id: int,
    name: str,
) -> None:
    """Write a renamed node back to the Duco box and refresh state."""
    try:
        await coordinator.client.async_set_node_config(
            node_id,
            PatchConfigNodeStruct(name=PatchConfigNodeValue(name)),
        )
    except DucoError:
        _async_clear_node_name_override(hass, device_id, name)
        _LOGGER.warning("Could not update Duco node name for node %s", node_id)
        return

    await coordinator.async_refresh()
    # Clear the HA-only override after a successful device rename so later
    # Duco-side name changes remain visible in Home Assistant.
    _async_clear_node_name_override(hass, device_id, name)


async def async_setup_entry(hass: HomeAssistant, entry: DucoConfigEntry) -> bool:
    """Set up Duco from a config entry."""
    # Clean up stale temperature registry entries so removed entities from the
    # python-duco-connectivity migration do not linger after upgrade.
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if _REMOVED_SENSOR_RE.search(entity_entry.unique_id):
            entity_registry.async_remove(entity_entry.entity_id)

    client = DucoClient(
        session=async_get_clientsession(hass),
        host=entry.data[CONF_HOST],
    )

    coordinator = DucoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    device_registry = dr.async_get(hass)
    mac = coordinator.mac

    @callback
    def _async_sync_node_names(updated_node_names: dict[int, str]) -> None:
        """Keep device registry names aligned with Duco node names."""
        for node_id, node_name in updated_node_names.items():
            if (
                device := device_registry.async_get_device(
                    identifiers=get_duco_node_identifiers(mac, node_id)
                )
            ) is None:
                continue

            if device.name != node_name:
                device_registry.async_update_device(device.id, name=node_name)

    @callback
    def _async_handle_device_registry_updated(
        event: Event[EventDeviceRegistryUpdatedData],
    ) -> None:
        """Write HA device renames back to the Duco API."""
        if (
            event.data["action"] != "update"
            or "name_by_user" not in event.data["changes"]
        ):
            return

        if (device := device_registry.async_get(event.data["device_id"])) is None:
            return

        if entry.entry_id not in device.config_entries:
            return

        if (node_id := get_duco_node_id(device, mac)) is None:
            return

        if not (new_name := device.name_by_user):
            return

        entry.async_create_background_task(
            hass,
            _async_set_node_name(hass, coordinator, device.id, node_id, new_name),
            name=f"duco set node name {node_id}",
        )

    entry.async_on_unload(
        coordinator.async_add_node_name_listener(_async_sync_node_names)
    )
    entry.async_on_unload(
        hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
            _async_handle_device_registry_updated,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DucoConfigEntry) -> bool:
    """Unload a Duco config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
