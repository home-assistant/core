"""Map LOIP components to Home Assistant entities by capability."""

from aiolanbon.models import Component, Device, DeviceSnapshot


def is_switch_component(component: Component) -> bool:
    """Return True when LOIP declares type=switch and set_on."""
    return component.type == "switch" and "set_on" in component.commands


def iter_switch_components(
    snapshot: DeviceSnapshot | None,
) -> list[tuple[Device, Component]]:
    """Return switch components from a snapshot."""
    if snapshot is None:
        return []
    rows: list[tuple[Device, Component]] = []
    for device in snapshot.devices:
        rows.extend(
            (device, component)
            for component in device.components
            if is_switch_component(component)
        )
    return rows
