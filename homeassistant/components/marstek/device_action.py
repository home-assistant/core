"""Device actions for Marstek integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pymarstek import build_command, get_es_mode
import voluptuous as vol

from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_HOST, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DEFAULT_UDP_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Action type constants
ACTION_CHARGE = "charge"
ACTION_DISCHARGE = "discharge"
ACTION_STOP = "stop"

ACTION_TYPES = {ACTION_CHARGE, ACTION_DISCHARGE, ACTION_STOP}

# Command constants from pymarstek
CMD_ES_SET_MODE = "ES.SetMode"

# Retry configuration
MAX_RETRY_ATTEMPTS = 8
RETRY_TIMEOUTS = [2.4, 3.2, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
RETRY_BACKOFF_BASES = [0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8]

# Verification configuration
VERIFICATION_ATTEMPTS = 5
VERIFICATION_TIMEOUT = 2.4
VERIFICATION_DELAY = 0.5
STOP_POWER_THRESHOLD = 50  # W

# Action power settings
CHARGE_POWER = -1300  # W (negative for charging)
DISCHARGE_POWER = 800  # W (positive for discharging)
STOP_POWER = 0  # W

# Manual mode configuration
MANUAL_MODE_START_TIME = "00:00"
MANUAL_MODE_END_TIME = "23:59"
MANUAL_MODE_WEEK_SET = 127  # All days of week

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): vol.In((DOMAIN,)),
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Optional("entity_id"): cv.entity_id,
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for a Marstek device."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if not device:
        return []

    if not any(ident[0] == DOMAIN for ident in device.identifiers):
        return []

    base_action = {
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    return [{CONF_TYPE: action_type} | base_action for action_type in ACTION_TYPES]


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    action_type: str = config[CONF_TYPE]
    device_id: str = config[CONF_DEVICE_ID]

    host = await _get_host_from_device(hass, device_id)
    if not host:
        raise InvalidDeviceAutomationConfig(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": device_id},
        )

    power, enable = _get_action_parameters(action_type)
    command = _build_set_mode_command(power, enable)

    runtime_data = _get_runtime_data_from_device_id(hass, device_id)
    if not runtime_data:
        raise InvalidDeviceAutomationConfig(
            translation_domain=DOMAIN,
            translation_key="config_invalid",
            translation_placeholders={"device_id": device_id},
        )

    udp_client = runtime_data.udp_client

    await udp_client.pause_polling(host)
    try:
        for attempt_idx, (timeout, backoff_base) in enumerate(
            zip(RETRY_TIMEOUTS, RETRY_BACKOFF_BASES, strict=False), start=1
        ):
            try:
                await udp_client.send_request(
                    command,
                    host,
                    DEFAULT_UDP_PORT,
                    timeout=timeout,
                    quiet_on_timeout=True,
                )
            except (TimeoutError, OSError, ValueError) as err:
                _LOGGER.debug(
                    "ES.SetMode send attempt %d/%d failed for %s: %s",
                    attempt_idx,
                    MAX_RETRY_ATTEMPTS,
                    host,
                    err,
                )

            try:
                if await _verify_es_mode(hass, host, enable, power, udp_client):
                    _LOGGER.info(
                        "ES.SetMode action '%s' confirmed after attempt %d/%d for device %s",
                        action_type,
                        attempt_idx,
                        MAX_RETRY_ATTEMPTS,
                        host,
                    )
                    return
            except (TimeoutError, OSError, ValueError) as err:
                _LOGGER.debug(
                    "ES.SetMode verification attempt %d/%d failed for %s: %s",
                    attempt_idx,
                    MAX_RETRY_ATTEMPTS,
                    host,
                    err,
                )

            if attempt_idx < MAX_RETRY_ATTEMPTS:
                jitter = 0.30 * attempt_idx
                delay = backoff_base * attempt_idx + jitter
                _LOGGER.warning(
                    "ES.SetMode action '%s' not confirmed on attempt %d/%d for device %s, retrying in %.2fs",
                    action_type,
                    attempt_idx,
                    MAX_RETRY_ATTEMPTS,
                    host,
                    delay,
                )
                await asyncio.sleep(delay)

        raise TimeoutError(
            f"ES.SetMode action '{action_type}' not confirmed after {MAX_RETRY_ATTEMPTS} attempts for device {host}"
        )
    finally:
        await udp_client.resume_polling(host)


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    return {"extra_fields": vol.Schema({})}


def _get_action_parameters(action_type: str) -> tuple[int, int]:
    """Get power and enable parameters for an action type."""
    if action_type == ACTION_CHARGE:
        return CHARGE_POWER, 1
    if action_type == ACTION_DISCHARGE:
        return DISCHARGE_POWER, 1
    if action_type == ACTION_STOP:
        return STOP_POWER, 0
    raise ValueError(f"Unknown action type: {action_type}")


def _build_set_mode_command(power: int, enable: int) -> str:
    """Build ES.SetMode command with manual configuration."""
    payload = {
        "id": 0,
        "config": {
            "mode": "Manual",
            "manual_cfg": {
                "time_num": 0,
                "start_time": MANUAL_MODE_START_TIME,
                "end_time": MANUAL_MODE_END_TIME,
                "week_set": MANUAL_MODE_WEEK_SET,
                "power": power,
                "enable": enable,
            },
        },
    }
    return build_command(CMD_ES_SET_MODE, payload)


async def _verify_es_mode(
    hass: HomeAssistant,
    host: str,
    enable: int,
    power: int,
    udp_client: Any,
) -> bool:
    """Verify that ES mode matches expected state.

    Rules:
    - Mode should be "Manual"
    - enable=0 (stop): ongrid_power should be near zero (< 50W)
    - enable=1 and power<0 (charge): ongrid_power should be negative
    - enable=1 and power>0 (discharge): ongrid_power should be positive
    """
    for _ in range(VERIFICATION_ATTEMPTS):
        try:
            response = await udp_client.send_request(
                get_es_mode(0),
                host,
                DEFAULT_UDP_PORT,
                timeout=VERIFICATION_TIMEOUT,
                quiet_on_timeout=True,
            )
        except (TimeoutError, OSError, ValueError):
            await asyncio.sleep(0.4)
            continue

        result = response.get("result", {}) if isinstance(response, dict) else {}
        mode = result.get("mode")
        ongrid_power = result.get("ongrid_power")

        if mode != "Manual" or not isinstance(ongrid_power, (int, float)):
            await asyncio.sleep(VERIFICATION_DELAY)
            continue

        if enable == 0:
            if abs(ongrid_power) < STOP_POWER_THRESHOLD:
                return True
        elif enable == 1 and power < 0:
            if ongrid_power < 0:
                return True
        elif enable == 1 and power > 0:
            if ongrid_power > 0:
                return True

        await asyncio.sleep(VERIFICATION_DELAY)

    return False


async def _get_host_from_device(hass: HomeAssistant, device_id: str) -> str | None:
    """Resolve device IP address from device registry and config entries."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if not device:
        return None

    # Priority 1: Get host (IP address) from config entry
    # Identifiers store MAC addresses, not IP addresses, so we need the config entry
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN:
            host = entry.data.get(CONF_HOST)  # Use CONF_HOST constant for consistency
            if host:
                return host

    # Priority 2: Fallback to identifier if it looks like an IP address
    # (This should rarely happen, as identifiers are typically MAC addresses)
    for domain, identifier in device.identifiers:
        if domain == DOMAIN:
            # Basic check: if identifier contains dots, it might be an IP address
            # Otherwise it's likely a MAC address and we should skip it
            if "." in identifier:
                return identifier

    return None


def _get_runtime_data_from_device_id(hass: HomeAssistant, device_id: str) -> Any | None:
    """Get runtime data for a device ID."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if not device:
        return None

    for config_entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(config_entry_id)
        if (
            entry
            and entry.domain == DOMAIN
            and entry.state is ConfigEntryState.LOADED
            and hasattr(entry, "runtime_data")
        ):
            return entry.runtime_data

    return None
