"""Websocket API for Z-Wave JS."""
from __future__ import annotations

from collections.abc import Callable
import dataclasses
from functools import partial, wraps
from typing import Any

from aiohttp import web, web_exceptions, web_request
import voluptuous as vol
from zwave_js_server.client import Client
from zwave_js_server.const import (
    CommandClass,
    InclusionStrategy,
    LogLevel,
    Protocols,
    QRCodeVersion,
    SecurityClass,
    ZwaveFeature,
)
from zwave_js_server.exceptions import (
    BaseZwaveJSServerError,
    FailedCommand,
    InvalidNewValue,
    NotFoundError,
    SetValueFailed,
)
from zwave_js_server.firmware import begin_firmware_update
from zwave_js_server.model.controller import (
    ControllerStatistics,
    InclusionGrant,
    ProvisioningEntry,
    QRProvisioningInformation,
)
from zwave_js_server.model.firmware import (
    FirmwareUpdateFinished,
    FirmwareUpdateProgress,
)
from zwave_js_server.model.log_config import LogConfig
from zwave_js_server.model.log_message import LogMessage
from zwave_js_server.model.node import Node, NodeStatistics
from zwave_js_server.model.utils import async_parse_qr_code_string
from zwave_js_server.util.node import async_set_config_parameter

from homeassistant.components import websocket_api
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.const import (
    ERR_INVALID_FORMAT,
    ERR_NOT_FOUND,
    ERR_NOT_SUPPORTED,
    ERR_UNKNOWN_ERROR,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    BITMASK_SCHEMA,
    CONF_DATA_COLLECTION_OPTED_IN,
    DATA_CLIENT,
    DOMAIN,
    EVENT_DEVICE_ADDED_TO_REGISTRY,
    LOGGER,
)
from .helpers import async_enable_statistics, update_data_collection_preference
from .migrate import (
    ZWaveMigrationData,
    async_get_migration_data,
    async_map_legacy_zwave_values,
    async_migrate_legacy_zwave,
)

DATA_UNSUBSCRIBE = "unsubs"

# general API constants
ID = "id"
ENTRY_ID = "entry_id"
ERR_NOT_LOADED = "not_loaded"
NODE_ID = "node_id"
COMMAND_CLASS_ID = "command_class_id"
TYPE = "type"
PROPERTY = "property"
PROPERTY_KEY = "property_key"
VALUE = "value"

# constants for log config commands
CONFIG = "config"
LEVEL = "level"
LOG_TO_FILE = "log_to_file"
FILENAME = "filename"
ENABLED = "enabled"
FORCE_CONSOLE = "force_console"

# constants for setting config parameters
VALUE_ID = "value_id"
STATUS = "status"

# constants for data collection
ENABLED = "enabled"
OPTED_IN = "opted_in"

# constants for granting security classes
SECURITY_CLASSES = "security_classes"
CLIENT_SIDE_AUTH = "client_side_auth"

# constants for migration
DRY_RUN = "dry_run"

# constants for inclusion
INCLUSION_STRATEGY = "inclusion_strategy"
PIN = "pin"
FORCE_SECURITY = "force_security"
PLANNED_PROVISIONING_ENTRY = "planned_provisioning_entry"
QR_PROVISIONING_INFORMATION = "qr_provisioning_information"
QR_CODE_STRING = "qr_code_string"

DSK = "dsk"

VERSION = "version"
GENERIC_DEVICE_CLASS = "generic_device_class"
SPECIFIC_DEVICE_CLASS = "specific_device_class"
INSTALLER_ICON_TYPE = "installer_icon_type"
MANUFACTURER_ID = "manufacturer_id"
PRODUCT_TYPE = "product_type"
PRODUCT_ID = "product_id"
APPLICATION_VERSION = "application_version"
MAX_INCLUSION_REQUEST_INTERVAL = "max_inclusion_request_interval"
UUID = "uuid"
SUPPORTED_PROTOCOLS = "supported_protocols"
ADDITIONAL_PROPERTIES = "additional_properties"

FEATURE = "feature"
UNPROVISION = "unprovision"

# https://github.com/zwave-js/node-zwave-js/blob/master/packages/core/src/security/QR.ts#L41
MINIMUM_QR_STRING_LENGTH = 52


def convert_planned_provisioning_entry(info: dict) -> ProvisioningEntry:
    """Handle provisioning entry dict to ProvisioningEntry."""
    info = ProvisioningEntry(
        dsk=info[DSK],
        security_classes=[SecurityClass(sec_cls) for sec_cls in info[SECURITY_CLASSES]],
        additional_properties={
            k: v for k, v in info.items() if k not in (DSK, SECURITY_CLASSES)
        },
    )
    return info


def convert_qr_provisioning_information(info: dict) -> QRProvisioningInformation:
    """Convert QR provisioning information dict to QRProvisioningInformation."""
    protocols = [Protocols(proto) for proto in info.get(SUPPORTED_PROTOCOLS, [])]
    info = QRProvisioningInformation(
        version=QRCodeVersion(info[VERSION]),
        security_classes=[SecurityClass(sec_cls) for sec_cls in info[SECURITY_CLASSES]],
        dsk=info[DSK],
        generic_device_class=info[GENERIC_DEVICE_CLASS],
        specific_device_class=info[SPECIFIC_DEVICE_CLASS],
        installer_icon_type=info[INSTALLER_ICON_TYPE],
        manufacturer_id=info[MANUFACTURER_ID],
        product_type=info[PRODUCT_TYPE],
        product_id=info[PRODUCT_ID],
        application_version=info[APPLICATION_VERSION],
        max_inclusion_request_interval=info.get(MAX_INCLUSION_REQUEST_INTERVAL),
        uuid=info.get(UUID),
        supported_protocols=protocols if protocols else None,
        additional_properties=info.get(ADDITIONAL_PROPERTIES, {}),
    )
    return info


