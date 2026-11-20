"""Services for Matter devices."""

from collections.abc import Callable
from typing import Any, cast

from chip.clusters.Types import NullValue
from matter_server.client.exceptions import MatterClientException
from matter_server.client.models.node import MatterEndpoint, MatterNode
from matter_server.common.errors import MatterError
from matter_server.common.models import ServerInfoMessage
import probatio
from python_otbr_api import tlv_parser

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.thread import (
    async_get_dataset,
    async_get_dataset_id,
    async_get_preferred_dataset,
)
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)
from homeassistant.util.json import JsonValueType

from .adapter import MatterAdapter
from .const import (
    CLEAR_ALL_INDEX,
    CREDENTIAL_RULE_REVERSE_MAP,
    CREDENTIAL_TYPE_REVERSE_MAP,
    DOMAIN,
    ID_TYPE_DEVICE_ID,
    LOGGER,
    MIGRATED,
    SERVICE_CREDENTIAL_TYPES,
    USER_TYPE_REVERSE_MAP,
    MatterService,
    MatterServiceArgument,
)
from .helpers import (
    MissingNode,
    get_child_device_identifier,
    get_child_device_owner,
    get_device_id,
    get_matter,
    node_from_ha_device_id,
)
from .thread_border_router import (
    async_push_dataset,
    async_read_dataset,
    async_read_dataset_timestamps,
    async_run_on_entry,
    get_border_router_endpoints,
)
from .thread_migration import (
    async_fleet_migration,
    async_migrate_device,
    get_migration_order,
    get_thread_network_endpoint,
)


def _get_matter(call: ServiceCall) -> MatterAdapter:
    """Return the Matter adapter; raise when Matter is not loaded."""
    try:
        return get_matter(call.hass)
    except IndexError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="matter_not_set_up"
        ) from err


async def _async_set_wifi_credentials(call: ServiceCall) -> None:
    """Set the Wi-Fi network the Matter server commissions devices onto."""
    matter = _get_matter(call)
    try:
        await matter.matter_client.set_wifi_credentials(
            ssid=call.data[MatterServiceArgument.SSID],
            credentials=call.data[MatterServiceArgument.PASSWORD],
        )
    except (MatterError, MatterClientException) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="wifi_credentials_set_failed",
            translation_placeholders={"error": str(err) or err.__class__.__name__},
        ) from err


def _resolve_device(
    call: ServiceCall, matter: MatterAdapter
) -> tuple[MatterNode, Callable[[MatterEndpoint], bool]]:
    """Return the node of the chosen device and a test for its own endpoints.

    The test tells the endpoints the device stands for from those of bridged
    devices and child devices on the same node.
    """
    device_id = call.data[ATTR_DEVICE_ID]
    try:
        node = node_from_ha_device_id(call.hass, device_id)
    except MissingNode:
        node = None
    if node is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device",
            translation_placeholders={"device_id": device_id},
        )
    # The node lookup above found the device, a child device included.
    device = cast(dr.AnyDeviceEntry, dr.async_get(call.hass).async_get(device_id))
    identifiers = set(device.identifiers)
    server_info = cast(ServerInfoMessage, matter.matter_client.server_info)

    def is_own(endpoint: MatterEndpoint) -> bool:
        # An endpoint split into a child device stands for that one.
        if (owner := get_child_device_owner(endpoint)) is not None:
            return get_child_device_identifier(server_info, owner) in identifiers
        device_id = get_device_id(server_info, endpoint)
        return (DOMAIN, f"{ID_TYPE_DEVICE_ID}_{device_id}") in identifiers

    return node, is_own


def _resolve_border_router(call: ServiceCall, matter: MatterAdapter) -> MatterEndpoint:
    """Return the border router endpoint of the chosen device."""
    node, is_own = _resolve_device(call, matter)
    endpoints = [e for e in get_border_router_endpoints(node) if is_own(e)]
    if len(endpoints) != 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_a_border_router"
        )
    return endpoints[0]


