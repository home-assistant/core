"""Anova utilities."""

from anova_wifi import AnovaPrecisionCooker


def serialize_device_list(devices: list[AnovaPrecisionCooker]) -> list[tuple[str, str]]:
    """Turn the device list into a serializable list that can be reconstructed."""
    return [(device.device_key, device.type) for device in devices]
