"""Connected Wi-Fi device scanners for TP-Link Omada access points."""

from typing import Literal, override

from tplink_omada_client.clients import OmadaWirelessClient
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OmadaConfigEntry
from .config_flow import CONF_SITE
from .controller import OmadaClientsCoordinator
from .services import SERVICE_BLOCK, SERVICE_RECONNECT, SERVICE_UNBLOCK

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device trackers and scanners."""

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

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(SERVICE_RECONNECT, {}, "async_reconnect")
    platform.async_register_entity_service(SERVICE_BLOCK, {}, "async_block")
    platform.async_register_entity_service(SERVICE_UNBLOCK, {}, "async_unblock")


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

    async def _async_client_action(
        self, action: Literal["reconnect", "block", "unblock"]
    ) -> None:
        """Run an action for this client."""
        try:
            if action == "reconnect":
                await self.coordinator.omada_client.reconnect_client(self._client_id)
            elif action == "block":
                await self.coordinator.omada_client.block_client(self._client_id)
            elif action == "unblock":
                await self.coordinator.omada_client.unblock_client(self._client_id)
            else:
                raise ValueError(f"Unknown client action: {action}")
        except OmadaClientException as ex:
            raise HomeAssistantError(
                f"Failed to {action} client with MAC {self._client_id}"
            ) from ex

    async def async_reconnect(self) -> None:
        """Reconnect this wireless client."""
        await self._async_client_action("reconnect")

    async def async_block(self) -> None:
        """Block this client from the network."""
        await self._async_client_action("block")

    async def async_unblock(self) -> None:
        """Allow this client to access the network."""
        await self._async_client_action("unblock")

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
