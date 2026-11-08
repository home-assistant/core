"""Connected Wi-Fi device scanners for TP-Link Omada access points."""

from typing import override

from tplink_omada_client.clients import OmadaWirelessClient

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OmadaConfigEntry
from .config_flow import CONF_SITE
from .const import CONF_SHOW_ONLY_ADOPTED_DEVICES, DOMAIN
from .coordinator import OmadaClientsCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device trackers and scanners."""

    if config_entry.options.get(CONF_SHOW_ONLY_ADOPTED_DEVICES, False):
        _detach_client_trackers(hass, config_entry)
        return

    controller = config_entry.runtime_data

    site_id = config_entry.data[CONF_SITE]

    # Add all known WiFi devices as potentially tracked devices. They will only be
    # tracked if the user enables the entity.
    async_add_entities(
        [
            OmadaClientScannerEntity(
                site_id, client.mac, client.name, controller.clients_coordinator
            )
            async for client in controller.omada_client.get_known_clients()
            if isinstance(client, OmadaWirelessClient)
        ]
    )


@callback
def _detach_client_trackers(hass: HomeAssistant, entry: OmadaConfigEntry) -> None:
    """Remove client-only devices while preserving tracker settings."""
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    client_device_ids = set()
    for entity in er.async_entries_for_config_entry(entities, entry.entry_id):
        if (
            entity.domain == "device_tracker"
            and entity.platform == DOMAIN
            and entity.unique_id.startswith(f"scanner_{entry.data[CONF_SITE]}_")
            and entity.device_id is not None
        ):
            client_device_ids.add(entity.device_id)
            entities.async_update_entity(entity.entity_id, device_id=None)

    for device_id in client_device_ids:
        if (
            (device := devices.async_get(device_id)) is not None
            and device.config_entry_id == entry.entry_id
            and not device.identifiers
            and not er.async_entries_for_device(
                entities, device_id, include_disabled_entities=True
            )
        ):
            devices.async_remove_device(device_id)


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
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, client_id)}, name=display_name
        )

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
