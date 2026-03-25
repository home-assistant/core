"""The Span Panel integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import cast

from span_panel_api import SpanMqttClient, SpanPanelSnapshot
from span_panel_api.exceptions import (
    SpanPanelAuthError,
    SpanPanelConnectionError,
    SpanPanelTimeoutError,
)
from span_panel_api.mqtt.models import MqttClientConfig
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import (
    CoreState,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType

# Import config flow to ensure it's registered
from . import config_flow  # noqa: F401  # type: ignore[misc]
from .const import (
    CONF_API_VERSION,
    CONF_EBUS_BROKER_HOST,
    CONF_EBUS_BROKER_PASSWORD,
    CONF_EBUS_BROKER_PORT,
    CONF_EBUS_BROKER_USERNAME,
    CONF_HTTP_PORT,
    DEFAULT_SNAPSHOT_INTERVAL,
    DOMAIN,
)
from .coordinator import SpanPanelCoordinator
from .helpers import build_circuit_unique_id
from .options import SNAPSHOT_UPDATE_INTERVAL
from .util import snapshot_to_device_info
from .websocket import async_register_commands

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class SpanPanelRuntimeData:
    """Runtime data for a Span Panel config entry."""

    coordinator: SpanPanelCoordinator


type SpanPanelConfigEntry = ConfigEntry[SpanPanelRuntimeData]

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)

# Must match the storage version produced by the latest supported entry format.
CURRENT_CONFIG_VERSION = 6

# Map internal device_type values to external manifest format
_DEVICE_TYPE_MAP: dict[str, str] = {"bess": "battery"}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Span Panel integration (domain-level, called once)."""
    _async_register_services(hass)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SpanPanelConfigEntry
) -> bool:
    """Apply config entry migrations.

    Entries reaching core are expected to already be storage-compatible with the
    latest supported custom integration release. If an older version is seen,
    bump the version marker without mutating stored data.
    """
    if config_entry.version < CURRENT_CONFIG_VERSION:
        _LOGGER.debug(
            "Updating config entry %s from version %s to %s without data changes",
            config_entry.entry_id,
            config_entry.version,
            CURRENT_CONFIG_VERSION,
        )
        hass.config_entries.async_update_entry(
            config_entry,
            version=CURRENT_CONFIG_VERSION,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SpanPanelConfigEntry) -> bool:
    """Set up Span Panel from a config entry."""
    _LOGGER.debug("Setting up entry %s (version %s)", entry.entry_id, entry.version)

    # Legacy in-integration simulation entries — skip setup; notification was
    # already created during migration.
    if entry.data.get(CONF_API_VERSION) == "simulation" or entry.data.get(
        "simulation_mode", False
    ):
        return False

    # Register WebSocket commands once per HA instance
    domain_data: dict[str, bool] = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get("websocket_registered"):
        domain_data["websocket_registered"] = True
        async_register_commands(hass)

    config = entry.data
    api_version = config.get(CONF_API_VERSION, "v1")

    # v1 entries: trigger reauthentication so user can provide v2 credentials
    if api_version == "v1":
        raise ConfigEntryAuthFailed(
            "This panel requires reauthentication. "
            "Please reauthenticate with your panel passphrase or proximity."
        )

    coordinator: SpanPanelCoordinator | None = None

    try:
        # --- v2 MQTT entries ---
        if api_version == "v2":
            required_keys = (
                CONF_EBUS_BROKER_HOST,
                CONF_EBUS_BROKER_USERNAME,
                CONF_EBUS_BROKER_PASSWORD,
                CONF_EBUS_BROKER_PORT,
            )
            missing = [k for k in required_keys if not config.get(k)]
            if missing:
                raise ConfigEntryAuthFailed(  # noqa: TRY301
                    f"v2 panel is missing MQTT credentials ({', '.join(missing)}). "
                    "Please reauthenticate to provide a passphrase."
                )

            host = config[CONF_HOST]
            serial_number = entry.unique_id
            if not serial_number:
                raise ConfigEntryNotReady(  # noqa: TRY301
                    "Config entry has no unique_id (serial number)"
                )

            # The MQTT broker runs on the panel itself. The panel advertises
            # its own mDNS hostname (.local) as ebusBrokerHost, but mDNS
            # does not resolve across VLAN boundaries. Use the user-configured
            # panel host (IP or FQDN) which is known reachable.
            advertised_broker = config[CONF_EBUS_BROKER_HOST]
            if advertised_broker != host:
                _LOGGER.debug(
                    "Panel advertised broker host '%s' differs from configured "
                    "host '%s'; using configured host for MQTT connection",
                    advertised_broker,
                    host,
                )

            broker_config = MqttClientConfig(
                broker_host=host,
                username=config[CONF_EBUS_BROKER_USERNAME],
                password=config[CONF_EBUS_BROKER_PASSWORD],
                mqtts_port=int(config[CONF_EBUS_BROKER_PORT]),
            )

            panel_http_port = int(config.get(CONF_HTTP_PORT, 80))

            snapshot_interval = entry.options.get(
                SNAPSHOT_UPDATE_INTERVAL, DEFAULT_SNAPSHOT_INTERVAL
            )
            client = SpanMqttClient(
                host,
                serial_number,
                broker_config,
                snapshot_interval=snapshot_interval,
                panel_http_port=panel_http_port,
            )
            try:
                await client.connect()
            except SpanPanelAuthError as err:
                await client.close()
                raise ConfigEntryAuthFailed(
                    f"MQTT authentication failed: {err}"
                ) from err
            except (SpanPanelConnectionError, SpanPanelTimeoutError) as err:
                await client.close()
                raise ConfigEntryNotReady(
                    f"Failed to connect to SPAN panel: {err}"
                ) from err

            coordinator = SpanPanelCoordinator(hass, client, entry)
            await coordinator.async_config_entry_first_refresh()
            await coordinator.async_setup_streaming()

        else:
            raise ConfigEntryError(  # noqa: TRY301
                f"Unknown api_version: {api_version}"
            )

        # --- Common setup for all transport modes ---

        entry.async_on_unload(entry.add_update_listener(update_listener))

        entry.runtime_data = SpanPanelRuntimeData(coordinator=coordinator)

        snapshot: SpanPanelSnapshot = coordinator.data
        serial_number = snapshot.serial_number

        base_name = "SPAN Panel"

        # Check existing config entries to avoid conflicts
        existing_entries = hass.config_entries.async_entries(DOMAIN)
        existing_titles = {
            e.title
            for e in existing_entries
            if e.title and e.title != serial_number and e.entry_id != entry.entry_id
        }

        smart_device_name = base_name
        counter = 2
        while smart_device_name in existing_titles:
            smart_device_name = f"{base_name} {counter}"
            counter += 1

        # Update config entry title if it's currently the serial number
        if entry.title == serial_number:
            hass.config_entries.async_update_entry(entry, title=smart_device_name)

        await ensure_device_registered(hass, entry, snapshot, smart_device_name)

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        if coordinator is not None:
            await coordinator.async_shutdown()
        raise
    else:
        return True


