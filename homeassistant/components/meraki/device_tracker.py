"""Device trackers for the clients of Meraki networks."""

from datetime import timedelta
from http import HTTPStatus
import json
import logging
from typing import override

import probatio

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    BaseScannerEntity,
    ScannerEntity,
    SourceType,
)
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .coordinator import MerakiConfigEntry, MerakiDataUpdateCoordinator
from .entity import MerakiEntity

PARALLEL_UPDATES = 0

# Access points report Bluetooth devices they hear; one not heard for this long is
# away.
BLUETOOTH_CONSIDER_HOME = timedelta(minutes=5)
BLUETOOTH_UNIQUE_ID_PREFIX = "bluetooth_"

CONF_VALIDATOR = "validator"
CONF_SECRET = "secret"
URL = "/api/meraki"
ACCEPTED_VERSIONS = ["2.0", "2.1"]


_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_VALIDATOR): cv.string,
        probatio.Required(probatio.Secret(CONF_SECRET)): cv.string,
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up an endpoint for the Meraki tracker."""
    hass.http.register_view(MerakiView(config, async_see))

    return True


class MerakiView(HomeAssistantView):
    """View to handle Meraki requests."""

    url = URL
    name = "api:meraki"
    requires_auth = False

    def __init__(self, config: ConfigType, async_see: AsyncSeeCallback) -> None:
        """Initialize Meraki URL endpoints."""
        self.async_see = async_see
        self.validator = config[CONF_VALIDATOR]
        self.secret = config[CONF_SECRET]

    async def get(self, request):
        """Meraki message received as GET."""
        return self.validator

    async def post(self, request):
        """Meraki CMX message received."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTPStatus.BAD_REQUEST)
        _LOGGER.debug("Meraki Data from Post: %s", json.dumps(data))
        if not data.get("secret", False):
            _LOGGER.error("The secret is invalid")
            return self.json_message("No secret", HTTPStatus.UNPROCESSABLE_ENTITY)
        if data["secret"] != self.secret:
            _LOGGER.error("Invalid Secret received from Meraki")
            return self.json_message("Invalid secret", HTTPStatus.UNPROCESSABLE_ENTITY)
        if data["version"] not in ACCEPTED_VERSIONS:
            _LOGGER.error("Invalid API version: %s", data["version"])
            return self.json_message("Invalid version", HTTPStatus.UNPROCESSABLE_ENTITY)
        _LOGGER.debug("Valid Secret")
        if data["type"] not in ("DevicesSeen", "BluetoothDevicesSeen"):
            _LOGGER.error("Unknown Device %s", data["type"])
            return self.json_message(
                "Invalid device type", HTTPStatus.UNPROCESSABLE_ENTITY
            )
        _LOGGER.debug("Processing %s", data["type"])
        if not data["data"]["observations"]:
            _LOGGER.debug("No observations found")
            return None
        self._handle(request.app[KEY_HASS], data)
        return None

    @callback
    def _handle(self, hass, data):
        for i in data["data"]["observations"]:
            data["data"]["secret"] = "hidden"

            lat = i["location"]["lat"]
            lng = i["location"]["lng"]
            try:
                accuracy = int(float(i["location"]["unc"]))
            except ValueError:
                accuracy = 0

            mac = i["clientMac"]
            _LOGGER.debug("clientMac: %s", mac)

            if lat == "NaN" or lng == "NaN":
                _LOGGER.debug("No coordinates received, skipping location for: %s", mac)
                gps_location = None
                accuracy = None
            else:
                gps_location = (lat, lng)

            attrs = {}
            if i.get("os", False):
                attrs["os"] = i["os"]
            if i.get("manufacturer", False):
                attrs["manufacturer"] = i["manufacturer"]
            if i.get("ipv4", False):
                attrs["ipv4"] = i["ipv4"]
            if i.get("ipv6", False):
                attrs["ipv6"] = i["ipv6"]
            if i.get("seenTime", False):
                attrs["seenTime"] = i["seenTime"]
            if i.get("ssid", False):
                attrs["ssid"] = i["ssid"]
            hass.async_create_task(
                self.async_see(
                    gps=gps_location,
                    mac=mac,
                    source_type=SourceType.ROUTER,
                    gps_accuracy=accuracy,
                    attributes=attrs,
                )
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MerakiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up trackers for the clients of the organization's networks."""
    coordinator = entry.runtime_data
    tracked: set[str] = set()

    # The API forgets clients after an hour; their trackers stay, as away.
    restored: list[MerakiClientTracker | MerakiBluetoothTracker] = []
    org_id = coordinator.organization_id
    for registry_entry in er.async_entries_for_config_entry(
        er.async_get(hass), entry.entry_id
    ):
        unique_id = registry_entry.unique_id
        name = registry_entry.original_name
        mac = unique_id.removeprefix(f"{org_id}_")
        if mac.startswith(BLUETOOTH_UNIQUE_ID_PREFIX):
            mac = mac.removeprefix(BLUETOOTH_UNIQUE_ID_PREFIX)
            restored.append(MerakiBluetoothTracker(coordinator, mac, name))
        else:
            restored.append(MerakiClientTracker(coordinator, mac, name))
        tracked.add(unique_id)
    async_add_entities(restored)

    @callback
    def _async_add_new_clients() -> None:
        new: list[MerakiClientTracker | MerakiBluetoothTracker] = []
        for mac, client in coordinator.data.clients.items():
            if (unique_id := _client_unique_id(org_id, mac)) not in tracked:
                tracked.add(unique_id)
                new.append(MerakiClientTracker(coordinator, mac, client.description))
        for mac, bluetooth_client in coordinator.data.bluetooth_clients.items():
            # The API has no address type to tell rotating addresses, which would
            # add a dead tracker every few minutes. Those of phones come unnamed.
            if bluetooth_client.name is None:
                continue
            if (unique_id := _bluetooth_unique_id(org_id, mac)) not in tracked:
                tracked.add(unique_id)
                new.append(
                    MerakiBluetoothTracker(coordinator, mac, bluetooth_client.name)
                )
        async_add_entities(new)

    _async_add_new_clients()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_clients))


