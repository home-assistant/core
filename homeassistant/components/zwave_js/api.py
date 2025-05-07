"""Websocket API for Z-Wave JS."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from contextlib import suppress
import dataclasses
from functools import partial, wraps
from typing import Any, Concatenate, Literal, cast

from aiohttp import web, web_exceptions, web_request
import voluptuous as vol
from zwave_js_server.client import Client
from zwave_js_server.const import (
    CommandClass,
    ExclusionStrategy,
    InclusionState,
    InclusionStrategy,
    LogLevel,
    NodeStatus,
    Protocols,
    ProvisioningEntryStatus,
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
from zwave_js_server.firmware import controller_firmware_update_otw, update_firmware
from zwave_js_server.model.controller import (
    ControllerStatistics,
    InclusionGrant,
    ProvisioningEntry,
    QRProvisioningInformation,
)
from zwave_js_server.model.controller.firmware import (
    ControllerFirmwareUpdateData,
    ControllerFirmwareUpdateProgress,
    ControllerFirmwareUpdateResult,
)
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.endpoint import Endpoint
from zwave_js_server.model.log_config import LogConfig
from zwave_js_server.model.log_message import LogMessage
from zwave_js_server.model.node import Node, NodeStatistics
from zwave_js_server.model.node.firmware import (
    NodeFirmwareUpdateData,
    NodeFirmwareUpdateProgress,
    NodeFirmwareUpdateResult,
)
from zwave_js_server.model.utils import (
    async_parse_qr_code_string,
    async_try_parse_dsk_from_qr_code_string,
)
from zwave_js_server.model.value import ConfigurationValueFormat
from zwave_js_server.util.node import async_set_config_parameter

from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_HASS, HomeAssistantView, require_admin
from homeassistant.components.websocket_api import (
    ERR_INVALID_FORMAT,
    ERR_NOT_FOUND,
    ERR_NOT_SUPPORTED,
    ERR_UNKNOWN_ERROR,
    ActiveConnection,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .config_validation import BITMASK_SCHEMA
from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_ENDPOINT,
    ATTR_METHOD_NAME,
    ATTR_PARAMETERS,
    ATTR_WAIT_FOR_RESULT,
    CONF_DATA_COLLECTION_OPTED_IN,
    CONF_INSTALLER_MODE,
    DATA_CLIENT,
    DOMAIN,
    EVENT_DEVICE_ADDED_TO_REGISTRY,
    RESTORE_NVM_DRIVER_READY_TIMEOUT,
    USER_AGENT,
)
from .helpers import (
    async_enable_statistics,
    async_get_node_from_device_id,
    async_get_provisioning_entry_from_device_id,
    get_device_id,
)

DATA_UNSUBSCRIBE = "unsubs"

# general API constants
ID = "id"
ENTRY_ID = "entry_id"
ERR_NOT_LOADED = "not_loaded"
NODE_ID = "node_id"
DEVICE_ID = "device_id"
COMMAND_CLASS_ID = "command_class_id"
TYPE = "type"
PROPERTY = "property"
PROPERTY_KEY = "property_key"
ENDPOINT = "endpoint"
VALUE = "value"
VALUE_SIZE = "value_size"
VALUE_FORMAT = "value_format"

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
SECURITY_CLASSES = "securityClasses"
CLIENT_SIDE_AUTH = "clientSideAuth"

# constants for inclusion
INCLUSION_STRATEGY = "inclusion_strategy"

INCLUSION_STRATEGY_NOT_SMART_START: dict[
    int,
    Literal[
        InclusionStrategy.DEFAULT,
        InclusionStrategy.SECURITY_S0,
        InclusionStrategy.SECURITY_S2,
        InclusionStrategy.INSECURE,
    ],
] = {
    InclusionStrategy.DEFAULT.value: InclusionStrategy.DEFAULT,
    InclusionStrategy.SECURITY_S0.value: InclusionStrategy.SECURITY_S0,
    InclusionStrategy.SECURITY_S2.value: InclusionStrategy.SECURITY_S2,
    InclusionStrategy.INSECURE.value: InclusionStrategy.INSECURE,
}
PIN = "pin"
FORCE_SECURITY = "force_security"
PLANNED_PROVISIONING_ENTRY = "planned_provisioning_entry"
QR_PROVISIONING_INFORMATION = "qr_provisioning_information"
QR_CODE_STRING = "qr_code_string"

DSK = "dsk"

VERSION = "version"
GENERIC_DEVICE_CLASS = "genericDeviceClass"
SPECIFIC_DEVICE_CLASS = "specificDeviceClass"
INSTALLER_ICON_TYPE = "installerIconType"
MANUFACTURER_ID = "manufacturerId"
PRODUCT_TYPE = "productType"
PRODUCT_ID = "productId"
APPLICATION_VERSION = "applicationVersion"
MAX_INCLUSION_REQUEST_INTERVAL = "maxInclusionRequestInterval"
UUID = "uuid"
SUPPORTED_PROTOCOLS = "supportedProtocols"
ADDITIONAL_PROPERTIES = "additional_properties"
STATUS = "status"
REQUESTED_SECURITY_CLASSES = "requestedSecurityClasses"

PROTOCOL = "protocol"
DEVICE_NAME = "device_name"
AREA_ID = "area_id"

FEATURE = "feature"
STRATEGY = "strategy"

# https://github.com/zwave-js/node-zwave-js/blob/master/packages/core/src/security/QR.ts#L41
MINIMUM_QR_STRING_LENGTH = 52

HARD_RESET_CONTROLLER_DRIVER_READY_TIMEOUT = 60


# Helper schemas
PLANNED_PROVISIONING_ENTRY_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(DSK): str,
            vol.Required(SECURITY_CLASSES): vol.All(
                cv.ensure_list,
                [vol.Coerce(SecurityClass)],
            ),
            vol.Optional(STATUS, default=ProvisioningEntryStatus.ACTIVE): vol.Coerce(
                ProvisioningEntryStatus
            ),
            vol.Optional(REQUESTED_SECURITY_CLASSES): vol.All(
                cv.ensure_list, [vol.Coerce(SecurityClass)]
            ),
        },
        # Provisioning entries can have extra keys for SmartStart
        extra=vol.ALLOW_EXTRA,
    ),
    ProvisioningEntry.from_dict,
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
            vol.Optional(STATUS, default=ProvisioningEntryStatus.ACTIVE): vol.Coerce(
                ProvisioningEntryStatus
            ),
            vol.Optional(REQUESTED_SECURITY_CLASSES): vol.All(
                cv.ensure_list, [vol.Coerce(SecurityClass)]
            ),
        },
        extra=vol.ALLOW_EXTRA,
    ),
    QRProvisioningInformation.from_dict,
)

QR_CODE_STRING_SCHEMA = vol.All(str, vol.Length(min=MINIMUM_QR_STRING_LENGTH))


async def _async_get_entry(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry_id: str,
) -> tuple[ConfigEntry, Client, Driver] | tuple[None, None, None]:
    """Get config entry and client from message data."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        connection.send_error(
            msg[ID], ERR_NOT_FOUND, f"Config entry {entry_id} not found"
        )
        return None, None, None

    if entry.state is not ConfigEntryState.LOADED:
        connection.send_error(
            msg[ID], ERR_NOT_LOADED, f"Config entry {entry_id} not loaded"
        )
        return None, None, None

    client: Client = entry.runtime_data[DATA_CLIENT]

    if client.driver is None:
        connection.send_error(
            msg[ID],
            ERR_NOT_LOADED,
            f"Config entry {msg[ENTRY_ID]} not loaded, driver not ready",
        )
        return None, None, None

    return entry, client, client.driver