async def async_unload_entry(hass: HomeAssistant, entry: SpanPanelConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading SPAN Panel integration")

    if hasattr(entry, "runtime_data") and entry.runtime_data is not None:
        await entry.runtime_data.coordinator.async_shutdown()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: SpanPanelConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow manual removal of a device (e.g., stale EVSE sub-device).

    The main panel device cannot be removed — only sub-devices (like EVSE
    chargers) that are no longer present can be removed by the user.
    """
    if not hasattr(config_entry, "runtime_data") or config_entry.runtime_data is None:
        return True

    coordinator = config_entry.runtime_data.coordinator
    snapshot = coordinator.data

    # Identify the main panel device identifier
    panel_identifier = snapshot.serial_number

    # Prevent removal of the main panel device
    for identifier in device_entry.identifiers:
        if identifier == (DOMAIN, panel_identifier):
            return False

    return True


async def update_listener(hass: HomeAssistant, entry: SpanPanelConfigEntry) -> None:
    """Handle options updates."""
    _LOGGER.debug("Configuration options changed for entry: %s", entry.entry_id)

    try:
        if hass.state is not CoreState.running:
            return

        await hass.config_entries.async_reload(entry.entry_id)
        _LOGGER.debug("Successfully reloaded SPAN Panel integration")

    except asyncio.CancelledError:
        raise
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("Failed to reload SPAN Panel integration: %s", err)


async def ensure_device_registered(
    hass: HomeAssistant,
    entry: SpanPanelConfigEntry,
    snapshot: SpanPanelSnapshot,
    device_name: str,
) -> None:
    """Register or reconcile the HA Device before creating sensors.

    Ensures the device exists in the device registry with proper naming and
    identifiers.
    """
    device_registry = dr.async_get(hass)

    serial_number = snapshot.serial_number
    host = entry.data.get(CONF_HOST)

    existing_device = device_registry.async_get_device(
        identifiers={(DOMAIN, serial_number)}
    )

    if existing_device:
        if existing_device.name == serial_number:
            device_registry.async_update_device(existing_device.id, name=device_name)
    else:
        device_info = snapshot_to_device_info(snapshot, device_name, host=host)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **device_info
        )


def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain-level services (called once per HA instance)."""

    async def async_handle_export_manifest(
        _call: ServiceCall,
    ) -> ServiceResponse:
        """Export circuit topology manifest for all configured SPAN panels."""
        if not hass.config_entries.async_loaded_entries(DOMAIN):
            raise ServiceValidationError(
                "No SPAN panel configuration entries are loaded. "
                "Add and configure a SPAN panel before calling this service.",
                translation_domain=DOMAIN,
                translation_key="export_manifest_no_entries",
            )

        entity_reg = er.async_get(hass)
        panels = []

        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            if not hasattr(entry, "runtime_data") or not isinstance(
                entry.runtime_data, SpanPanelRuntimeData
            ):
                continue

            snapshot = entry.runtime_data.coordinator.data
            serial = snapshot.serial_number
            circuits = []

            for circuit_id, circuit in snapshot.circuits.items():
                if circuit_id.startswith("unmapped_tab_"):
                    continue

                tabs = getattr(circuit, "tabs", None)
                if not tabs:
                    continue

                unique_id = build_circuit_unique_id(serial, circuit_id, "instantPowerW")
                entity_id = entity_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
                if entity_id is None:
                    continue

                raw_type = getattr(circuit, "device_type", "circuit")

                circuits.append(
                    {
                        "entity_id": entity_id,
                        "template": f"clone_{min(tabs)}",
                        "device_type": _DEVICE_TYPE_MAP.get(raw_type, raw_type),
                        "tabs": list(tabs),
                    }
                )

            if circuits:
                panels.append(
                    {
                        "serial": serial,
                        "host": entry.data[CONF_HOST],
                        "circuits": circuits,
                    }
                )

        return cast(ServiceResponse, {"panels": panels})

    hass.services.async_register(
        DOMAIN,
        "export_circuit_manifest",
        async_handle_export_manifest,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )
