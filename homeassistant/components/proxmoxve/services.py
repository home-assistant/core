"""Services for Proxmox VE."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from time import monotonic
from typing import Any, Final

from proxmoxer import AuthenticationError, ProxmoxAPI
from proxmoxer.core import ResourceException
import requests
from requests.exceptions import ConnectTimeout, SSLError
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import CONF_NODE, DOMAIN, ProxmoxPermission
from .coordinator import ProxmoxCoordinator
from .helpers import is_granted

SERVICE_VM_COMMAND_WAIT: Final = "vm_command_wait"
CONF_COMMAND: Final = "command"
CONF_ENTRY_ID: Final = "entry_id"
CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_RESOURCE_TYPE: Final = "resource_type"
CONF_TIMEOUT: Final = "timeout"
CONF_VMID: Final = "vmid"

RESOURCE_QEMU: Final = "qemu"
RESOURCE_LXC: Final = "lxc"

SUPPORTED_COMMANDS: Final[dict[str, dict[str, Callable[[Any], Any]]]] = {
    RESOURCE_QEMU: {
        "start": lambda resource: resource.status.start.post(),
        "stop": lambda resource: resource.status.stop.post(),
        "shutdown": lambda resource: resource.status.shutdown.post(),
        "restart": lambda resource: resource.status.reboot.post(),
        "reset": lambda resource: resource.status.reset.post(),
        "hibernate": lambda resource: resource.status.hibernate.post(),
    },
    RESOURCE_LXC: {
        "start": lambda resource: resource.status.start.post(),
        "stop": lambda resource: resource.status.stop.post(),
        "shutdown": lambda resource: resource.status.shutdown.post(),
        "restart": lambda resource: resource.status.reboot.post(),
    },
}

SERVICE_VM_COMMAND_WAIT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NODE): cv.string,
        vol.Required(CONF_VMID): cv.positive_int,
        vol.Required(CONF_COMMAND): vol.In(
            sorted(
                {
                    command
                    for commands in SUPPORTED_COMMANDS.values()
                    for command in commands
                }
            )
        ),
        vol.Optional(CONF_RESOURCE_TYPE, default=RESOURCE_QEMU): vol.In(
            (RESOURCE_QEMU, RESOURCE_LXC)
        ),
        vol.Optional(CONF_ENTRY_ID): cv.string,
        vol.Optional(CONF_TIMEOUT, default=120): vol.All(
            vol.Coerce(float), vol.Range(min=1, max=3600)
        ),
        vol.Optional(CONF_POLL_INTERVAL, default=1): vol.All(
            vol.Coerce(float), vol.Range(min=0.2, max=30)
        ),
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Proxmox VE services."""
    if hass.services.has_service(DOMAIN, SERVICE_VM_COMMAND_WAIT):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_VM_COMMAND_WAIT,
        _async_vm_command_wait,
        schema=SERVICE_VM_COMMAND_WAIT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def _async_vm_command_wait(call: ServiceCall) -> ServiceResponse:
    """Run a VM or container command and wait for the task to complete."""
    node = call.data[CONF_NODE]
    vmid = call.data[CONF_VMID]
    resource_type = call.data[CONF_RESOURCE_TYPE]
    command = call.data[CONF_COMMAND]
    timeout = float(call.data[CONF_TIMEOUT])
    poll_interval = float(call.data[CONF_POLL_INTERVAL])

    if command not in SUPPORTED_COMMANDS[resource_type]:
        raise ServiceValidationError(
            f"Command '{command}' is not supported for resource type '{resource_type}'."
        )

    coordinator = _resolve_coordinator(call.hass, node, call.data.get(CONF_ENTRY_ID))
    _validate_target_and_permissions(coordinator, node, vmid, resource_type)

    try:
        upid = await call.hass.async_add_executor_job(
            _execute_command,
            coordinator.proxmox,
            node,
            vmid,
            resource_type,
            command,
        )
        await coordinator.async_refresh()

        task_status = await _wait_for_task(
            call.hass,
            coordinator.proxmox,
            node,
            upid,
            timeout,
            poll_interval,
        )
        await coordinator.async_refresh()
    except AuthenticationError as err:
        raise HomeAssistantError(
            "Authentication failed while talking to Proxmox."
        ) from err
    except SSLError as err:
        raise HomeAssistantError("SSL error while talking to Proxmox.") from err
    except ConnectTimeout as err:
        raise HomeAssistantError("Timed out while talking to Proxmox.") from err
    except (ResourceException, requests.exceptions.ConnectionError) as err:
        raise HomeAssistantError(f"Proxmox API error: {err}") from err
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    exitstatus = str(task_status.get("exitstatus", ""))
    if exitstatus != "OK":
        raise HomeAssistantError(
            f"Proxmox task {upid} failed with exit status '{exitstatus or 'unknown'}'."
        )

    return {
        "command": command,
        "entry_id": coordinator.config_entry.entry_id,
        "exitstatus": exitstatus,
        "node": node,
        "resource_type": resource_type,
        "status": task_status.get("status"),
        "upid": upid,
        "vmid": vmid,
    }