def async_get_entry(
    orig_func: Callable[
        [HomeAssistant, ActiveConnection, dict[str, Any], ConfigEntry, Client, Driver],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any]], Coroutine[Any, Any, None]
]:
    """Decorate async function to get entry."""

    @wraps(orig_func)
    async def async_get_entry_func(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        """Provide user specific data and store to function."""
        entry, client, driver = await _async_get_entry(
            hass, connection, msg, msg[ENTRY_ID]
        )

        if not entry or not client or not driver:
            return

        await orig_func(hass, connection, msg, entry, client, driver)

    return async_get_entry_func


async def _async_get_node(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict, device_id: str
) -> Node | None:
    """Get node from message data."""
    try:
        node = async_get_node_from_device_id(hass, device_id)
    except ValueError as err:
        error_code = ERR_NOT_FOUND
        if "loaded" in err.args[0]:
            error_code = ERR_NOT_LOADED
        connection.send_error(msg[ID], error_code, err.args[0])
        return None
    return node


def async_get_node(
    orig_func: Callable[
        [HomeAssistant, ActiveConnection, dict[str, Any], Node],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any]], Coroutine[Any, Any, None]
]:
    """Decorate async function to get node."""

    @wraps(orig_func)
    async def async_get_node_func(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        """Provide user specific data and store to function."""
        node = await _async_get_node(hass, connection, msg, msg[DEVICE_ID])
        if not node:
            return
        await orig_func(hass, connection, msg, node)

    return async_get_node_func


def async_handle_failed_command[**_P](
    orig_func: Callable[
        Concatenate[HomeAssistant, ActiveConnection, dict[str, Any], _P],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    Concatenate[HomeAssistant, ActiveConnection, dict[str, Any], _P],
    Coroutine[Any, Any, None],
]:
    """Decorate async function to handle FailedCommand and send relevant error."""

    @wraps(orig_func)
    async def async_handle_failed_command_func(
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict[str, Any],
        *args: _P.args,
        **kwargs: _P.kwargs,
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


def node_status(node: Node) -> dict[str, Any]:
    """Get node status."""
    return {
        "node_id": node.node_id,
        "is_routing": node.is_routing,
        "status": node.status,
        "is_secure": node.is_secure,
        "ready": node.ready,
        "zwave_plus_version": node.zwave_plus_version,
        "highest_security_class": node.highest_security_class,
        "is_controller_node": node.is_controller_node,
        "has_firmware_update_cc": any(
            cc.id == CommandClass.FIRMWARE_UPDATE_MD.value
            for cc in node.command_classes
        ),
    }


@callback
def async_register_api(hass: HomeAssistant) -> None:
    """Register all of our api endpoints."""
    websocket_api.async_register_command(hass, websocket_network_status)
    websocket_api.async_register_command(hass, websocket_subscribe_node_status)
    websocket_api.async_register_command(hass, websocket_node_status)
    websocket_api.async_register_command(hass, websocket_node_metadata)
    websocket_api.async_register_command(hass, websocket_node_alerts)
    websocket_api.async_register_command(hass, websocket_add_node)
    websocket_api.async_register_command(hass, websocket_cancel_secure_bootstrap_s2)
    websocket_api.async_register_command(hass, websocket_subscribe_s2_inclusion)
    websocket_api.async_register_command(hass, websocket_grant_security_classes)
    websocket_api.async_register_command(hass, websocket_validate_dsk_and_enter_pin)
    websocket_api.async_register_command(hass, websocket_subscribe_new_devices)
    websocket_api.async_register_command(hass, websocket_provision_smart_start_node)
    websocket_api.async_register_command(hass, websocket_unprovision_smart_start_node)
    websocket_api.async_register_command(hass, websocket_get_provisioning_entries)
    websocket_api.async_register_command(hass, websocket_parse_qr_code_string)
    websocket_api.async_register_command(
        hass, websocket_try_parse_dsk_from_qr_code_string
    )
    websocket_api.async_register_command(hass, websocket_lookup_device)
    websocket_api.async_register_command(hass, websocket_supports_feature)
    websocket_api.async_register_command(hass, websocket_stop_inclusion)
    websocket_api.async_register_command(hass, websocket_stop_exclusion)
    websocket_api.async_register_command(hass, websocket_remove_node)
    websocket_api.async_register_command(hass, websocket_remove_failed_node)
    websocket_api.async_register_command(hass, websocket_replace_failed_node)
    websocket_api.async_register_command(hass, websocket_begin_rebuilding_routes)
    websocket_api.async_register_command(
        hass, websocket_subscribe_rebuild_routes_progress
    )
    websocket_api.async_register_command(hass, websocket_stop_rebuilding_routes)
    websocket_api.async_register_command(hass, websocket_refresh_node_info)
    websocket_api.async_register_command(hass, websocket_refresh_node_values)
    websocket_api.async_register_command(hass, websocket_refresh_node_cc_values)
    websocket_api.async_register_command(hass, websocket_rebuild_node_routes)
    websocket_api.async_register_command(hass, websocket_set_config_parameter)
    websocket_api.async_register_command(hass, websocket_get_config_parameters)
    websocket_api.async_register_command(hass, websocket_get_raw_config_parameter)
    websocket_api.async_register_command(hass, websocket_set_raw_config_parameter)
    websocket_api.async_register_command(hass, websocket_subscribe_log_updates)
    websocket_api.async_register_command(hass, websocket_update_log_config)
    websocket_api.async_register_command(hass, websocket_get_log_config)
    websocket_api.async_register_command(
        hass, websocket_update_data_collection_preference
    )
    websocket_api.async_register_command(hass, websocket_data_collection_status)
    websocket_api.async_register_command(hass, websocket_abort_firmware_update)
    websocket_api.async_register_command(
        hass, websocket_is_node_firmware_update_in_progress
    )
    websocket_api.async_register_command(
        hass, websocket_subscribe_firmware_update_status
    )
    websocket_api.async_register_command(
        hass, websocket_get_node_firmware_update_capabilities
    )
    websocket_api.async_register_command(
        hass, websocket_is_any_ota_firmware_update_in_progress
    )
    websocket_api.async_register_command(hass, websocket_check_for_config_updates)
    websocket_api.async_register_command(hass, websocket_install_config_update)
    websocket_api.async_register_command(
        hass, websocket_subscribe_controller_statistics
    )
    websocket_api.async_register_command(hass, websocket_subscribe_node_statistics)
    websocket_api.async_register_command(hass, websocket_hard_reset_controller)
    websocket_api.async_register_command(hass, websocket_node_capabilities)
    websocket_api.async_register_command(hass, websocket_invoke_cc_api)
    websocket_api.async_register_command(hass, websocket_get_integration_settings)
    websocket_api.async_register_command(hass, websocket_backup_nvm)
    websocket_api.async_register_command(hass, websocket_restore_nvm)
    hass.http.register_view(FirmwareUploadView(dr.async_get(hass)))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/network_status",
        vol.Exclusive(DEVICE_ID, "id"): str,
        vol.Exclusive(ENTRY_ID, "id"): str,
    }
)
@websocket_api.async_response
async def websocket_network_status(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get the status of the Z-Wave JS network."""
    if ENTRY_ID in msg:
        _, client, driver = await _async_get_entry(hass, connection, msg, msg[ENTRY_ID])
        if not client or not driver:
            return
    elif DEVICE_ID in msg:
        node = await _async_get_node(hass, connection, msg, msg[DEVICE_ID])
        if not node:
            return
        client = node.client
        assert client.driver
        driver = client.driver
    else:
        connection.send_error(
            msg[ID], ERR_INVALID_FORMAT, "Must specify either device_id or entry_id"
        )
        return
    controller = driver.controller
    controller.update(await controller.async_get_state())
    client_version_info = client.version
    assert client_version_info  # When client is connected version info is set.
    data = {
        "client": {
            "ws_server_url": client.ws_server_url,
            "state": "connected" if client.connected else "disconnected",
            "driver_version": client_version_info.driver_version,
            "server_version": client_version_info.server_version,
            "server_logging_enabled": client.server_logging_enabled,
        },
        "controller": {
            "home_id": controller.home_id,
            "sdk_version": controller.sdk_version,
            "type": controller.controller_type,
            "own_node_id": controller.own_node_id,
            "is_primary": controller.is_primary,
            "is_using_home_id_from_other_network": (
                controller.is_using_home_id_from_other_network
            ),
            "is_sis_present": controller.is_SIS_present,
            "was_real_primary": controller.was_real_primary,
            "is_suc": controller.is_suc,
            "node_type": controller.node_type,
            "firmware_version": controller.firmware_version,
            "manufacturer_id": controller.manufacturer_id,
            "product_id": controller.product_id,
            "product_type": controller.product_type,
            "supported_function_types": controller.supported_function_types,
            "suc_node_id": controller.suc_node_id,
            "supports_timers": controller.supports_timers,
            "supports_long_range": controller.supports_long_range,
            "is_rebuilding_routes": controller.is_rebuilding_routes,
            "inclusion_state": controller.inclusion_state,
            "rf_region": controller.rf_region,
            "status": controller.status,
            "nodes": [node_status(node) for node in driver.controller.nodes.values()],
        },
    }
    connection.send_result(
        msg[ID],
        data,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_node_status",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_subscribe_node_status(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Subscribe to node status update events of a Z-Wave JS node."""

    @callback
    def forward_event(event: dict) -> None:
        """Forward the event."""
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {"event": event["event"], "status": node.status, "ready": node.ready},
            )
        )

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [
        node.on(evt, forward_event)
        for evt in ("alive", "dead", "sleep", "wake up", "ready")
    ]

    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/node_status",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_node_status(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Get the status of a Z-Wave JS node."""
    connection.send_result(msg[ID], node_status(node))


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/node_metadata",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_node_metadata(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
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
        vol.Required(TYPE): "zwave_js/node_alerts",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
