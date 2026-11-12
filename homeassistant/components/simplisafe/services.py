"""Services for SimpliSafe."""

from collections.abc import Callable, Coroutine
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import probatio
from simplipy.errors import SimplipyError
from simplipy.system.v3 import (
    MAX_ALARM_DURATION,
    MAX_ENTRY_DELAY_AWAY,
    MAX_ENTRY_DELAY_HOME,
    MAX_EXIT_DELAY_AWAY,
    MAX_EXIT_DELAY_HOME,
    MIN_ALARM_DURATION,
    MIN_ENTRY_DELAY_AWAY,
    MIN_EXIT_DELAY_AWAY,
    SystemV3,
    Volume,
)

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.service import (
    async_get_device_and_config_entry,
    async_register_admin_service,
    verify_domain_control,
)

from .const import DOMAIN
from .typing import SystemType

if TYPE_CHECKING:
    from . import SimpliSafeConfigEntry


class SimpliSafeService(StrEnum):
    """Store keys for SimpliSafe services."""

    REMOVE_PIN = "remove_pin"
    SET_PIN = "set_pin"
    SET_SYSTEM_PROPERTIES = "set_system_properties"


class SimpliSafeServiceArgument(StrEnum):
    """Store keys for SimpliSafe service arguments."""

    LABEL_OR_PIN = "label_or_pin"
    LABEL = "label"
    PIN = "pin"
    ALARM_DURATION = "alarm_duration"
    ALARM_VOLUME = "alarm_volume"
    CHIME_VOLUME = "chime_volume"
    ENTRY_DELAY_AWAY = "entry_delay_away"
    ENTRY_DELAY_HOME = "entry_delay_home"
    EXIT_DELAY_AWAY = "exit_delay_away"
    EXIT_DELAY_HOME = "exit_delay_home"
    LIGHT = "light"
    VOICE_PROMPT_VOLUME = "voice_prompt_volume"


VOLUME_MAP = {
    "high": Volume.HIGH,
    "low": Volume.LOW,
    "medium": Volume.MEDIUM,
    "off": Volume.OFF,
}


SERVICE_REMOVE_PIN_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Required(SimpliSafeServiceArgument.LABEL_OR_PIN): cv.string,
    }
)

SERVICE_SET_PIN_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Required(SimpliSafeServiceArgument.LABEL): cv.string,
        probatio.Required(SimpliSafeServiceArgument.PIN): cv.string,
    },
)

SERVICE_SET_SYSTEM_PROPERTIES_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Optional(SimpliSafeServiceArgument.ALARM_DURATION): probatio.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            probatio.Range(min=MIN_ALARM_DURATION, max=MAX_ALARM_DURATION),
        ),
        probatio.Optional(SimpliSafeServiceArgument.ALARM_VOLUME): probatio.All(
            probatio.In(VOLUME_MAP), VOLUME_MAP.get
        ),
        probatio.Optional(SimpliSafeServiceArgument.CHIME_VOLUME): probatio.All(
            probatio.In(VOLUME_MAP), VOLUME_MAP.get
        ),
        probatio.Optional(SimpliSafeServiceArgument.ENTRY_DELAY_AWAY): probatio.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            probatio.Range(min=MIN_ENTRY_DELAY_AWAY, max=MAX_ENTRY_DELAY_AWAY),
        ),
        probatio.Optional(SimpliSafeServiceArgument.ENTRY_DELAY_HOME): probatio.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            probatio.Range(max=MAX_ENTRY_DELAY_HOME),
        ),
        probatio.Optional(SimpliSafeServiceArgument.EXIT_DELAY_AWAY): probatio.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            probatio.Range(min=MIN_EXIT_DELAY_AWAY, max=MAX_EXIT_DELAY_AWAY),
        ),
        probatio.Optional(SimpliSafeServiceArgument.EXIT_DELAY_HOME): probatio.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            probatio.Range(max=MAX_EXIT_DELAY_HOME),
        ),
        probatio.Optional(SimpliSafeServiceArgument.LIGHT): cv.boolean,
        probatio.Optional(SimpliSafeServiceArgument.VOICE_PROMPT_VOLUME): probatio.All(
            probatio.In(VOLUME_MAP), VOLUME_MAP.get
        ),
    }
)

_verify_domain_control = verify_domain_control(DOMAIN)


@callback
def _async_get_system_for_service_call(call: ServiceCall) -> SystemType:
    """Get the SimpliSafe system related to a service call (by device ID)."""
    device_id = call.data[CommonServiceArgument.DEVICE_ID]
    device_registry = dr.async_get(call.hass)

    if (
        alarm_control_panel_device_entry := device_registry.async_get(
            device_id, include_child_devices=False
        )
    ) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
            translation_placeholders={"device_id": device_id},
        )

    if TYPE_CHECKING:
        assert alarm_control_panel_device_entry.via_device_id

    config_entry: SimpliSafeConfigEntry
    base_station_device_entry, config_entry = async_get_device_and_config_entry(
        call.hass, DOMAIN, alarm_control_panel_device_entry.via_device_id
    )

    [system_id_str] = [
        identity[1]
        for identity in base_station_device_entry.identifiers
        if identity[0] == DOMAIN
    ]

    return config_entry.runtime_data.systems[int(system_id_str)]


@callback
def extract_system(
    func: Callable[[ServiceCall, SystemType], Coroutine[Any, Any, None]],
) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
    """Define a decorator to get the correct system for a service call."""

    async def wrapper(call: ServiceCall) -> None:
        """Wrap the service function."""
        system = _async_get_system_for_service_call(call)

        try:
            await func(call, system)
        except SimplipyError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_while_executing",
                translation_placeholders={"service": call.service, "error": str(err)},
            ) from err

    return wrapper


@_verify_domain_control
@extract_system
async def async_remove_pin(call: ServiceCall, system: SystemType) -> None:
    """Remove a PIN."""
    await system.async_remove_pin(call.data[SimpliSafeServiceArgument.LABEL_OR_PIN])


@_verify_domain_control
@extract_system
async def async_set_pin(call: ServiceCall, system: SystemType) -> None:
    """Set a PIN."""
    await system.async_set_pin(
        call.data[SimpliSafeServiceArgument.LABEL],
        call.data[SimpliSafeServiceArgument.PIN],
    )


@_verify_domain_control
@extract_system
async def async_set_system_properties(call: ServiceCall, system: SystemType) -> None:
    """Set one or more system parameters."""
    if not isinstance(system, SystemV3):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="set_system_properties_not_v3",
        )

    await system.async_set_properties(
        {
            prop: value
            for prop, value in call.data.items()
            if prop != CommonServiceArgument.DEVICE_ID
        }
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    for service, method, schema in (
        (SimpliSafeService.REMOVE_PIN, async_remove_pin, SERVICE_REMOVE_PIN_SCHEMA),
        (SimpliSafeService.SET_PIN, async_set_pin, SERVICE_SET_PIN_SCHEMA),
        (
            SimpliSafeService.SET_SYSTEM_PROPERTIES,
            async_set_system_properties,
            SERVICE_SET_SYSTEM_PROPERTIES_SCHEMA,
        ),
    ):
        async_register_admin_service(hass, DOMAIN, service, method, schema=schema)