# The same device can be a client in several organizations.
def _client_unique_id(org_id: str, mac: str) -> str:
    return f"{org_id}_{mac}"


def _bluetooth_unique_id(org_id: str, mac: str) -> str:
    return f"{org_id}_{BLUETOOTH_UNIQUE_ID_PREFIX}{mac}"


class MerakiClientTracker(MerakiEntity, ScannerEntity):
    """A Wi-Fi or wired client, home while it is connected to the network."""

    def __init__(
        self, coordinator: MerakiDataUpdateCoordinator, mac: str, name: str | None
    ) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self.mac = mac
        self._attr_mac_address = mac
        self._attr_name = name or mac
        self._async_update_attrs()

    @property
    @override
    def unique_id(self) -> str:
        """Return the MAC, scoped to the organization."""
        return _client_unique_id(self.coordinator.organization_id, self.mac)

    @property
    @override
    def is_connected(self) -> bool:
        """Return True if Meraki reports the client as online."""
        client = self.coordinator.data.clients.get(self.mac)
        return client is not None and client.online

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        if client := self.coordinator.data.clients.get(self.mac):
            self._attr_hostname = client.description
            self._attr_ip_address = client.ip


class MerakiBluetoothTracker(MerakiEntity, BaseScannerEntity):
    """A Bluetooth device, home while access points hear it."""

    _attr_entity_registry_enabled_default = False
    _attr_source_type = SourceType.BLUETOOTH_LE

    def __init__(
        self, coordinator: MerakiDataUpdateCoordinator, mac: str, name: str | None
    ) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self.mac = mac
        self._attr_unique_id = _bluetooth_unique_id(coordinator.organization_id, mac)
        self._attr_name = name or mac

    @property
    @override
    def is_connected(self) -> bool:
        """Return True if an access point heard the device recently."""
        client = self.coordinator.data.bluetooth_clients.get(self.mac)
        return (
            client is not None
            and dt_util.utcnow() - client.last_seen < BLUETOOTH_CONSIDER_HOME
        )
