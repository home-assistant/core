"""Connected Wi-Fi device scanners for TP-Link Omada access points."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from tplink_omada_client.clients import OmadaWirelessClient
from tplink_omada_client.exceptions import RequestFailed

from homeassistant.components.device_tracker import (
    ScannerEntity,
    SourceType,
    TrackerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .config_flow import (
    CONF_SITE,
    OPT_DEVICE_TRACKER,
    OPT_SCANNED_CLIENTS,
    OPT_TRACKED_CLIENTS,
)
from .const import DOMAIN
from .controller import OmadaClientsCoordinator, OmadaSiteController

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device trackers and scanners."""

    if not config_entry.options.get(OPT_DEVICE_TRACKER, False):
        return

    controller: OmadaSiteController = hass.data[DOMAIN][config_entry.entry_id]

    clients_coordinator = controller.get_clients_coordinator()
    site_id = config_entry.data[CONF_SITE]

    entities: list[OmadaBaseTrackerEntity] = []

    for client_mac in set().union(
        config_entry.options[OPT_SCANNED_CLIENTS],
        config_entry.options[OPT_TRACKED_CLIENTS],
    ):
        client_name = None
        try:
            # Get a display name for the client, even if the client is not currently connected
            client_name = (await controller.omada_client.get_client(client_mac)).name
        except RequestFailed as ex:
            _LOGGER.error(
                "Error getting Omada wi-fi client details for MAC %s: %s",
                client_mac,
                ex,
            )

        if client_mac in config_entry.options[OPT_SCANNED_CLIENTS]:
            entities.extend(
                [
                    OmadaClientScannerEntity(
                        site_id,
                        client_mac,
                        client_name or client_mac,
                        clients_coordinator,
                        ed,
                    )
                    for ed in DEVICE_TRACKERS
                ]
            )
        if client_mac in config_entry.options[OPT_TRACKED_CLIENTS]:
            entities.extend(
                [
                    OmadaClientTrackerEntity(
                        site_id,
                        client_mac,
                        client_name or client_mac,
                        clients_coordinator,
                        ed,
                    )
                    for ed in DEVICE_TRACKERS
                ]
            )

    async_add_entities(entities)


@dataclass(frozen=True, kw_only=True)
class OmadaDeviceTrackerEntityDescription(EntityDescription):
    """Entity description for a device tracker derived from a connected wireless client."""

    coordinator_update_func: Callable[
        [OmadaClientsCoordinator, str], OmadaWirelessClient | None
    ]
    ip_address_fn: Callable[[OmadaWirelessClient | None], str | None]
    mac_address_fn: Callable[[OmadaWirelessClient | None], str | None]
    hostname_fn: Callable[[OmadaWirelessClient | None], str | None]
    location_fn: Callable[[OmadaWirelessClient | None], str | None]
    is_connected_fn: Callable[[OmadaWirelessClient | None], bool]
    has_entity_name = True


DEVICE_TRACKERS = [
    OmadaDeviceTrackerEntityDescription(
        key="device_tracker",
        coordinator_update_func=lambda coordinator, mac: coordinator.data.get(mac),
        ip_address_fn=lambda client: client.ip if client else None,
        mac_address_fn=lambda client: client.mac if client else None,
        hostname_fn=lambda client: client.host_name if client else None,
        location_fn=lambda client: client.ap_name if client else None,
        is_connected_fn=lambda client: client.is_active if client else False,
    )
]


class OmadaBaseTrackerEntity(CoordinatorEntity[OmadaClientsCoordinator]):
    """Base entity for tracking a client connected to the Omada network."""

    entity_description: OmadaDeviceTrackerEntityDescription
    _client_details: OmadaWirelessClient | None = None

    def __init__(
        self,
        site_id: str,
        client_id: str,
        display_name: str,
        coordinator: OmadaClientsCoordinator,
        entity_description: OmadaDeviceTrackerEntityDescription,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._site_id = site_id
        self._client_id = client_id
        self._attr_name = display_name

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.ROUTER

    def _do_update(self) -> None:
        self._client_details = self.entity_description.coordinator_update_func(
            self.coordinator, self._client_id
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._do_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._do_update()
        self.async_write_ha_state()


class OmadaClientScannerEntity(OmadaBaseTrackerEntity, ScannerEntity):
    """Entity for a client connected to the Omada network."""

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self.entity_description.ip_address_fn(self._client_details)

    @property
    def mac_address(self) -> str | None:
        """Return the mac address of the device."""
        return self.entity_description.mac_address_fn(self._client_details)

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self.entity_description.hostname_fn(self._client_details)

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self.entity_description.is_connected_fn(self._client_details)

    @property
    def unique_id(self) -> str | None:
        """Return the unique id of the device."""
        return f"scanner_{self._site_id}_{self._client_id}"


class OmadaClientTrackerEntity(OmadaBaseTrackerEntity, TrackerEntity):
    """Entity for a client connected to the Omada network."""

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        return self.entity_description.location_fn(self._client_details)

    @property
    def unique_id(self) -> str | None:
        """Return the unique id of the device."""
        return f"tracker_{self._site_id}_{self._client_details}"