async def _dataset_from_call(call: ServiceCall) -> bytes:
    """Return the stored dataset the call names, by default the preferred network.

    The call names a dataset of the Thread store rather than carrying one: a
    dataset holds the network key, and action data is recorded.
    """
    if (dataset_id := call.data.get(MatterServiceArgument.DATASET_ID)) is None:
        if (dataset := await async_get_preferred_dataset(call.hass)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_preferred_dataset"
            )
    elif (dataset := await async_get_dataset(call.hass, dataset_id)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_dataset",
            translation_placeholders={"dataset_id": dataset_id},
        )
    return bytes.fromhex(dataset)


async def _async_push_thread_dataset(call: ServiceCall) -> None:
    """Hand a dataset, by default the preferred network, to a border router."""
    matter = _get_matter(call)
    endpoint = _resolve_border_router(call, matter)
    dataset = await _dataset_from_call(call)
    await async_run_on_entry(
        call.hass,
        matter.config_entry,
        async_push_dataset(call.hass, matter.matter_client, endpoint, dataset),
        f"matter_push_thread_dataset_{endpoint.node.node_id}",
    )


async def _async_network_details(
    hass: HomeAssistant, dataset: bytes, tag: tlv_parser.MeshcopTLVType
) -> dict[str, Any]:
    """Return what tells a dataset's network apart, without its network key.

    `tag` names the dataset's own timestamp: the active or the pending one.
    """
    try:
        tlvs = tlv_parser.parse_tlv(dataset.hex())
    except tlv_parser.TLVError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="thread_dataset_unusable"
        ) from err
    types = tlv_parser.MeshcopTLVType
    name, channel = tlvs.get(types.NETWORKNAME), tlvs.get(types.CHANNEL)
    extended_pan_id = (
        item.data.hex() if (item := tlvs.get(types.EXTPANID)) is not None else None
    )
    return {
        "network_name": name.name if isinstance(name, tlv_parser.NetworkName) else None,
        "extended_pan_id": extended_pan_id,
        "pan_id": item.data.hex()
        if (item := tlvs.get(types.PANID)) is not None
        else None,
        "channel": channel.channel if isinstance(channel, tlv_parser.Channel) else None,
        "timestamp": (
            int.from_bytes(item.data, "big")
            if (item := tlvs.get(tag)) is not None
            else None
        ),
        "dataset_id": (
            await async_get_dataset_id(hass, extended_pan_id)
            if extended_pan_id is not None
            else None
        ),
    }


async def _async_get_thread_dataset(call: ServiceCall) -> ServiceResponse:
    """Return the networks of a border router: the active one, and the pending one.

    Each is told by its name, extended PAN ID, PAN ID, channel, timestamp and
    the ID of the dataset Home Assistant stores for it. The datasets hold the
    network key, which an automation using the response would record in its
    trace, so they are not returned; and only those whose timestamp says they
    exist are read.
    """
    matter = _get_matter(call)
    endpoint = _resolve_border_router(call, matter)
    try:
        active, pending = await async_read_dataset_timestamps(
            matter.matter_client, endpoint
        )
    except (MatterError, MatterClientException) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="thread_dataset_read_failed",
            translation_placeholders={"error": str(err) or err.__class__.__name__},
        ) from err
    response: dict[str, Any] = {}
    for kind, timestamp, tag in (
        ("active", active, tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP),
        ("pending", pending, tlv_parser.MeshcopTLVType.PENDINGTIMESTAMP),
    ):
        response[kind] = None
        if timestamp in (None, NullValue):
            continue
        try:
            dataset = await async_read_dataset(
                matter.matter_client, endpoint, pending=kind == "pending"
            )
        except (MatterError, MatterClientException) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="thread_dataset_read_failed",
                translation_placeholders={"error": str(err) or err.__class__.__name__},
            ) from err
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="thread_dataset_unusable"
            ) from err
        if dataset:
            response[kind] = await _async_network_details(call.hass, dataset, tag)
    return response


def _resolve_thread_device(call: ServiceCall, matter: MatterAdapter) -> MatterEndpoint:
    """Return the Thread network endpoint of the chosen device."""
    node, is_own = _resolve_device(call, matter)
    endpoint = get_thread_network_endpoint(node)
    # A border router is the network, not a device on it.
    if endpoint is None or get_border_router_endpoints(node) or not is_own(endpoint):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_a_thread_device"
        )
    return endpoint