async def websocket_node_alerts(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the alerts for a Z-Wave JS node."""
    try:
        node = async_get_node_from_device_id(hass, msg[DEVICE_ID])
    except ValueError as err:
        if "can't be found" in err.args[0]:
            provisioning_entry = await async_get_provisioning_entry_from_device_id(
                hass, msg[DEVICE_ID]
            )
            if provisioning_entry:
                connection.send_result(
                    msg[ID],
                    {
                        "comments": [
                            {
                                "level": "info",
                                "text": "This device has been provisioned but is not yet included in the "
                                "network.",
                            }
                        ],
                    },
                )
            else:
                connection.send_error(msg[ID], ERR_NOT_FOUND, str(err))
        else:
            connection.send_error(msg[ID], ERR_NOT_LOADED, str(err))
        return

    connection.send_result(
        msg[ID],
        {
            "comments": node.device_config.metadata.comments,
            "is_embedded": node.device_config.is_embedded,
        },
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
        vol.Exclusive(DSK, "options"): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_add_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Add a node to the Z-Wave network."""
    controller = driver.controller
    inclusion_strategy = InclusionStrategy(msg[INCLUSION_STRATEGY])
    force_security = msg.get(FORCE_SECURITY)
    provisioning = (
        msg.get(PLANNED_PROVISIONING_ENTRY)
        or msg.get(QR_PROVISIONING_INFORMATION)
        or msg.get(QR_CODE_STRING)
    )
    dsk = msg.get(DSK)

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
    def forward_node_added(
        node: Node, low_security: bool, low_security_reason: str | None
    ) -> None:
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
            "low_security": low_security,
            "low_security_reason": low_security_reason,
        }
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node added", "node": node_details}
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
    def node_found(event: dict) -> None:
        node = event["node"]
        node_details = {
            "node_id": node["nodeId"],
        }
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node found", "node": node_details}
            )
        )

    @callback
    def node_added(event: dict) -> None:
        forward_node_added(
            event["node"],
            event["result"].get("lowSecurity", False),
            event["result"].get("lowSecurityReason"),
        )

    @callback
    def device_registered(device: dr.DeviceEntry) -> None:
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
    unsubs: list[Callable[[], None]] = [
        controller.on("inclusion started", forward_event),
        controller.on("inclusion failed", forward_event),
        controller.on("inclusion stopped", forward_event),
        controller.on("validate dsk and enter pin", forward_dsk),
        controller.on("grant security classes", forward_requested_grant),
        controller.on("node found", node_found),
        controller.on("node added", node_added),
        async_dispatcher_connect(
            hass, EVENT_DEVICE_ADDED_TO_REGISTRY, device_registered
        ),
    ]
    msg[DATA_UNSUBSCRIBE] = unsubs

    if controller.inclusion_state in (InclusionState.INCLUDING, InclusionState.BUSY):
        connection.send_result(
            msg[ID],
            True,  # Inclusion is already in progress
        )
        # Check for nodes that have been added but not fully included
        for node in controller.nodes.values():
            if node.status != NodeStatus.DEAD and not node.ready:
                forward_node_added(
                    node,
                    not node.is_secure,
                    None,
                )
    else:
        try:
            result = await controller.async_begin_inclusion(
                INCLUSION_STRATEGY_NOT_SMART_START[inclusion_strategy.value],
                force_security=force_security,
                provisioning=provisioning,
                dsk=dsk,
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
        vol.Required(TYPE): "zwave_js/cancel_secure_bootstrap_s2",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_cancel_secure_bootstrap_s2(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Cancel secure bootstrap S2."""
    await driver.controller.async_cancel_secure_bootstrap_s2()
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_s2_inclusion",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_subscribe_s2_inclusion(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Subscribe to S2 inclusion initiated by the controller."""

    @callback
    def async_cleanup() -> None:
        for unsub in unsubs:
            unsub()

    @callback
    def forward_dsk(event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": event["event"], "dsk": event["dsk"]}
            )
        )

    @callback
    def handle_requested_grant(event: dict) -> None:
        """Accept the requested security classes without user interaction."""
        hass.async_create_task(
            driver.controller.async_grant_security_classes(event["requested_grant"])
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [
        driver.controller.on("grant security classes", handle_requested_grant),
        driver.controller.on("validate dsk and enter pin", forward_dsk),
    ]
    connection.send_result(msg[ID])


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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Choose SecurityClass grants as part of S2 inclusion process."""
    inclusion_grant = InclusionGrant(
        [SecurityClass(sec_cls) for sec_cls in msg[SECURITY_CLASSES]],
        msg[CLIENT_SIDE_AUTH],
    )
    await driver.controller.async_grant_security_classes(inclusion_grant)
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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Validate DSK and enter PIN as part of S2 inclusion process."""
    await driver.controller.async_validate_dsk_and_enter_pin(msg[PIN])
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_new_devices",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
async def websocket_subscribe_new_devices(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to new devices."""

    @callback
    def async_cleanup() -> None:
        for unsub in unsubs:
            unsub()

    @callback
    def device_registered(device: dr.DeviceEntry) -> None:
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
        async_dispatcher_connect(
            hass, EVENT_DEVICE_ADDED_TO_REGISTRY, device_registered
        ),
    ]
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/provision_smart_start_node",
        vol.Required(ENTRY_ID): str,
        vol.Required(QR_PROVISIONING_INFORMATION): QR_PROVISIONING_INFORMATION_SCHEMA,
        vol.Optional(PROTOCOL): vol.Coerce(Protocols),
        vol.Optional(DEVICE_NAME): str,
        vol.Optional(AREA_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_provision_smart_start_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Pre-provision a smart start node."""
    qr_info = msg[QR_PROVISIONING_INFORMATION]

    if qr_info.version == QRCodeVersion.S2:
        connection.send_error(
            msg[ID],
            ERR_INVALID_FORMAT,
            "QR code version S2 is not supported for this command",
        )
        return

    provisioning_info = ProvisioningEntry(
        dsk=qr_info.dsk,
        security_classes=qr_info.security_classes,
        requested_security_classes=qr_info.requested_security_classes,
        protocol=msg.get(PROTOCOL),
        additional_properties=qr_info.additional_properties,
    )

    device = None
    # Create an empty device if device_name is provided
    if device_name := msg.get(DEVICE_NAME):
        dev_reg = dr.async_get(hass)

        # Create a unique device identifier using the DSK
        device_identifier = (DOMAIN, f"provision_{qr_info.dsk}")

        manufacturer = None
        model = None

        device_info = await driver.config_manager.lookup_device(
            qr_info.manufacturer_id,
            qr_info.product_type,
            qr_info.product_id,
        )
        if device_info:
            manufacturer = device_info.manufacturer
            model = device_info.label

        # Create an empty device
        device = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={device_identifier},
            name=device_name,
            manufacturer=manufacturer,
            model=model,
            via_device=get_device_id(driver, driver.controller.own_node)
            if driver.controller.own_node
            else None,
        )
        dev_reg.async_update_device(
            device.id, area_id=msg.get(AREA_ID), name_by_user=device_name
        )

        if provisioning_info.additional_properties is None:
            provisioning_info.additional_properties = {}
        provisioning_info.additional_properties["device_id"] = device.id

    await driver.controller.async_provision_smart_start_node(provisioning_info)
    if device:
        connection.send_result(msg[ID], device.id)
    else:
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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
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
    provisioning_entry = await driver.controller.async_get_provisioning_entry(
        dsk_or_node_id
    )
    if (
        provisioning_entry
        and provisioning_entry.additional_properties
        and "device_id" in provisioning_entry.additional_properties
    ):
        device_identifier = (DOMAIN, f"provision_{provisioning_entry.dsk}")
        device_id = provisioning_entry.additional_properties["device_id"]
        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(device_id)
        if device and device.identifiers == {device_identifier}:
            # Only remove the device if nothing else has claimed it
            dev_reg.async_remove_device(device_id)

    await driver.controller.async_unprovision_smart_start_node(dsk_or_node_id)

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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Get provisioning entries (entries that have been pre-provisioned)."""
    provisioning_entries = await driver.controller.async_get_provisioning_entries()
    connection.send_result(msg[ID], [entry.to_dict() for entry in provisioning_entries])


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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Parse a QR Code String and return QRProvisioningInformation dict."""
    qr_provisioning_information = await async_parse_qr_code_string(
        client, msg[QR_CODE_STRING]
    )
    connection.send_result(msg[ID], qr_provisioning_information.to_dict())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/try_parse_dsk_from_qr_code_string",
        vol.Required(ENTRY_ID): str,
        vol.Required(QR_CODE_STRING): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_try_parse_dsk_from_qr_code_string(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Try to parse a DSK string from a QR code."""
    connection.send_result(
        msg[ID],
        await async_try_parse_dsk_from_qr_code_string(client, msg[QR_CODE_STRING]),
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/lookup_device",
        vol.Required(ENTRY_ID): str,
        vol.Required(MANUFACTURER_ID): int,
        vol.Required(PRODUCT_TYPE): int,
        vol.Required(PRODUCT_ID): int,
        vol.Optional(APPLICATION_VERSION): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_lookup_device(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Look up the definition of a given device in the configuration DB."""
    device = await driver.config_manager.lookup_device(
        msg[MANUFACTURER_ID],
        msg[PRODUCT_TYPE],
        msg[PRODUCT_ID],
        msg.get(APPLICATION_VERSION),
    )
    if device is None:
        connection.send_error(msg[ID], ERR_NOT_FOUND, "Device not found")
    else:
        connection.send_result(msg[ID], device.to_dict())


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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Check if controller supports a particular feature."""
    supported = await driver.controller.async_supports_feature(msg[FEATURE])
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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Cancel adding a node to the Z-Wave network."""
    controller = driver.controller
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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Cancel removing a node from the Z-Wave network."""
    controller = driver.controller
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
        vol.Optional(STRATEGY): vol.Coerce(ExclusionStrategy),
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_remove_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Remove a node from the Z-Wave network."""
    controller = driver.controller

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
            "reason": event["reason"],
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

    result = await controller.async_begin_exclusion(msg.get(STRATEGY))
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/replace_failed_node",
        vol.Required(DEVICE_ID): str,
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
@async_get_node
async def websocket_replace_failed_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Replace a failed node with a new node."""
    assert node.client.driver
    controller = node.client.driver.controller
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
    def node_found(event: dict) -> None:
        node = event["node"]
        node_details = {
            "node_id": node["nodeId"],
        }
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node found", "node": node_details}
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
    def device_registered(device: dr.DeviceEntry) -> None:
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
    unsubs: list[Callable[[], None]] = [
        controller.on("inclusion started", forward_event),
        controller.on("inclusion failed", forward_event),
        controller.on("inclusion stopped", forward_event),
        controller.on("validate dsk and enter pin", forward_dsk),
        controller.on("grant security classes", forward_requested_grant),
        controller.on("node removed", node_removed),
        controller.on("node found", node_found),
        controller.on("node added", node_added),
        async_dispatcher_connect(
            hass, EVENT_DEVICE_ADDED_TO_REGISTRY, device_registered
        ),
    ]
    msg[DATA_UNSUBSCRIBE] = unsubs

    try:
        result = await controller.async_replace_failed_node(
            node,
            INCLUSION_STRATEGY_NOT_SMART_START[inclusion_strategy.value],
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
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_remove_failed_node(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Remove a failed node from the Z-Wave network."""
    driver = node.client.driver
    assert driver is not None  # The node comes from the driver instance.
    controller = driver.controller

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def node_removed(event: dict) -> None:
        node_details = {"node_id": event["node"].node_id}

        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": "node removed", "node": node_details}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [controller.on("node removed", node_removed)]

    await controller.async_remove_failed_node(node)
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/begin_rebuilding_routes",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_begin_rebuilding_routes(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Begin rebuilding Z-Wave routes."""
    controller = driver.controller

    result = await controller.async_begin_rebuilding_routes()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_rebuild_routes_progress",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_get_entry
async def websocket_subscribe_rebuild_routes_progress(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Subscribe to rebuild Z-Wave routes status updates."""
    controller = driver.controller

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(key: str, event: dict) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg[ID], {"event": event["event"], "rebuild_routes_status": event[key]}
            )
        )

    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [
        controller.on("rebuild routes progress", partial(forward_event, "progress")),
        controller.on("rebuild routes done", partial(forward_event, "result")),
    ]

    if controller.rebuild_routes_progress:
        connection.send_result(
            msg[ID],
            {
                node.node_id: status
                for node, status in controller.rebuild_routes_progress.items()
            },
        )
    else:
        connection.send_result(msg[ID], None)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/stop_rebuilding_routes",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_stop_rebuilding_routes(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Stop rebuilding Z-Wave routes."""
    controller = driver.controller
    result = await controller.async_stop_rebuilding_routes()
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/rebuild_node_routes",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_rebuild_node_routes(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Heal a node on the Z-Wave network."""
    driver = node.client.driver
    assert driver is not None  # The node comes from the driver instance.
    controller = driver.controller

    result = await controller.async_rebuild_node_routes(node)
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/refresh_node_info",
        vol.Required(DEVICE_ID): str,
    },
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_refresh_node_info(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
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

    await node.async_refresh_info()
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/refresh_node_values",
        vol.Required(DEVICE_ID): str,
    },
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_refresh_node_values(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Refresh node values."""
    await node.async_refresh_values()
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/refresh_node_cc_values",
        vol.Required(DEVICE_ID): str,
        vol.Required(COMMAND_CLASS_ID): int,
    },
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_refresh_node_cc_values(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
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
        vol.Required(DEVICE_ID): str,
        vol.Required(PROPERTY): int,
        vol.Optional(ENDPOINT, default=0): int,
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
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Set a config parameter value for a Z-Wave node."""
    property_ = msg[PROPERTY]
    endpoint = msg[ENDPOINT]
    property_key = msg.get(PROPERTY_KEY)
    value = msg[VALUE]

    try:
        zwave_value, cmd_status = await async_set_config_parameter(
            node, value, property_, property_key=property_key, endpoint=endpoint
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
            STATUS: cmd_status.status,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/get_config_parameters",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_get_config_parameters(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any], node: Node
) -> None:
    """Get a list of configuration parameters for a Z-Wave node."""
    values = node.get_configuration_values()
    result: dict[str, Any] = {}
    for value_id, zwave_value in values.items():
        metadata = zwave_value.metadata
        result[value_id] = {
            "property": zwave_value.property_,
            "property_key": zwave_value.property_key,
            "endpoint": zwave_value.endpoint,
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
                "default": metadata.default,
            },
            "value": zwave_value.value,
        }
        if zwave_value.metadata.states:
            result[value_id]["metadata"]["states"] = zwave_value.metadata.states

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/set_raw_config_parameter",
        vol.Required(DEVICE_ID): str,
        vol.Required(PROPERTY): int,
        vol.Required(VALUE): int,
        vol.Required(VALUE_SIZE): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
        vol.Required(VALUE_FORMAT): vol.Coerce(ConfigurationValueFormat),
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_set_raw_config_parameter(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Set a custom config parameter value for a Z-Wave node."""
    result = await node.async_set_raw_config_parameter_value(
        msg[VALUE],
        msg[PROPERTY],
        value_size=msg[VALUE_SIZE],
        value_format=msg[VALUE_FORMAT],
    )

    connection.send_result(
        msg[ID],
        {
            STATUS: result.status,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/get_raw_config_parameter",
        vol.Required(DEVICE_ID): str,
        vol.Required(PROPERTY): int,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_get_raw_config_parameter(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Get a custom config parameter value for a Z-Wave node."""
    value = await node.async_get_raw_config_parameter_value(
        msg[PROPERTY],
    )

    connection.send_result(
        msg[ID],
        {
            VALUE: value,
        },
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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Subscribe to log message events from the server."""

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        hass.async_create_task(client.async_stop_listening_logs())
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

    await client.async_start_listening_logs()
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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Update the driver log config."""
    await driver.async_update_log_config(LogConfig(**msg[CONFIG]))
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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Get log configuration for the Z-Wave JS driver."""
    assert client and client.driver
    connection.send_result(
        msg[ID],
        dataclasses.asdict(driver.log_config),
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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Update preference for data collection and enable/disable collection."""
    opted_in = msg[OPTED_IN]
    if entry.data.get(CONF_DATA_COLLECTION_OPTED_IN) != opted_in:
        new_data = entry.data.copy()
        new_data[CONF_DATA_COLLECTION_OPTED_IN] = opted_in
        hass.config_entries.async_update_entry(entry, data=new_data)

    if opted_in:
        await async_enable_statistics(driver)
    else:
        await driver.async_disable_statistics()

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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Return data collection preference and status."""
    assert client and client.driver
    result = {
        OPTED_IN: entry.data.get(CONF_DATA_COLLECTION_OPTED_IN),
        ENABLED: await driver.async_is_statistics_enabled(),
    }
    connection.send_result(msg[ID], result)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/abort_firmware_update",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_abort_firmware_update(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Abort a firmware update."""
    await node.async_abort_firmware_update()
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/is_node_firmware_update_in_progress",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_is_node_firmware_update_in_progress(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Get whether firmware update is in progress for given node."""
    connection.send_result(msg[ID], await node.async_is_firmware_update_in_progress())


def _get_node_firmware_update_progress_dict(
    progress: NodeFirmwareUpdateProgress,
) -> dict[str, int | float]:
    """Get a dictionary of a node's firmware update progress."""
    return {
        "current_file": progress.current_file,
        "total_files": progress.total_files,
        "sent_fragments": progress.sent_fragments,
        "total_fragments": progress.total_fragments,
        "progress": progress.progress,
    }


def _get_controller_firmware_update_progress_dict(
    progress: ControllerFirmwareUpdateProgress,
) -> dict[str, int | float]:
    """Get a dictionary of a controller's firmware update progress."""
    return {
        "current_file": 1,
        "total_files": 1,
        "sent_fragments": progress.sent_fragments,
        "total_fragments": progress.total_fragments,
        "progress": progress.progress,
    }


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_firmware_update_status",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_subscribe_firmware_update_status(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Subscribe to the status of a firmware update."""
    assert node.client.driver
    controller = node.client.driver.controller

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_node_progress(event: dict) -> None:
        progress: NodeFirmwareUpdateProgress = event["firmware_update_progress"]
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    **_get_node_firmware_update_progress_dict(progress),
                },
            )
        )

    @callback
    def forward_node_finished(event: dict) -> None:
        finished: NodeFirmwareUpdateResult = event["firmware_update_finished"]
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    "status": finished.status,
                    "success": finished.success,
                    "wait_time": finished.wait_time,
                    "reinterview": finished.reinterview,
                },
            )
        )

    @callback
    def forward_controller_progress(event: dict) -> None:
        progress: ControllerFirmwareUpdateProgress = event["firmware_update_progress"]
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    **_get_controller_firmware_update_progress_dict(progress),
                },
            )
        )

    @callback
    def forward_controller_finished(event: dict) -> None:
        finished: ControllerFirmwareUpdateResult = event["firmware_update_finished"]
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    "status": finished.status,
                    "success": finished.success,
                },
            )
        )

    if controller.own_node == node:
        msg[DATA_UNSUBSCRIBE] = unsubs = [
            controller.on("firmware update progress", forward_controller_progress),
            controller.on("firmware update finished", forward_controller_finished),
        ]
    else:
        msg[DATA_UNSUBSCRIBE] = unsubs = [
            node.on("firmware update progress", forward_node_progress),
            node.on("firmware update finished", forward_node_finished),
        ]
    connection.subscriptions[msg["id"]] = async_cleanup

    connection.send_result(msg[ID])
    if node.is_controller_node and (
        controller_progress := controller.firmware_update_progress
    ):
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": "firmware update progress",
                    **_get_controller_firmware_update_progress_dict(
                        controller_progress
                    ),
                },
            )
        )
    elif controller.own_node != node and (
        node_progress := node.firmware_update_progress
    ):
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": "firmware update progress",
                    **_get_node_firmware_update_progress_dict(node_progress),
                },
            )
        )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/get_node_firmware_update_capabilities",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_get_node_firmware_update_capabilities(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Get a node's firmware update capabilities."""
    capabilities = await node.async_get_firmware_update_capabilities()
    connection.send_result(msg[ID], capabilities.to_dict())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/is_any_ota_firmware_update_in_progress",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_is_any_ota_firmware_update_in_progress(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Get whether any firmware updates are in progress."""
    connection.send_result(
        msg[ID], await driver.controller.async_is_any_ota_firmware_update_in_progress()
    )


