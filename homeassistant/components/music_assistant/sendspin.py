"""Link Music Assistant Sendspin players to their ESPHome devices."""

from typing import TYPE_CHECKING

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_when_setup

from .const import DOMAIN

if TYPE_CHECKING:
    from music_assistant_models.player import Player

    from . import MusicAssistantConfigEntry

_ESPHOME_DOMAIN = "esphome"


@callback
def async_setup_sendspin_links(hass: HomeAssistant) -> None:
    """Handle late Sendspin discovery and ESPHome area changes."""

    async def esphome_setup(hass: HomeAssistant, _component: str) -> None:
        from homeassistant.components.esphome import (  # noqa: PLC0415
            async_sendspin_client_ids,
            async_subscribe_sendspin_clients,
        )

        @callback
        def clients_changed(client_ids: list[str]) -> None:
            for entry in hass.config_entries.async_loaded_entries(DOMAIN):
                data = entry.runtime_data
                for client_id in client_ids:
                    if (
                        client_id in data.discovered_players
                        and (player := data.mass.players.get(client_id)) is not None
                    ):
                        async_link_sendspin_player(hass, entry, player)

        async_subscribe_sendspin_clients(hass, clients_changed)
        clients_changed(async_sendspin_client_ids(hass))

        registry = dr.async_get(hass)

        @callback
        def area_changed(event: Event[dr.EventDeviceRegistryUpdatedData]) -> None:
            if not isinstance(
                source := registry.async_get(event.data["device_id"]), dr.DeviceEntry
            ) or not _is_device_from(hass, source, _ESPHOME_DOMAIN):
                return
            # Only use connections already registered by an explicit client ID match.
            connections = {
                item
                for item in source.connections
                if item[0] == dr.CONNECTION_NETWORK_MAC
            }
            for device in registry.async_get_devices(connections=connections):
                if _is_device_from(hass, device, DOMAIN):
                    registry.async_update_device(device.id, area_id=source.area_id)

        @callback
        def is_area_update(event_data: dr.EventDeviceRegistryUpdatedData) -> bool:
            return (
                event_data["action"] == "update" and "area_id" in event_data["changes"]
            )

        hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, area_changed, event_filter=is_area_update
        )

    async_when_setup(hass, _ESPHOME_DOMAIN, esphome_setup)


@callback
def _is_device_from(hass: HomeAssistant, device: dr.DeviceEntry, domain: str) -> bool:
    entry = hass.config_entries.async_get_entry(device.config_entry_id)
    return entry is not None and entry.domain == domain


@callback
def async_link_sendspin_player(
    hass: HomeAssistant, entry: MusicAssistantConfigEntry, player: Player
) -> None:
    """Register a shared connection only for an explicit Sendspin client ID match."""
    if _ESPHOME_DOMAIN not in hass.config.components or (
        (provider := entry.runtime_data.mass.get_provider(player.provider)) is None
        or provider.domain != "sendspin"
    ):
        return

    from homeassistant.components.esphome import async_get_sendspin_device  # noqa: PLC0415

    if (satellite := async_get_sendspin_device(hass, player.player_id)) is None:
        return
    if (
        connection := next(
            (
                item
                for item in satellite.connections
                if item[0] == dr.CONNECTION_NETWORK_MAC
            ),
            None,
        )
    ) is None:
        return

    registry = dr.async_get(hass)
    identifier = (DOMAIN, player.player_id)
    device = registry.async_get_device_by_identifier(identifier, entry.entry_id)
    if (
        owner := registry.async_get_device_by_connection(connection, entry.entry_id)
    ) is not None and (device is None or owner.id != device.id):
        # Release the old link before registering the new one to keep both devices.
        registry.async_update_device(
            owner.id, new_connections=owner.connections - {connection}
        )

    if device is None:
        device = registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={identifier},
            connections={connection},
        )

    registry.async_update_device(
        device.id,
        new_connections={
            item for item in device.connections if item[0] != connection[0]
        }
        | {connection},
        area_id=satellite.area_id,
    )