# Helper schemas
PLANNED_PROVISIONING_ENTRY_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(DSK): str,
            vol.Required(SECURITY_CLASSES): vol.All(
                cv.ensure_list,
                [vol.Coerce(SecurityClass)],
            ),
        },
        # Provisioning entries can have extra keys for SmartStart
        extra=vol.ALLOW_EXTRA,
    ),
    convert_planned_provisioning_entry,
)

QR_PROVISIONING_INFORMATION_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(VERSION): vol.Coerce(QRCodeVersion),
            vol.Required(SECURITY_CLASSES): vol.All(
                cv.ensure_list,
                [vol.Coerce(SecurityClass)],
            ),
            vol.Required(DSK): str,
            vol.Required(GENERIC_DEVICE_CLASS): int,
            vol.Required(SPECIFIC_DEVICE_CLASS): int,
            vol.Required(INSTALLER_ICON_TYPE): int,
            vol.Required(MANUFACTURER_ID): int,
            vol.Required(PRODUCT_TYPE): int,
            vol.Required(PRODUCT_ID): int,
            vol.Required(APPLICATION_VERSION): str,
            vol.Optional(MAX_INCLUSION_REQUEST_INTERVAL): vol.Any(int, None),
            vol.Optional(UUID): vol.Any(str, None),
            vol.Optional(SUPPORTED_PROTOCOLS): vol.All(
                cv.ensure_list,
                [vol.Coerce(Protocols)],
            ),
            vol.Optional(ADDITIONAL_PROPERTIES): dict,
        }
    ),
    convert_qr_provisioning_information,
)

QR_CODE_STRING_SCHEMA = vol.All(str, vol.Length(min=MINIMUM_QR_STRING_LENGTH))


def async_get_entry(orig_func: Callable) -> Callable:
    """Decorate async function to get entry."""

    @wraps(orig_func)
    async def async_get_entry_func(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict
    ) -> None:
        """Provide user specific data and store to function."""
        entry_id = msg[ENTRY_ID]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            connection.send_error(
                msg[ID], ERR_NOT_FOUND, f"Config entry {entry_id} not found"
            )
            return

        if entry.state is not ConfigEntryState.LOADED:
            connection.send_error(
                msg[ID], ERR_NOT_LOADED, f"Config entry {entry_id} not loaded"
            )
            return

        client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
        await orig_func(hass, connection, msg, entry, client)

    return async_get_entry_func


def async_get_node(orig_func: Callable) -> Callable:
    """Decorate async function to get node."""

    @async_get_entry
    @wraps(orig_func)
    async def async_get_node_func(
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict,
        entry: ConfigEntry,
        client: Client,
    ) -> None:
        """Provide user specific data and store to function."""
        node_id = msg[NODE_ID]
        node = client.driver.controller.nodes.get(node_id)

        if node is None:
            connection.send_error(msg[ID], ERR_NOT_FOUND, f"Node {node_id} not found")
            return
        await orig_func(hass, connection, msg, node)

    return async_get_node_func


