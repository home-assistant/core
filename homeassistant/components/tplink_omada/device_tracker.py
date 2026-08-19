"""Connected Wi-Fi device scanners for TP-Link Omada access points."""

from typing import Literal, cast, override

from tplink_omada_client.clients import OmadaWirelessClient
from tplink_omada_client.exceptions import OmadaClientException
import voluptuous as vol

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .config_flow import CONF_SITE
from .const import DOMAIN
from .controller import OmadaClientsCoordinator, OmadaSiteController

PARALLEL_UPDATES = 0

SERVICE_RECONNECT_CLIENT = "reconnect_client"
SERVICE_RECONNECT = "reconnect"
SERVICE_BLOCK = "block"
SERVICE_UNBLOCK = "unblock"

ATTR_MAC = "mac"

SERVICE_ACTIONS: dict[str, Literal["reconnect", "block", "unblock"]] = {
    SERVICE_RECONNECT_CLIENT: "reconnect",
    SERVICE_RECONNECT: "reconnect",
    SERVICE_BLOCK: "block",
    SERVICE_UNBLOCK: "unblock",
}


def _get_controller(call: ServiceCall) -> OmadaSiteController:
    if call.data.get(ATTR_CONFIG_ENTRY_ID):
        entry = call.hass.config_entries.async_get_entry(
            call.data[ATTR_CONFIG_ENTRY_ID]
        )
        if not entry:
            raise ServiceValidationError("Specified TP-Link Omada controller not found")
    else:
        # Assume first loaded entry if none specified
        # (for backward compatibility/99% use case)
        entries = call.hass.config_entries.async_entries(DOMAIN)
        if len(entries) == 0:
            raise ServiceValidationError("No active TP-Link Omada controllers found")
        entry = entries[0]

    entry = cast(ConfigEntry[OmadaSiteController], entry)

    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            "The TP-Link Omada integration is not currently available"
        )
    return entry.runtime_data


SCHEMA_RECONNECT_CLIENT = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        vol.Required(ATTR_MAC): cv.string,
    }
)


async def _handle_client_action(call: ServiceCall) -> None:
    """Handle a service action for a network client."""
    controller = _get_controller(call)
    mac: str = call.data[ATTR_MAC]
    action = SERVICE_ACTIONS[call.service]

    try:
        if action == "reconnect":
            await controller.omada_client.reconnect_client(mac)
        elif action == "block":
            await controller.omada_client.block_client(mac)
        else:
            await controller.omada_client.unblock_client(mac)
    except OmadaClientException as ex:
        raise HomeAssistantError(f"Failed to {action} client with MAC {mac}") from ex


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the TP-Link Omada integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        _handle_client_action,
        schema=SCHEMA_RECONNECT_CLIENT,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECONNECT,
        _handle_client_action,
        schema=SCHEMA_RECONNECT_CLIENT,
    )
    for service in (SERVICE_BLOCK, SERVICE_UNBLOCK):
        async_register_admin_service(
            hass,
            DOMAIN,
            service,
            _handle_client_action,
            schema=SCHEMA_RECONNECT_CLIENT,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry[OmadaSiteController],
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
