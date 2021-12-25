"""Button to set Proxmox VE data."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import ProxmoxClient, ProxmoxEntity, call_api_post_status, compile_device_info
from .const import (
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_VMS,
    COORDINATORS,
    DOMAIN,
    PROXMOX_BUTTON_TYPES,
    PROXMOX_CLIENTS,
    Node_Type,
)
from .model import ProxmoxButtonDescription


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up button."""
    if discovery_info is None:
        return

    buttons = []

    for host_config in discovery_info["config"][DOMAIN]:
        host_name = host_config[CONF_HOST]
        host_name_coordinators = hass.data[DOMAIN][COORDINATORS][host_name]

        if hass.data[PROXMOX_CLIENTS][host_name] is None:
            continue

        proxmox_client = hass.data[PROXMOX_CLIENTS][host_name]

        for node_config in host_config[CONF_NODES]:
            node_name = node_config[CONF_NODE]

            for vm_id in node_config[CONF_VMS]:
                coordinator = host_name_coordinators[node_name][vm_id]

                # unfound vm case
                if (coordinator_data := coordinator.data) is None:
                    continue

                vm_name = coordinator_data["name"]
                device_info = compile_device_info(host_name, node_name, vm_id, vm_name)

                for description in PROXMOX_BUTTON_TYPES:
                    buttons.append(
                        create_button(
                            coordinator=coordinator,
                            device_info=device_info,
                            description=description,
                            node_name=node_name,
                            mid=vm_id,
                            name=vm_name,
                            proxmox_client=proxmox_client,
                            machine_type=Node_Type.TYPE_VM,
                        )
                    )

            for ct_id in node_config[CONF_CONTAINERS]:
                coordinator = host_name_coordinators[node_name][ct_id]

                # unfound container case
                if (coordinator_data := coordinator.data) is None:
                    continue

                ct_name = coordinator_data["name"]
                device_info = compile_device_info(host_name, node_name, ct_id, ct_name)
                for description in PROXMOX_BUTTON_TYPES:
                    buttons.append(
                        create_button(
                            coordinator=coordinator,
                            device_info=device_info,
                            description=description,
                            node_name=node_name,
                            mid=ct_id,
                            name=ct_name,
                            proxmox_client=proxmox_client,
                            machine_type=Node_Type.TYPE_CONTAINER,
                        )
                    )

    add_entities(buttons)


def create_button(
    coordinator: DataUpdateCoordinator,
    device_info: DeviceInfo,
    description: ProxmoxButtonDescription,
    node_name: str,
    mid: str,
    name: str,
    proxmox_client: ProxmoxClient,
    machine_type: Node_Type,
):
    """Create a button based on the given data."""
    return ProxmoxButton(
        coordinator=coordinator,
        device_info=device_info,
        description=description,
        unique_id=f"proxmox_{node_name}_{mid}_{description.key}",
        name=f"{node_name}_{name}_{description.key}",
        proxmox_client=proxmox_client,
        node_name=node_name,
        vm_id=mid,
        machine_type=machine_type,
    )


class ProxmoxButton(ProxmoxEntity, ButtonEntity):
    """A button for reading/writing Proxmox VE status."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: DeviceInfo,
        description: ProxmoxButtonDescription,
        name: str,
        unique_id: str,
        proxmox_client: ProxmoxClient,
        node_name: str,
        vm_id: str,
        machine_type: Node_Type,
    ):
        """Create the button for vms or containers."""
        super().__init__(
            coordinator=coordinator,
            device_info=device_info,
            name=name,
            unique_id=unique_id,
        )
        self.entity_description = description

        def _button_press():
            """Post start command & tell HA state is on."""
            call_api_post_status(
                proxmox_client.get_api_client(),
                node_name,
                vm_id,
                machine_type,
                description.key,
            )

        self._button_press_funct = _button_press

    @property
    def available(self):
        """Return sensor availability."""
        return super().available and self.coordinator.data is not None

    def press(self) -> None:
        """Press the button."""
        self._button_press_funct()