async def _wait_for_task(
    hass: HomeAssistant,
    proxmox: ProxmoxAPI,
    node: str,
    upid: str,
    timeout: float,
    poll_interval: float,
) -> dict[str, Any]:
    """Wait for a Proxmox task to finish and return the final status."""
    deadline = monotonic() + timeout

    while True:
        task_status = await hass.async_add_executor_job(
            _get_task_status,
            proxmox,
            node,
            upid,
        )
        if task_status.get("status") != "running":
            return task_status

        if monotonic() >= deadline:
            raise HomeAssistantError(
                f"Timed out waiting for Proxmox task {upid} to finish."
            )

        await asyncio.sleep(poll_interval)


def _resolve_coordinator(
    hass: HomeAssistant,
    node: str,
    entry_id: str | None,
) -> ProxmoxCoordinator:
    """Resolve the coordinator for a given node and optional config entry id."""
    entries = hass.config_entries.async_entries(DOMAIN)

    if entry_id is not None:
        for entry in entries:
            if entry.entry_id != entry_id:
                continue
            coordinator = getattr(entry, "runtime_data", None)
            if coordinator is None:
                raise ServiceValidationError(
                    f"Config entry '{entry_id}' is not loaded for Proxmox VE."
                )
            if node not in coordinator.data:
                raise ServiceValidationError(
                    f"Node '{node}' is not managed by config entry '{entry_id}'."
                )
            return coordinator
        raise ServiceValidationError(f"Config entry '{entry_id}' was not found.")

    matches: list[ProxmoxCoordinator] = []
    for entry in entries:
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator is not None and node in coordinator.data:
            matches.append(coordinator)

    if not matches:
        raise ServiceValidationError(
            f"Node '{node}' is not managed by any Proxmox VE entry."
        )

    if len(matches) > 1:
        raise ServiceValidationError(
            f"Node '{node}' exists in multiple Proxmox VE entries; provide entry_id."
        )

    return matches[0]


def _validate_target_and_permissions(
    coordinator: ProxmoxCoordinator,
    node: str,
    vmid: int,
    resource_type: str,
) -> None:
    """Validate that the target exists and the configured user can control it."""
    node_data = coordinator.data[node]
    resources = (
        node_data.vms if resource_type == RESOURCE_QEMU else node_data.containers
    )

    if vmid not in resources:
        raise ServiceValidationError(
            f"{resource_type.upper()} '{vmid}' was not found on node '{node}'."
        )

    if not is_granted(
        coordinator.permissions,
        p_type="vms",
        p_id=vmid,
        permission=ProxmoxPermission.POWER,
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_permission_vm_lxc_power",
        )


def _execute_command(
    proxmox: ProxmoxAPI,
    node: str,
    vmid: int,
    resource_type: str,
    command: str,
) -> str:
    """Execute a VM or container command and return the task UPID."""
    resource = (
        proxmox.nodes(node).qemu(vmid)
        if resource_type == RESOURCE_QEMU
        else proxmox.nodes(node).lxc(vmid)
    )
    response = SUPPORTED_COMMANDS[resource_type][command](resource)
    return _extract_upid(response)


def _get_task_status(
    proxmox: ProxmoxAPI,
    node: str,
    upid: str,
) -> dict[str, Any]:
    """Fetch the current status for a Proxmox task."""
    status = proxmox.nodes(node).tasks(upid).status.get()
    if not isinstance(status, dict):
        raise ValueError(f"Unexpected task status response for Proxmox task {upid!r}.")
    return status


def _extract_upid(response: Any) -> str:
    """Extract the Proxmox task UPID from a command response."""
    if isinstance(response, str) and response:
        return response

    if isinstance(response, dict):
        upid = response.get("data") or response.get("upid") or response.get("taskid")
        if isinstance(upid, str) and upid:
            return upid

    raise ValueError("Proxmox command did not return a task UPID.")