class FirmwareUploadView(HomeAssistantView):
    """View to upload firmware."""

    url = r"/api/zwave_js/firmware/upload/{device_id}"
    name = "api:zwave_js:firmware:upload"

    def __init__(self, dev_reg: dr.DeviceRegistry) -> None:
        """Initialize view."""
        super().__init__()
        self._dev_reg = dev_reg

    @require_admin
    async def post(self, request: web.Request, device_id: str) -> web.Response:
        """Handle upload."""
        hass = request.app[KEY_HASS]

        try:
            node = async_get_node_from_device_id(hass, device_id, self._dev_reg)
        except ValueError as err:
            if "not loaded" in err.args[0]:
                raise web_exceptions.HTTPBadRequest from err
            raise web_exceptions.HTTPNotFound from err

        # If this was not true, we wouldn't have been able to get the node from the
        # device ID above
        assert node.client.driver

        # Increase max payload
        request._client_max_size = 1024 * 1024 * 10  # noqa: SLF001

        data = await request.post()

        if "file" not in data or not isinstance(data["file"], web_request.FileField):
            raise web_exceptions.HTTPBadRequest

        uploaded_file: web_request.FileField = data["file"]

        try:
            if node.client.driver.controller.own_node == node:
                await controller_firmware_update_otw(
                    node.client.ws_server_url,
                    ControllerFirmwareUpdateData(
                        uploaded_file.filename,
                        await hass.async_add_executor_job(uploaded_file.file.read),
                    ),
                    async_get_clientsession(hass),
                    additional_user_agent_components=USER_AGENT,
                )
            else:
                firmware_target: int | None = None
                if "target" in data:
                    firmware_target = int(cast(str, data["target"]))
                await update_firmware(
                    node.client.ws_server_url,
                    node,
                    [
                        NodeFirmwareUpdateData(
                            uploaded_file.filename,
                            await hass.async_add_executor_job(uploaded_file.file.read),
                            firmware_target=firmware_target,
                        )
                    ],
                    async_get_clientsession(hass),
                    additional_user_agent_components=USER_AGENT,
                )
        except BaseZwaveJSServerError as err:
            raise web_exceptions.HTTPBadRequest(reason=str(err)) from err

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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Check for config updates."""
    config_update = await driver.async_check_for_config_updates()
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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Check for config updates."""
    success = await driver.async_install_config_update()
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
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Subscribe to the statistics updates for a controller."""

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

    controller = driver.controller

    msg[DATA_UNSUBSCRIBE] = unsubs = [
        controller.on("statistics updated", forward_stats)
    ]
    connection.subscriptions[msg["id"]] = async_cleanup

    connection.send_result(msg[ID])
    connection.send_message(
        websocket_api.event_message(
            msg[ID],
            {
                "event": "statistics updated",
                "source": "controller",
                **_get_controller_statistics_dict(controller.statistics),
            },
        )
    )


def _get_node_statistics_dict(
    hass: HomeAssistant, statistics: NodeStatistics
) -> dict[str, Any]:
    """Get dictionary of node statistics."""
    dev_reg = dr.async_get(hass)

    def _convert_node_to_device_id(node: Node) -> str:
        """Convert a node to a device id."""
        driver = node.client.driver
        assert driver
        device = dev_reg.async_get_device(identifiers={get_device_id(driver, node)})
        assert device
        return device.id

    data: dict = {
        "commands_tx": statistics.commands_tx,
        "commands_rx": statistics.commands_rx,
        "commands_dropped_tx": statistics.commands_dropped_tx,
        "commands_dropped_rx": statistics.commands_dropped_rx,
        "timeout_response": statistics.timeout_response,
        "rtt": statistics.rtt,
        "rssi": statistics.rssi,
        "lwr": statistics.lwr.as_dict() if statistics.lwr else None,
        "nlwr": statistics.nlwr.as_dict() if statistics.nlwr else None,
    }
    for key in ("lwr", "nlwr"):
        if not data[key]:
            continue
        for key_2 in ("repeaters", "route_failed_between"):
            if not data[key][key_2]:
                continue
            data[key][key_2] = [
                _convert_node_to_device_id(node) for node in data[key][key_2]
            ]

    return data


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/subscribe_node_statistics",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_get_node
async def websocket_subscribe_node_statistics(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Subscribe to the statistics updates for a node."""

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
                    **_get_node_statistics_dict(hass, statistics),
                },
            )
        )

    msg[DATA_UNSUBSCRIBE] = unsubs = [node.on("statistics updated", forward_stats)]
    connection.subscriptions[msg["id"]] = async_cleanup

    connection.send_result(msg[ID])
    connection.send_message(
        websocket_api.event_message(
            msg[ID],
            {
                "event": "statistics updated",
                "source": "node",
                "nodeId": node.node_id,
                **_get_node_statistics_dict(hass, node.statistics),
            },
        )
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/hard_reset_controller",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_hard_reset_controller(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Hard reset controller."""
    unsubs: list[Callable[[], None]]

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()
        unsubs.clear()

    @callback
    def _handle_device_added(device: dr.DeviceEntry) -> None:
        """Handle device is added."""
        if entry.entry_id in device.config_entries:
            connection.send_result(msg[ID], device.id)
            async_cleanup()

    @callback
    def set_driver_ready(event: dict) -> None:
        "Set the driver ready event."
        wait_driver_ready.set()

    wait_driver_ready = asyncio.Event()

    msg[DATA_UNSUBSCRIBE] = unsubs = [
        async_dispatcher_connect(
            hass, EVENT_DEVICE_ADDED_TO_REGISTRY, _handle_device_added
        ),
        driver.once("driver ready", set_driver_ready),
    ]

    await driver.async_hard_reset()

    with suppress(TimeoutError):
        async with asyncio.timeout(HARD_RESET_CONTROLLER_DRIVER_READY_TIMEOUT):
            await wait_driver_ready.wait()

    await hass.config_entries.async_reload(entry.entry_id)


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/node_capabilities",
        vol.Required(DEVICE_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_node_capabilities(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Get node endpoints with their support command classes."""
    # consumers expect snake_case at the moment
    # remove that addition when consumers are updated
    connection.send_result(
        msg[ID],
        {
            idx: [
                command_class.to_dict() | {"is_secure": command_class.is_secure}
                for command_class in endpoint.command_classes
            ]
            for idx, endpoint in node.endpoints.items()
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/invoke_cc_api",
        vol.Required(DEVICE_ID): str,
        vol.Required(ATTR_COMMAND_CLASS): vol.All(
            vol.Coerce(int), vol.Coerce(CommandClass)
        ),
        vol.Optional(ATTR_ENDPOINT): vol.Coerce(int),
        vol.Required(ATTR_METHOD_NAME): cv.string,
        vol.Required(ATTR_PARAMETERS): list,
        vol.Optional(ATTR_WAIT_FOR_RESULT): cv.boolean,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_node
async def websocket_invoke_cc_api(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    node: Node,
) -> None:
    """Call invokeCCAPI on the node or provided endpoint."""
    command_class: CommandClass = msg[ATTR_COMMAND_CLASS]
    method_name: str = msg[ATTR_METHOD_NAME]
    parameters: list[Any] = msg[ATTR_PARAMETERS]

    node_or_endpoint: Node | Endpoint = node
    if (endpoint := msg.get(ATTR_ENDPOINT)) is not None:
        node_or_endpoint = node.endpoints[endpoint]

    try:
        result = await node_or_endpoint.async_invoke_cc_api(
            command_class,
            method_name,
            *parameters,
            wait_for_result=msg.get(ATTR_WAIT_FOR_RESULT, False),
        )
    except BaseZwaveJSServerError as err:
        connection.send_error(msg[ID], err.__class__.__name__, str(err))
    else:
        connection.send_result(
            msg[ID],
            result,
        )


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/get_integration_settings",
    }
)
def websocket_get_integration_settings(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get Z-Wave JS integration wide configuration."""
    connection.send_result(
        msg[ID],
        {
            # list explicitly to avoid leaking other keys and to set default
            CONF_INSTALLER_MODE: hass.data[DOMAIN].get(CONF_INSTALLER_MODE, False),
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/backup_nvm",
        vol.Required(ENTRY_ID): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_backup_nvm(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Backup NVM data."""
    controller = driver.controller

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_progress(event: dict) -> None:
        """Forward progress events to websocket."""
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    "bytesRead": event["bytesRead"],
                    "total": event["total"],
                },
            )
        )

    # Set up subscription for progress events
    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [
        controller.on("nvm backup progress", forward_progress),
    ]

    result = await controller.async_backup_nvm_raw_base64()
    # Send the finished event with the backup data
    connection.send_message(
        websocket_api.event_message(
            msg[ID],
            {
                "event": "finished",
                "data": result,
            },
        )
    )
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "zwave_js/restore_nvm",
        vol.Required(ENTRY_ID): str,
        vol.Required("data"): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_entry
async def websocket_restore_nvm(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    entry: ConfigEntry,
    client: Client,
    driver: Driver,
) -> None:
    """Restore NVM data."""
    controller = driver.controller

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_progress(event: dict) -> None:
        """Forward progress events to websocket."""
        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event["event"],
                    "bytesRead": event.get("bytesRead"),
                    "bytesWritten": event.get("bytesWritten"),
                    "total": event["total"],
                },
            )
        )

    @callback
    def set_driver_ready(event: dict) -> None:
        "Set the driver ready event."
        wait_driver_ready.set()

    wait_driver_ready = asyncio.Event()

    # Set up subscription for progress events
    connection.subscriptions[msg["id"]] = async_cleanup
    msg[DATA_UNSUBSCRIBE] = unsubs = [
        controller.on("nvm convert progress", forward_progress),
        controller.on("nvm restore progress", forward_progress),
        driver.once("driver ready", set_driver_ready),
    ]

    await controller.async_restore_nvm_base64(msg["data"])

    with suppress(TimeoutError):
        async with asyncio.timeout(RESTORE_NVM_DRIVER_READY_TIMEOUT):
            await wait_driver_ready.wait()
    await hass.config_entries.async_reload(entry.entry_id)

    connection.send_message(
        websocket_api.event_message(
            msg[ID],
            {
                "event": "finished",
            },
        )
    )
    connection.send_result(msg[ID])