async def _async_migrate_thread_device(call: ServiceCall) -> ServiceResponse:
    """Move a Thread device onto a network, by default the preferred one."""
    matter = _get_matter(call)
    endpoint = _resolve_thread_device(call, matter)
    dataset = await _dataset_from_call(call)
    result = await async_run_on_entry(
        call.hass,
        matter.config_entry,
        async_migrate_device(call.hass, matter.matter_client, endpoint, dataset),
        f"matter_migrate_thread_device_{endpoint.node.node_id}",
    )
    return {"result": result}


async def _async_migrate_fleet(
    hass: HomeAssistant, matter: MatterAdapter, dataset: bytes
) -> dict[str, list[dict[str, JsonValueType]]]:
    """Move the Thread devices one at a time, end devices first.

    Once a device fails to move, the devices of a later tier are held back,
    and after a router-capable device the rest of its tier too: moving the
    routers a failed device depends on could strand it on a network that is
    gone. Offline devices do not hold the others back.
    """
    queue: list[tuple[int, int, MatterEndpoint]] = []
    report: dict[str, list[dict[str, JsonValueType]]] = {
        "migrated": [],
        "skipped": [],
        "failed": [],
        "held_back": [],
    }
    for node in matter.matter_client.get_nodes():
        node_id = node.node_id
        endpoint = get_thread_network_endpoint(node)
        if endpoint is None or get_border_router_endpoints(node):
            continue
        if not node.available:
            report["failed"].append(
                {"name": node.name, "node_id": node_id, "reason": "offline"}
            )
        else:
            queue.append((get_migration_order(endpoint), node_id, endpoint))

    queue.sort(key=lambda item: item[:2])
    failed_order: int | None = None
    async with async_fleet_migration(hass):
        for index, (order, node_id, endpoint) in enumerate(queue, start=1):
            entry: dict[str, JsonValueType] = {
                "name": endpoint.node.name,
                "node_id": node_id,
            }
            if failed_order is not None and (
                order > failed_order or (order == failed_order and order > 0)
            ):
                report["held_back"].append(entry)
                continue
            LOGGER.debug(
                "Moving node %s (%d of %d) to the Thread network",
                node_id,
                index,
                len(queue),
            )
            try:
                result = await async_migrate_device(
                    hass, matter.matter_client, endpoint, dataset, in_fleet=True
                )
            except HomeAssistantError as err:
                LOGGER.debug("Could not move node %s: %s", node_id, err)
                # A code automations can match, not a message that is
                # translated and reworded.
                report["failed"].append(
                    {**entry, "reason": err.translation_key or "failed"}
                )
                if failed_order is None:
                    failed_order = order
            else:
                report["migrated" if result == MIGRATED else "skipped"].append(entry)
    return report


