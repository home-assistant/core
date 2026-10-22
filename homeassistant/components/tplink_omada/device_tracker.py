"""Connected Wi-Fi device scanners for TP-Link Omada access points."""

from typing import override

from tplink_omada_client.clients import OmadaWirelessClient

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ScannerEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OmadaConfigEntry
from .config_flow import CONF_SITE
from .const import DOMAIN
from .coordinator import OmadaClientsCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device trackers and scanners."""

    controller = config_entry.runtime_data

    site_id = config_entry.data[CONF_SITE]
    known_clients_coordinator = controller.known_clients_coordinator

    added_unique_ids: set[str] = set()

    def _is_device_registered(mac: str) -> bool:
        """Return if a device with the client's MAC address is registered."""
        return bool(
            dr.async_get(hass).async_get_devices(
                connections={(dr.CONNECTION_NETWORK_MAC, mac)}
            )
        )

    def _reenable_if_device_known(unique_id: str, mac: str) -> bool:
        """Enable a tracker disabled by the integration when its device is known.

        Stale tracker cleanup removes the registry entry, and recreating it
        restores the saved integration disable. If another integration has
        registered a device with the client's MAC in the meantime, the scanner
        is enabled by default again, so drop the restored disable. User
        disables and disabled new entities are left alone.
        """
        entity_registry = er.async_get(hass)
        entity_id = entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, unique_id
        )
        if entity_id is None:
            deleted_entry = entity_registry.deleted_entities.get(
                (DEVICE_TRACKER_DOMAIN, DOMAIN, unique_id)
            )
            if deleted_entry is None:
                return False
            disabled_by = deleted_entry.disabled_by
        else:
            entity_entry = entity_registry.async_get(entity_id)
            disabled_by = entity_entry.disabled_by if entity_entry else None

        if disabled_by is not er.RegistryEntryDisabler.INTEGRATION:
            return False
        if config_entry.pref_disable_new_entities or not _is_device_registered(mac):
            return False

        if entity_id is None:
            # Recreate the entry so the restored disable can be cleared before
            # the entity platform adds the tracker.
            entity_id = entity_registry.async_get_or_create(
                DEVICE_TRACKER_DOMAIN, DOMAIN, unique_id, config_entry=config_entry
            ).entity_id
        entity_registry.async_update_entity(entity_id, disabled_by=None)
        return True

    def _should_add(unique_id: str, mac: str) -> bool:
        """Return if a tracker should be added by this platform run.

        Existing registry entries are submitted again, so the entity platform
        updates their metadata and, for disabled entries, still runs
        ``ScannerEntity.async_prepare_to_add_to_hass`` before skipping them.
        That registers the MAC address for automatic enabling when a matching
        device appears. Entries removed by stale tracker cleanup are created
        again when their client returns.
        """
        entity_registry = er.async_get(hass)
        enabled = _reenable_if_device_known(unique_id, mac)
        entity_id = entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, unique_id
        )
        if enabled or entity_id is None:
            # The tracker is created or enabled again in this run, so it is
            # added even if this platform run submitted it before.
            added_unique_ids.discard(unique_id)
        if unique_id in added_unique_ids:
            return False
        added_unique_ids.add(unique_id)
        return True

    def _new_trackers() -> list[OmadaClientScannerEntity]:
        """Return trackers for known clients that this platform has not added."""
        entities: list[OmadaClientScannerEntity] = []
        for client in (known_clients_coordinator.data or {}).values():
            unique_id = f"scanner_{site_id}_{client.mac}"
            if not _should_add(unique_id, client.mac):
                continue
            entities.append(
                OmadaClientScannerEntity(
                    site_id, client.mac, client.name, controller.clients_coordinator
                )
            )
        return entities

    @callback
    def _handle_known_clients_update() -> None:
        """Add trackers for clients that reappeared on the controller."""
        if entities := _new_trackers():
            async_add_entities(entities)

    config_entry.async_on_unload(
        known_clients_coordinator.async_add_listener(_handle_known_clients_update)
    )

    # Add all known WiFi devices as potentially tracked devices. They will only be
    # tracked if the user enables the entity.
    async_add_entities(_new_trackers())


class OmadaClientScannerEntity(
    CoordinatorEntity[OmadaClientsCoordinator], ScannerEntity
):
    """Entity for a client connected to the Omada network."""

    _attr_has_entity_name = True
    _client_details: OmadaWirelessClient | None = None

    def __init__(
        self,
        site_id: str,
        client_id: str,
        display_name: str,
        coordinator: OmadaClientsCoordinator,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(coordinator)
        self._site_id = site_id
        self._client_id = client_id
        self._attr_name = display_name

    def _do_update(self) -> None:
        self._client_details = self.coordinator.data.get(self._client_id)

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._do_update()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._do_update()
        self.async_write_ha_state()

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._client_details.ip if self._client_details else None

    @property
    @override
    def mac_address(self) -> str | None:
        """Return the mac address of the device."""
        return self._client_id

    @property
    @override
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self._client_details.host_name if self._client_details else None

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._client_details.is_active if self._client_details else False

    @property
    @override
    def unique_id(self) -> str | None:
        """Return the unique id of the device."""
        return f"scanner_{self._site_id}_{self._client_id}"
