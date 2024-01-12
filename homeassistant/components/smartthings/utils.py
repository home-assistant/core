"""Shared functionality to serve multiple HA components."""
from pysmartthings import DeviceStatusBase


def format_component_name(
    prefix: str, suffix: str, component_id: str | None, delimiter: str = " "
) -> str:
    """Format component name according to convention."""
    parts = [prefix]

    if component_id is not None:
        parts.append(component_id)

    parts.append(suffix)

    component_name = delimiter.join(parts)

    return component_name


def get_device_status(device, component_id: str | None) -> DeviceStatusBase:
    """Choose the status object based on device and component id."""
    status = device.status

    if component_id is not None:
        status = status.components[component_id]

    return status


def get_device_attributes(device) -> dict[str | None, list[str] | None]:
    """Construct list of components related to a device."""
    result: dict[str | None, list[str] | None] = {}
    device_components_keys = list(device.status.components.keys())

    components_keys = [None]

    if len(device_components_keys) > 1:
        components_keys.extend(device_components_keys)

    disabled_components = device.status.attributes["disabledComponents"]

    for component_key in components_keys:
        if component_key is not None and component_key in disabled_components:
            continue

        component_id = None
        component_attributes = None

        if component_key is not None:
            component = device.status.components[component_key]
            component_id = component.component_id
            component_attributes = list(component.attributes.keys())

        result[component_id] = component_attributes

    return result
