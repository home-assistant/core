"""Helpers for Daikin demand control."""

from homeassistant.exceptions import HomeAssistantError

from .const import DAIKIN_DEMAND_CONTROL_MODES, DOMAIN
from .coordinator import DaikinCoordinator


def get_demand_control_mode(attrs: dict[str, str]) -> str | None:
    """Return the configured demand control mode."""
    mode_value = attrs.get("mode")
    if mode_value is None or not mode_value.isdigit():
        return None

    mode = int(mode_value)
    return next(
        (name for name, value in DAIKIN_DEMAND_CONTROL_MODES.items() if value == mode),
        None,
    )


def get_demand_control_option(attrs: dict[str, str]) -> str | None:
    """Return the active demand control option."""
    match attrs.get("en_demand"):
        case "0":
            return "off"
        case "1":
            return get_demand_control_mode(attrs)
        case _:
            return None


def get_demand_control_max_power(attrs: dict[str, str]) -> int | None:
    """Return the configured maximum power."""
    max_power = attrs.get("max_pow")
    if max_power is None or not max_power.isdigit():
        return None
    return int(max_power)


async def async_update_demand_control(
    coordinator: DaikinCoordinator,
    *,
    enabled: bool,
    max_power: int,
    mode: str,
) -> None:
    """Update the demand control settings and refresh device data."""
    async with coordinator.demand_control_lock:
        await _async_update_demand_control(
            coordinator, enabled=enabled, max_power=max_power, mode=mode
        )


async def async_select_demand_control_option(
    coordinator: DaikinCoordinator, option: str
) -> None:
    """Select a demand control option while preserving other settings."""
    async with coordinator.demand_control_lock:
        attrs = coordinator.device.get_demand_control()
        mode = (
            get_demand_control_mode(attrs) if option == "off" else option
        ) or "manual"
        max_power = get_demand_control_max_power(attrs)
        await _async_update_demand_control(
            coordinator,
            enabled=option != "off",
            max_power=100 if max_power is None else max_power,
            mode=mode,
        )


async def async_set_demand_control_max_power(
    coordinator: DaikinCoordinator, max_power: int
) -> None:
    """Set maximum power while preserving the other demand control settings."""
    async with coordinator.demand_control_lock:
        enabled, mode = demand_control_write_state(
            coordinator.device.get_demand_control()
        )
        await _async_update_demand_control(
            coordinator, enabled=enabled, max_power=max_power, mode=mode
        )


async def _async_update_demand_control(
    coordinator: DaikinCoordinator,
    *,
    enabled: bool,
    max_power: int,
    mode: str,
) -> None:
    """Update demand control; the caller must hold the coordinator lock."""
    device = coordinator.device
    if not device.support_demand_control:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="demand_control_unsupported",
        )

    await device.set_demand_control(
        en_demand="on" if enabled else "off",
        max_pow=max_power,
        mode=DAIKIN_DEMAND_CONTROL_MODES[mode],
    )
    await coordinator.async_refresh()


def demand_control_write_state(attrs: dict[str, str]) -> tuple[bool, str]:
    """Return the enabled state and configured mode for a number write."""
    mode = get_demand_control_mode(attrs)
    enabled = attrs.get("en_demand")
    if mode is None or enabled not in ("0", "1"):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="demand_control_invalid_state",
        )
    return enabled == "1", mode