async def _async_migrate_thread_fleet(call: ServiceCall) -> ServiceResponse:
    """Move every Thread device onto a network, by default the preferred one.

    Devices already there are skipped and border routers left alone; end
    devices go before the routers they depend on, which a device that fails
    to move holds back, and offline ones are reported as failed. One fleet
    migration runs at a time. Running it again picks up the devices that
    were not moved, which fail the action unless its response is asked for.
    """
    matter = _get_matter(call)
    dataset = await _dataset_from_call(call)
    report = await async_run_on_entry(
        call.hass,
        matter.config_entry,
        _async_migrate_fleet(call.hass, matter, dataset),
        "matter_migrate_thread_fleet",
    )
    if (report["failed"] or report["held_back"]) and not call.return_response:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="thread_migration_incomplete",
            translation_placeholders={
                "devices": ", ".join(
                    str(entry["name"] or entry["node_id"])
                    for entry in report["failed"] + report["held_back"]
                )
            },
        )
    return {
        kind: cast(list[JsonValueType], entries) for kind, entries in report.items()
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Matter services."""

    service.async_register_admin_service(
        hass,
        DOMAIN,
        MatterService.SET_WIFI_CREDENTIALS,
        _async_set_wifi_credentials,
        schema=probatio.Schema(
            {
                probatio.Required(MatterServiceArgument.SSID): cv.string,
                probatio.Required(MatterServiceArgument.PASSWORD): cv.string,
            }
        ),
    )
    service.async_register_admin_service(
        hass,
        DOMAIN,
        MatterService.PUSH_THREAD_DATASET,
        _async_push_thread_dataset,
        schema=probatio.Schema(
            {
                probatio.Required(ATTR_DEVICE_ID): cv.string,
                probatio.Optional(MatterServiceArgument.DATASET_ID): cv.string,
            }
        ),
    )
    service.async_register_admin_service(
        hass,
        DOMAIN,
        MatterService.GET_THREAD_DATASET,
        _async_get_thread_dataset,
        schema=probatio.Schema({probatio.Required(ATTR_DEVICE_ID): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    service.async_register_admin_service(
        hass,
        DOMAIN,
        MatterService.MIGRATE_THREAD_DEVICE,
        _async_migrate_thread_device,
        schema=probatio.Schema(
            {
                probatio.Required(ATTR_DEVICE_ID): cv.string,
                probatio.Optional(MatterServiceArgument.DATASET_ID): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    service.async_register_admin_service(
        hass,
        DOMAIN,
        MatterService.MIGRATE_THREAD_FLEET,
        _async_migrate_thread_fleet,
        schema=probatio.Schema(
            {probatio.Optional(MatterServiceArgument.DATASET_ID): cv.string}
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.WATER_HEATER_BOOST,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            # duration >=1
            probatio.Required(MatterServiceArgument.DURATION): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1)
            ),
            probatio.Optional(MatterServiceArgument.EMERGENCY_BOOST): cv.boolean,
            probatio.Optional(MatterServiceArgument.TEMPORARY_SETPOINT): probatio.All(
                probatio.Coerce(int), probatio.Range(min=30, max=65)
            ),
        },
        func="async_set_boost",
    )

    # Lock services - Full user CRUD
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.SET_LOCK_USER,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Optional(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1)
            ),
            probatio.Optional(MatterServiceArgument.USER_NAME): probatio.Any(str, None),
            probatio.Optional(MatterServiceArgument.USER_TYPE): probatio.In(
                USER_TYPE_REVERSE_MAP.keys()
            ),
            probatio.Optional(MatterServiceArgument.CREDENTIAL_RULE): probatio.In(
                CREDENTIAL_RULE_REVERSE_MAP.keys()
            ),
        },
        func="async_set_lock_user",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.CLEAR_LOCK_USER,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int),
                probatio.Any(probatio.Range(min=1), CLEAR_ALL_INDEX),
            ),
        },
        func="async_clear_lock_user",
    )

    # Lock services - Query operations
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.GET_LOCK_INFO,
        entity_domain=LOCK_DOMAIN,
        schema={},
        func="async_get_lock_info",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.GET_LOCK_USERS,
        entity_domain=LOCK_DOMAIN,
        schema={},
        func="async_get_lock_users",
        supports_response=SupportsResponse.ONLY,
    )

    # Lock services - Credential management
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.SET_LOCK_CREDENTIAL,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(MatterServiceArgument.CREDENTIAL_TYPE): probatio.In(
                SERVICE_CREDENTIAL_TYPES
            ),
            probatio.Required(MatterServiceArgument.CREDENTIAL_DATA): cv.string,
            probatio.Optional(MatterServiceArgument.CREDENTIAL_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0)
            ),
            probatio.Optional(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1)
            ),
            probatio.Optional(MatterServiceArgument.USER_STATUS): probatio.In(
                ["occupied_enabled", "occupied_disabled"]
            ),
            probatio.Optional(MatterServiceArgument.USER_TYPE): probatio.In(
                USER_TYPE_REVERSE_MAP.keys()
            ),
        },
        func="async_set_lock_credential",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.CLEAR_LOCK_CREDENTIAL,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(MatterServiceArgument.CREDENTIAL_TYPE): probatio.In(
                SERVICE_CREDENTIAL_TYPES
            ),
            probatio.Required(MatterServiceArgument.CREDENTIAL_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0)
            ),
        },
        func="async_clear_lock_credential",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.GET_LOCK_CREDENTIAL_STATUS,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(MatterServiceArgument.CREDENTIAL_TYPE): probatio.In(
                CREDENTIAL_TYPE_REVERSE_MAP.keys()
            ),
            probatio.Required(MatterServiceArgument.CREDENTIAL_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0)
            ),
        },
        func="async_get_lock_credential_status",
        supports_response=SupportsResponse.ONLY,
    )