def async_handle_failed_command(orig_func: Callable) -> Callable:
    """Decorate async function to handle FailedCommand and send relevant error."""

    @wraps(orig_func)
    async def async_handle_failed_command_func(
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Handle FailedCommand within function and send relevant error."""
        try:
            await orig_func(hass, connection, msg, *args, **kwargs)
        except FailedCommand as err:
            # Unsubscribe to callbacks
            if unsubs := msg.get(DATA_UNSUBSCRIBE):
                for unsub in unsubs:
                    unsub()
            connection.send_error(msg[ID], err.error_code, err.args[0])

    return async_handle_failed_command_func


@callback
def async_register_api(hass: HomeAssistant) -> None:
    """Register all of our api endpoints."""
    websocket_api.async_register_command(hass, websocket_network_status)
    websocket_api.async_register_command(hass, websocket_node_status)
    websocket_api.async_register_command(hass, websocket_node_metadata)
    websocket_api.async_register_command(hass, websocket_ping_node)
    websocket_api.async_register_command(hass, websocket_add_node)
    websocket_api.async_register_command(hass, websocket_grant_security_classes)
    websocket_api.async_register_command(hass, websocket_validate_dsk_and_enter_pin)
    websocket_api.async_register_command(hass, websocket_provision_smart_start_node)
    websocket_api.async_register_command(hass, websocket_unprovision_smart_start_node)
    websocket_api.async_register_command(hass, websocket_get_provisioning_entries)
    websocket_api.async_register_command(hass, websocket_parse_qr_code_string)
    websocket_api.async_register_command(hass, websocket_supports_feature)
    websocket_api.async_register_command(hass, websocket_stop_inclusion)
    websocket_api.async_register_command(hass, websocket_stop_exclusion)
    websocket_api.async_register_command(hass, websocket_remove_node)
    websocket_api.async_register_command(hass, websocket_remove_failed_node)
    websocket_api.async_register_command(hass, websocket_replace_failed_node)
    websocket_api.async_register_command(hass, websocket_begin_healing_network)
    websocket_api.async_register_command(
        hass, websocket_subscribe_heal_network_progress
    )
    websocket_api.async_register_command(hass, websocket_stop_healing_network)
    websocket_api.async_register_command(hass, websocket_refresh_node_info)
    websocket_api.async_register_command(hass, websocket_refresh_node_values)
    websocket_api.async_register_command(hass, websocket_refresh_node_cc_values)
    websocket_api.async_register_command(hass, websocket_heal_node)
    websocket_api.async_register_command(hass, websocket_set_config_parameter)
    websocket_api.async_register_command(hass, websocket_get_config_parameters)
    websocket_api.async_register_command(hass, websocket_subscribe_log_updates)
    websocket_api.async_register_command(hass, websocket_update_log_config)
    websocket_api.async_register_command(hass, websocket_get_log_config)
    websocket_api.async_register_command(
        hass, websocket_update_data_collection_preference
    )
    websocket_api.async_register_command(hass, websocket_data_collection_status)
    websocket_api.async_register_command(hass, websocket_abort_firmware_update)
    websocket_api.async_register_command(
        hass, websocket_subscribe_firmware_update_status
    )
    websocket_api.async_register_command(hass, websocket_check_for_config_updates)
    websocket_api.async_register_command(hass, websocket_install_config_update)
    websocket_api.async_register_command(
        hass, websocket_subscribe_controller_statistics
    )
    websocket_api.async_register_command(hass, websocket_subscribe_node_statistics)
    websocket_api.async_register_command(hass, websocket_node_ready)
    websocket_api.async_register_command(hass, websocket_migrate_zwave)
    hass.http.register_view(FirmwareUploadView())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required(TYPE): "zwave_js/network_status", vol.Required(ENTRY_ID): str}
)
@websocket_api.async_response
@async_get_entry
async def websocket_network_status(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Get the status of the Z-Wave JS network."""
    controller = client.driver.controller
    await controller.async_get_state()
    data = {
        "client": {
            "ws_server_url": client.ws_server_url,
            "state": "connected" if client.connected else "disconnected",
            "driver_version": client.version.driver_version,
            "server_version": client.version.server_version,
        },
        "controller": {
            "home_id": controller.home_id,
            "library_version": controller.library_version,
            "type": controller.controller_type,
            "own_node_id": controller.own_node_id,
            "is_secondary": controller.is_secondary,
            "is_using_home_id_from_other_network": controller.is_using_home_id_from_other_network,
            "is_sis_present": controller.is_SIS_present,
            "was_real_primary": controller.was_real_primary,
            "is_static_update_controller": controller.is_static_update_controller,
            "is_slave": controller.is_slave,
            "serial_api_version": controller.serial_api_version,
            "manufacturer_id": controller.manufacturer_id,
            "product_id": controller.product_id,
            "product_type": controller.product_type,
            "supported_function_types": controller.supported_function_types,
            "suc_node_id": controller.suc_node_id,
            "supports_timers": controller.supports_timers,
            "is_heal_network_active": controller.is_heal_network_active,
            "inclusion_state": controller.inclusion_state,
            "nodes": list(client.driver.controller.nodes),
        },
    }
    connection.send_result(
        msg[ID],
        data,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/node_ready",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_node_ready(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    node: Node,
) -> None:
    """Subscribe to the node ready event of a Z-Wave JS node."""

    @callback
    def forward_event(event: dict) -> None:
        """Forward the event."""
        connection.send_message(
            websocket_api.event_message(msg[ID], {"event": event["event"]})
        )

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [node.on("ready", forward_event)]

    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/node_status",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_node_status(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    node: Node,
) -> None:
    """Get the status of a Z-Wave JS node."""
    data = {
        "node_id": node.node_id,
        "is_routing": node.is_routing,
        "status": node.status,
        "is_secure": node.is_secure,
        "ready": node.ready,
        "zwave_plus_version": node.zwave_plus_version,
        "highest_security_class": node.highest_security_class,
        "is_controller_node": node.is_controller_node,
    }
    connection.send_result(
        msg[ID],
        data,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/node_metadata",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_node_metadata(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    node: Node,
) -> None:
    """Get the metadata of a Z-Wave JS node."""
    data = {
        "node_id": node.node_id,
        "exclusion": node.device_config.metadata.exclusion,
        "inclusion": node.device_config.metadata.inclusion,
        "manual": node.device_config.metadata.manual,
        "wakeup": node.device_config.metadata.wakeup,
        "reset": node.device_config.metadata.reset,
        "device_database_url": node.device_database_url,
    }
    connection.send_result(
        msg[ID],
        data,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/ping_node",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_ping_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    node: Node,
) -> None:
    """Ping a Z-Wave JS node."""
    result = await node.async_ping()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/add_node",
        vol.Required(ENTRY_ID): str,
        vol.Optional(INCLUSION_STRATEGY, default=InclusionStrategy.DEFAULT): vol.All(
            vol.Coerce(int),
            vol.In(
                [
                    strategy.value
                    for strategy in InclusionStrategy
                    if strategy != InclusionStrategy.SMART_START
                ]
            ),
        ),
        vol.Optional(FORCE_SECURITY): bool,
        vol.Exclusive(
            PLANNED_PROVISIONING_ENTRY, "options"
        ): PLANNED_PROVISIONING_ENTRY_SCHEMA,
        vol.Exclusive(
            QR_PROVISIONING_INFORMATION, "options"
        ): QR_PROVISIONING_INFORMATION_SCHEMA,
        vol.Exclusive(QR_CODE_STRING, "options"): QR_CODE_STRING_SCHEMA,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_add_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Add a node to the Z-Wave network."""
    controller = client.driver.controller
    inclusion_strategy = InclusionStrategy(msg[INCLUSION_STRATEGY])
    force_security = msg.get(FORCE_SECURITY)
    provisioning = (
        msg.get(PLANNED_PROVISIONING_ENTRY)
        or msg.get(QR_PROVISIONING_INFORMATION)
        or msg.get(QR_CODE_STRING)
    )

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(msg[ID], {"event": event["event"]})
        )

    @callback
    def forward_dsk(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": event["event"], "dsk": event["dsk"]}
            )
        )

    @callback
    def forward_requested_grant(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    "requested_grant": event["requested_grant"].to_dict(),
                },
            )
        )

    @callback
    def forward_stage(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": event["event"], "stage": event["stageName"]}
            )
        )

    @callback
    def node_added(event: dict) -> None:
        node = event["node"]
        interview_unsubs = [
            node.on("interview started", forward_event),
            node.on("interview completed", forward_event),
            node.on("interview stage completed", forward_stage),
            node.on("interview failed", forward_event),
        ]
        unsubs.extend(interview_unsubs)
        node_details = {
            "node_id": node.node_id,
            "status": node.status,
            "ready": node.ready,
            "low_security": event["result"].get("lowSecurity", False),
        }
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node added", "node": node_details}
            )
        )

    @callback
    def device_registered(device: DeviceEntry) -> None:
        device_details = {
            "name": device.name,
            "id": device.id,
            "manufacturer": device.manufacturer,
            "model": device.model,
        }
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "device registered", "device": device_details}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [
        controller.on("inclusion started", forward_event),
        controller.on("inclusion failed", forward_event),
        controller.on("inclusion stopped", forward_event),
        controller.on("validate dsk and enter pin", forward_dsk),
        controller.on("grant security classes", forward_requested_grant),
        controller.on("node added", node_added),
        async_dispatcher_connect(
            hass, EVENT_DEVICE_ADDED_TO_REGISTRY, device_registered
        ),
    ]

    try:
        result = await controller.async_begin_inclusion(
            inclusion_strategy, force_security=force_security, provisioning=provisioning
        )
    except ValueError as err:
        connection.send_error(
            msg[ID],
            ERR_INVALID_FORMAT,
            err.args[0],
        )
        return

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/grant_security_classes",
        vol.Required(ENTRY_ID): str,
        vol.Required(SECURITY_CLASSES): vol.All(
            cv.ensure_list,
            [vol.Coerce(SecurityClass)],
        ),
        vol.Optional(CLIENT_SIDE_AUTH, default=False): bool,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_grant_security_classes(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Choose SecurityClass grants as part of S2 inclusion process."""
    inclusion_grant = InclusionGrant(
        [SecurityClass(sec_cls) for sec_cls in msg[SECURITY_CLASSES]],
        msg[CLIENT_SIDE_AUTH],
    )
    await client.driver.controller.async_grant_security_classes(inclusion_grant)
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/validate_dsk_and_enter_pin",
        vol.Required(ENTRY_ID): str,
        vol.Required(PIN): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_validate_dsk_and_enter_pin(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Validate DSK and enter PIN as part of S2 inclusion process."""
    await client.driver.controller.async_validate_dsk_and_enter_pin(msg[PIN])
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/provision_smart_start_node",
        vol.Required(ENTRY_ID): str,
        vol.Exclusive(
            PLANNED_PROVISIONING_ENTRY, "options"
        ): PLANNED_PROVISIONING_ENTRY_SCHEMA,
        vol.Exclusive(
            QR_PROVISIONING_INFORMATION, "options"
        ): QR_PROVISIONING_INFORMATION_SCHEMA,
        vol.Exclusive(QR_CODE_STRING, "options"): QR_CODE_STRING_SCHEMA,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_provision_smart_start_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Pre-provision a smart start node."""
    try:
        cv.has_at_least_one_key(
            PLANNED_PROVISIONING_ENTRY, QR_PROVISIONING_INFORMATION, QR_CODE_STRING
        )(msg)
    except vol.Invalid as err:
        connection.send_error(
            msg[ID],
            ERR_INVALID_FORMAT,
            err.args[0],
        )
        return

    provisioning_info = (
        msg.get(PLANNED_PROVISIONING_ENTRY)
        or msg.get(QR_PROVISIONING_INFORMATION)
        or msg[QR_CODE_STRING]
    )

    if (
        QR_PROVISIONING_INFORMATION in msg
        and provisioning_info.version == QRCodeVersion.S2
    ):
        connection.send_error(
            msg[ID],
            ERR_INVALID_FORMAT,
            "QR code version S2 is not supported for this command",
        )
        return
    await client.driver.controller.async_provision_smart_start_node(provisioning_info)
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/unprovision_smart_start_node",
        vol.Required(ENTRY_ID): str,
        vol.Exclusive(DSK, "input"): str,
        vol.Exclusive(NODE_ID, "input"): int,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_unprovision_smart_start_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Unprovision a smart start node."""
    try:
        cv.has_at_least_one_key(DSK, NODE_ID)(msg)
    except vol.Invalid as err:
        connection.send_error(
            msg[ID],
            ERR_INVALID_FORMAT,
            err.args[0],
        )
        return
    dsk_or_node_id = msg.get(DSK) or msg[NODE_ID]
    await client.driver.controller.async_unprovision_smart_start_node(dsk_or_node_id)
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/get_provisioning_entries",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_get_provisioning_entries(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Get provisioning entries (entries that have been pre-provisioned)."""
    provisioning_entries = (
        await client.driver.controller.async_get_provisioning_entries()
    )
    connection.send_result(
        msg[ID], [dataclasses.asdict(entry) for entry in provisioning_entries]
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/parse_qr_code_string",
        vol.Required(ENTRY_ID): str,
        vol.Required(QR_CODE_STRING): QR_CODE_STRING_SCHEMA,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_parse_qr_code_string(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Parse a QR Code String and return QRProvisioningInformation dict."""
    qr_provisioning_information = await async_parse_qr_code_string(
        client, msg[QR_CODE_STRING]
    )
    connection.send_result(msg[ID], dataclasses.asdict(qr_provisioning_information))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/supports_feature",
        vol.Required(ENTRY_ID): str,
        vol.Required(FEATURE): vol.Coerce(ZwaveFeature),
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_supports_feature(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Check if controller supports a particular feature."""
    supported = await client.driver.controller.async_supports_feature(msg[FEATURE])
    connection.send_result(
        msg[ID],
        {"supported": supported},
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/stop_inclusion",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_stop_inclusion(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Cancel adding a node to the Z-Wave network."""
    controller = client.driver.controller
    result = await controller.async_stop_inclusion()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/stop_exclusion",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_stop_exclusion(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Cancel removing a node from the Z-Wave network."""
    controller = client.driver.controller
    result = await controller.async_stop_exclusion()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/remove_node",
        vol.Required(ENTRY_ID): str,
        vol.Optional(UNPROVISION): bool,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_remove_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Remove a node from the Z-Wave network."""
    controller = client.driver.controller

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(msg[ID], {"event": event["event"]})
        )

    @callback
    def node_removed(event: dict) -> None:
        node = event["node"]
        node_details = {
            "node_id": node.node_id,
        }

        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node removed", "node": node_details}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [
        controller.on("exclusion started", forward_event),
        controller.on("exclusion failed", forward_event),
        controller.on("exclusion stopped", forward_event),
        controller.on("node removed", node_removed),
    ]

    result = await controller.async_begin_exclusion(msg.get(UNPROVISION))
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/replace_failed_node",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
        vol.Optional(INCLUSION_STRATEGY, default=InclusionStrategy.DEFAULT): vol.All(
            vol.Coerce(int),
            vol.In(
                [
                    strategy.value
                    for strategy in InclusionStrategy
                    if strategy != InclusionStrategy.SMART_START
                ]
            ),
        ),
        vol.Optional(FORCE_SECURITY): bool,
        vol.Exclusive(
            PLANNED_PROVISIONING_ENTRY, "options"
        ): PLANNED_PROVISIONING_ENTRY_SCHEMA,
        vol.Exclusive(
            QR_PROVISIONING_INFORMATION, "options"
        ): QR_PROVISIONING_INFORMATION_SCHEMA,
        vol.Exclusive(QR_CODE_STRING, "options"): QR_CODE_STRING_SCHEMA,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_replace_failed_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Replace a failed node with a new node."""
    controller = client.driver.controller
    node_id = msg[NODE_ID]
    inclusion_strategy = InclusionStrategy(msg[INCLUSION_STRATEGY])
    force_security = msg.get(FORCE_SECURITY)
    provisioning = (
        msg.get(PLANNED_PROVISIONING_ENTRY)
        or msg.get(QR_PROVISIONING_INFORMATION)
        or msg.get(QR_CODE_STRING)
    )

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(msg[ID], {"event": event["event"]})
        )

    @callback
    def forward_dsk(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": event["event"], "dsk": event["dsk"]}
            )
        )

    @callback
    def forward_requested_grant(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    "requested_grant": event["requested_grant"].to_dict(),
                },
            )
        )

    @callback
    def forward_stage(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": event["event"], "stage": event["stageName"]}
            )
        )

    @callback
    def node_added(event: dict) -> None:
        node = event["node"]
        interview_unsubs = [
            node.on("interview started", forward_event),
            node.on("interview completed", forward_event),
            node.on("interview stage completed", forward_stage),
            node.on("interview failed", forward_event),
        ]
        unsubs.extend(interview_unsubs)
        node_details = {
            "node_id": node.node_id,
            "status": node.status,
            "ready": node.ready,
        }
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node added", "node": node_details}
            )
        )

    @callback
    def node_removed(event: dict) -> None:
        node = event["node"]
        node_details = {
            "node_id": node.node_id,
        }

        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node removed", "node": node_details}
            )
        )

    @callback
    def device_registered(device: DeviceEntry) -> None:
        device_details = {
            "name": device.name,
            "id": device.id,
            "manufacturer": device.manufacturer,
            "model": device.model,
        }
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "device registered", "device": device_details}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [
        controller.on("inclusion started", forward_event),
        controller.on("inclusion failed", forward_event),
        controller.on("inclusion stopped", forward_event),
        controller.on("validate dsk and enter pin", forward_dsk),
        controller.on("grant security classes", forward_requested_grant),
        controller.on("node removed", node_removed),
        controller.on("node added", node_added),
        async_dispatcher_connect(
            hass, EVENT_DEVICE_ADDED_TO_REGISTRY, device_registered
        ),
    ]

    try:
        result = await controller.async_replace_failed_node(
            node_id,
            inclusion_strategy,
            force_security=force_security,
            provisioning=provisioning,
        )
    except ValueError as err:
        connection.send_error(
            msg[ID],
            ERR_INVALID_FORMAT,
            err.args[0],
        )
        return

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/remove_failed_node",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_remove_failed_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Remove a failed node from the Z-Wave network."""
    controller = client.driver.controller
    node_id = msg[NODE_ID]

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def node_removed(event: dict) -> None:
        node = event["node"]
        node_details = {
            "node_id": node.node_id,
        }

        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node removed", "node": node_details}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [controller.on("node removed", node_removed)]

    result = await controller.async_remove_failed_node(node_id)
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/begin_healing_network",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_begin_healing_network(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Begin healing the Z-Wave network."""
    controller = client.driver.controller

    result = await controller.async_begin_healing_network()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_heal_network_progress",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_get_entry
async def websocket_subscribe_heal_network_progress(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Subscribe to heal Z-Wave network status updates."""
    controller = client.driver.controller

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(key: str, event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": event["event"], "heal_node_status": event[key]}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [
        controller.on("heal network progress", partial(forward_event, "progress")),
        controller.on("heal network done", partial(forward_event, "result")),
    ]

    connection.send_result(msg[ID], controller.heal_network_progress)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/stop_healing_network",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_stop_healing_network(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Stop healing the Z-Wave network."""
    controller = client.driver.controller
    result = await controller.async_stop_healing_network()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/heal_node",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_heal_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Heal a node on the Z-Wave network."""
    controller = client.driver.controller
    node_id = msg[NODE_ID]
    result = await controller.async_heal_node(node_id)
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/refresh_node_info",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    },
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_refresh_node_info(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    node: Node,
) -> None:
    """Re-interview a node."""

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(msg[ID], {"event": event["event"]})
        )

    @callback
    def forward_stage(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": event["event"], "stage": event["stageName"]}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [
        node.on("interview started", forward_event),
        node.on("interview completed", forward_event),
        node.on("interview stage completed", forward_stage),
        node.on("interview failed", forward_event),
    ]

    result = await node.async_refresh_info()
    connection.send_result(msg[ID], result)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/refresh_node_values",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    },
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_refresh_node_values(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    node: Node,
) -> None:
    """Refresh node values."""
    await node.async_refresh_values()
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/refresh_node_cc_values",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
        vol.Required(COMMAND_CLASS_ID): int,
    },
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_refresh_node_cc_values(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    node: Node,
) -> None:
    """Refresh node values for a particular CommandClass."""
    command_class_id = msg[COMMAND_CLASS_ID]

    try:
        command_class = CommandClass(command_class_id)
    except ValueError:
        connection.send_error(
            msg[ID], ERR_NOT_FOUND, f"Command class {command_class_id} not found"
        )
        return

    await node.async_refresh_cc_values(command_class)
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/set_config_parameter",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
        vol.Required(PROPERTY): int,
        vol.Optional(PROPERTY_KEY): int,
        vol.Required(VALUE): vol.Any(int, BITMASK_SCHEMA),
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_set_config_parameter(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    node: Node,
) -> None:
    """Set a config parameter value for a Z-Wave node."""
    property_ = msg[PROPERTY]
    property_key = msg.get(PROPERTY_KEY)
    value = msg[VALUE]

    try:
        zwave_value, cmd_status = await async_set_config_parameter(
            node, value, property_, property_key=property_key
        )
    except (InvalidNewValue, NotFoundError, NotImplementedError, SetValueFailed) as err:
        code = ERR_UNKNOWN_ERROR
        if isinstance(err, NotFoundError):
            code = ERR_NOT_FOUND
        elif isinstance(err, (InvalidNewValue, NotImplementedError)):
            code = ERR_NOT_SUPPORTED

        connection.send_error(
            msg[ID],
            code,
            str(err),
        )
        return

    connection.send_result(
        msg[ID],
        {
            VALUE_ID: zwave_value.value_id,
            STATUS: cmd_status,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/get_config_parameters",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_get_config_parameters(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict, node: Node
) -> None:
    """Get a list of configuration parameters for a Z-Wave node."""
    values = node.get_configuration_values()
    result = {}
    for value_id, zwave_value in values.items():
        metadata = zwave_value.metadata
        result[value_id] = {
            "property": zwave_value.property_,
            "property_key": zwave_value.property_key,
            "configuration_value_type": zwave_value.configuration_value_type.value,
            "metadata": {
                "description": metadata.description,
                "label": metadata.label,
                "type": metadata.type,
                "min": metadata.min,
                "max": metadata.max,
                "unit": metadata.unit,
                "writeable": metadata.writeable,
                "readable": metadata.readable,
            },
            "value": zwave_value.value,
        }
        if zwave_value.metadata.states:
            result[value_id]["metadata"]["states"] = zwave_value.metadata.states

    connection.send_result(
        msg[ID],
        result,
    )


def filename_is_present_if_logging_to_file(obj: dict) -> dict:
    """Validate that filename is provided if log_to_file is True."""
    if obj.get(LOG_TO_FILE, False) and FILENAME not in obj:
        raise vol.Invalid("`filename` must be provided if logging to file")
    return obj


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_log_updates",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_subscribe_log_updates(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Subscribe to log message events from the server."""
    driver = client.driver

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        hass.async_create_task(driver.async_stop_listening_logs())
        for unsub in unsubs:
            unsub()

    @callback
    def log_messages(event: dict) -> None:
        log_msg: LogMessage = event["log_message"]
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "type": "log_message",
                    "log_message": {
                        "timestamp": log_msg.timestamp,
                        "level": log_msg.level,
                        "primary_tags": log_msg.primary_tags,
                        "message": log_msg.formatted_message,
                    },
                },
            )
        )

    @callback
    def log_config_updates(event: dict) -> None:
        log_config: LogConfig = event["log_config"]
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "type": "log_config",
                    "log_config": dataclasses.asdict(log_config),
                },
            )
        )

    msg[DATA_UNSUBSCRIBE] = unsubs = [
        driver.on("logging", log_messages),
        driver.on("log config updated", log_config_updates),
    ]
    connection.subscriptions[msg["id"]] = async_cleanup

    await driver.async_start_listening_logs()
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/update_log_config",
        vol.Required(ENTRY_ID): str,
        vol.Required(CONFIG): vol.All(
            vol.Schema(
                {
                    vol.Optional(ENABLED): cv.boolean,
                    vol.Optional(LEVEL): vol.All(
                        str,
                        vol.Lower,
                        vol.Coerce(LogLevel),
                    ),
                    vol.Optional(LOG_TO_FILE): cv.boolean,
                    vol.Optional(FILENAME): str,
                    vol.Optional(FORCE_CONSOLE): cv.boolean,
                }
            ),
            cv.has_at_least_one_key(
                ENABLED, FILENAME, FORCE_CONSOLE, LEVEL, LOG_TO_FILE
            ),
            filename_is_present_if_logging_to_file,
        ),
    },
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_update_log_config(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Update the driver log config."""
    await client.driver.async_update_log_config(LogConfig(**msg[CONFIG]))
    connection.send_result(
        msg[ID],
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/get_log_config",
        vol.Required(ENTRY_ID): str,
    },
)
@websocket_api.async_response
@async_get_entry
async def websocket_get_log_config(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Get log configuration for the Z-Wave JS driver."""
    connection.send_result(
        msg[ID],
        dataclasses.asdict(client.driver.log_config),
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/update_data_collection_preference",
        vol.Required(ENTRY_ID): str,
        vol.Required(OPTED_IN): bool,
    },
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_update_data_collection_preference(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Update preference for data collection and enable/disable collection."""
    opted_in = msg[OPTED_IN]
    update_data_collection_preference(hass, entry, opted_in)

    if opted_in:
        await async_enable_statistics(client)
    else:
        await client.driver.async_disable_statistics()

    connection.send_result(
        msg[ID],
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/data_collection_status",
        vol.Required(ENTRY_ID): str,
    },
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_data_collection_status(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Return data collection preference and status."""
    result = {
        OPTED_IN: entry.data.get(CONF_DATA_COLLECTION_OPTED_IN),
        ENABLED: await client.driver.async_is_statistics_enabled(),
    }
    connection.send_result(msg[ID], result)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/abort_firmware_update",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_abort_firmware_update(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    node: Node,
) -> None:
    """Abort a firmware update."""
    await node.async_abort_firmware_update()
    connection.send_result(msg[ID])


def _get_firmware_update_progress_dict(
    progress: FirmwareUpdateProgress,
) -> dict[str, int]:
    """Get a dictionary of firmware update progress."""
    return {
        "sent_fragments": progress.sent_fragments,
        "total_fragments": progress.total_fragments,
    }


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_firmware_update_status",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_subscribe_firmware_update_status(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    node: Node,
) -> None:
    """Subscribe to the status of a firmware update."""

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_progress(event: dict) -> None:
        progress: FirmwareUpdateProgress = event["firmware_update_progress"]
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    **_get_firmware_update_progress_dict(progress),
                },
            )
        )

    @callback
    def forward_finished(event: dict) -> None:
        finished: FirmwareUpdateFinished = event["firmware_update_finished"]
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    "status": finished.status,
                    "wait_time": finished.wait_time,
                },
            )
        )

    msg[DATA_UNSUBSCRIBE] = unsubs = [
        node.on("firmware update progress", forward_progress),
        node.on("firmware update finished", forward_finished),
    ]
    connection.subscriptions[msg["id"]] = async_cleanup

    progress = node.firmware_update_progress
    connection.send_result(
        msg[ID], _get_firmware_update_progress_dict(progress) if progress else None
    )


class FirmwareUploadView(HomeAssistantView):
    """View to upload firmware."""

    url = r"/api/zwave_js/firmware/upload/{config_entry_id}/{node_id:\d+}"
    name = "api:zwave_js:firmware:upload"

    async def post(
        self, request: web.Request, config_entry_id: str, node_id: str
    ) -> web.Response:
        """Handle upload."""
        if not request["hass_user"].is_admin:
            raise Unauthorized()
        hass = request.app["hass"]
        if config_entry_id not in hass.data[DOMAIN]:
            raise web_exceptions.HTTPBadRequest

        entry = hass.config_entries.async_get_entry(config_entry_id)
        client: Client = hass.data[DOMAIN][config_entry_id][DATA_CLIENT]
        node = client.driver.controller.nodes.get(int(node_id))
        if not node:
            raise web_exceptions.HTTPNotFound

        # Increase max payload
        request._client_max_size = 1024 * 1024 * 10  # pylint: disable=protected-access

        data = await request.post()

        if "file" not in data or not isinstance(data["file"], web_request.FileField):
            raise web_exceptions.HTTPBadRequest

        uploaded_file: web_request.FileField = data["file"]

        try:
            await begin_firmware_update(
                entry.data[CONF_URL],
                node,
                uploaded_file.filename,
                await hass.async_add_executor_job(uploaded_file.file.read),
                async_get_clientsession(hass),
            )
        except BaseZwaveJSServerError as err:
            raise web_exceptions.HTTPBadRequest from err

        return self.json(None)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/check_for_config_updates",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_check_for_config_updates(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Check for config updates."""
    config_update = await client.driver.async_check_for_config_updates()
    connection.send_result(
        msg[ID],
        {
            "update_available": config_update.update_available,
            "new_version": config_update.new_version,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/install_config_update",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_install_config_update(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Check for config updates."""
    success = await client.driver.async_install_config_update()
    connection.send_result(msg[ID], success)


def _get_controller_statistics_dict(
    statistics: ControllerStatistics,
) -> dict[str, int]:
    """Get dictionary of controller statistics."""
    return {
        "messages_tx": statistics.messages_tx,
        "messages_rx": statistics.messages_rx,
        "messages_dropped_tx": statistics.messages_dropped_tx,
        "messages_dropped_rx": statistics.messages_dropped_rx,
        "nak": statistics.nak,
        "can": statistics.can,
        "timeout_ack": statistics.timeout_ack,
        "timout_response": statistics.timeout_response,
        "timeout_callback": statistics.timeout_callback,
    }


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_controller_statistics",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_get_entry
async def websocket_subscribe_controller_statistics(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Subsribe to the statistics updates for a controller."""

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_stats(event: dict) -> None:
        statistics: ControllerStatistics = event["statistics_updated"]
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    "source": "controller",
                    **_get_controller_statistics_dict(statistics),
                },
            )
        )

    controller = client.driver.controller

    msg[DATA_UNSUBSCRIBE] = unsubs = [
        controller.on("statistics updated", forward_stats)
    ]
    connection.subscriptions[msg["id"]] = async_cleanup

    connection.send_result(
        msg[ID], _get_controller_statistics_dict(controller.statistics)
    )


def _get_node_statistics_dict(statistics: NodeStatistics) -> dict[str, int]:
    """Get dictionary of node statistics."""
    return {
        "commands_tx": statistics.commands_tx,
        "commands_rx": statistics.commands_rx,
        "commands_dropped_tx": statistics.commands_dropped_tx,
        "commands_dropped_rx": statistics.commands_dropped_rx,
        "timeout_response": statistics.timeout_response,
    }


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_node_statistics",
        vol.Required(ENTRY_ID): str,
        vol.Required(NODE_ID): int,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_subscribe_node_statistics(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    node: Node,
) -> None:
    """Subsribe to the statistics updates for a node."""

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_stats(event: dict) -> None:
        statistics: NodeStatistics = event["statistics_updated"]
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    "source": "node",
                    "node_id": node.node_id,
                    **_get_node_statistics_dict(statistics),
                },
            )
        )

    msg[DATA_UNSUBSCRIBE] = unsubs = [node.on("statistics updated", forward_stats)]
    connection.subscriptions[msg["id"]] = async_cleanup

    connection.send_result(msg[ID], _get_node_statistics_dict(node.statistics))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/migrate_zwave",
        vol.Required(ENTRY_ID): str,
        vol.Optional(DRY_RUN, default=True): bool,
    }
)
@websocket_api.async_response
@async_get_entry
async def websocket_migrate_zwave(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    entry: ConfigEntry,
    client: Client,
) -> None:
    """Migrate Z-Wave device and entity data to Z-Wave JS integration."""
    if "zwave" not in hass.config.components:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "zwave_not_loaded", "Integration zwave is not loaded"
            )
        )
        return

    zwave = hass.components.zwave
    zwave_config_entries = hass.config_entries.async_entries("zwave")
    zwave_config_entry = zwave_config_entries[0]  # zwave only has a single config entry
    zwave_data: dict[str, ZWaveMigrationData] = await zwave.async_get_migration_data(
        hass, zwave_config_entry
    )
    LOGGER.debug("Migration zwave data: %s", zwave_data)

    zwave_js_config_entry = entry
    zwave_js_data = await async_get_migration_data(hass, zwave_js_config_entry)
    LOGGER.debug("Migration zwave_js data: %s", zwave_js_data)

    migration_map = async_map_legacy_zwave_values(zwave_data, zwave_js_data)

    zwave_entity_ids = [entry["entity_id"] for entry in zwave_data.values()]
    zwave_js_entity_ids = [entry["entity_id"] for entry in zwave_js_data.values()]
    migration_device_map = {
        zwave_device_id: zwave_js_device_id
        for zwave_js_device_id, zwave_device_id in migration_map.device_entries.items()
    }
    migration_entity_map = {
        zwave_entry["entity_id"]: zwave_js_entity_id
        for zwave_js_entity_id, zwave_entry in migration_map.entity_entries.items()
    }
    LOGGER.debug("Migration entity map: %s", migration_entity_map)

    if not msg[DRY_RUN]:
        await async_migrate_legacy_zwave(
            hass, zwave_config_entry, zwave_js_config_entry, migration_map
        )

    connection.send_result(
        msg[ID],
        {
            "migration_device_map": migration_device_map,
            "zwave_entity_ids": zwave_entity_ids,
            "zwave_js_entity_ids": zwave_js_entity_ids,
            "migration_entity_map": migration_entity_map,
            "migrated": not msg[DRY_RUN],
        },
    )
