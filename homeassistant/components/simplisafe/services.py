"""Services for SimpliSafe."""

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

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
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.service import (
    async_register_admin_service,
    verify_domain_control,
)

from .const import (
    ATTR_ALARM_DURATION,
    ATTR_ALARM_VOLUME,
    ATTR_CHIME_VOLUME,
    ATTR_ENTRY_DELAY_AWAY,
    ATTR_ENTRY_DELAY_HOME,
    ATTR_EXIT_DELAY_AWAY,
    ATTR_EXIT_DELAY_HOME,
    ATTR_LIGHT,
    ATTR_VOICE_PROMPT_VOLUME,
    DOMAIN,
)
from .typing import SystemType

if TYPE_CHECKING:
    from . import SimpliSafeConfigEntry

ATTR_PIN_LABEL = "label"
ATTR_PIN_LABEL_OR_VALUE = "label_or_pin"
ATTR_PIN_VALUE = "pin"

VOLUME_MAP = {
    "high": Volume.HIGH,
    "low": Volume.LOW,
    "medium": Volume.MEDIUM,
    "off": Volume.OFF,
}

SERVICE_NAME_REMOVE_PIN = "remove_pin"
SERVICE_NAME_SET_PIN = "set_pin"
SERVICE_NAME_SET_SYSTEM_PROPERTIES = "set_system_properties"

SERVICE_REMOVE_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_PIN_LABEL_OR_VALUE): cv.string,
    }
)

SERVICE_SET_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_PIN_LABEL): cv.string,
        vol.Required(ATTR_PIN_VALUE): cv.string,
    },
)

SERVICE_SET_SYSTEM_PROPERTIES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_ALARM_DURATION): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=MIN_ALARM_DURATION, max=MAX_ALARM_DURATION),
        ),
        vol.Optional(ATTR_ALARM_VOLUME): vol.All(vol.In(VOLUME_MAP), VOLUME_MAP.get),
        vol.Optional(ATTR_CHIME_VOLUME): vol.All(vol.In(VOLUME_MAP), VOLUME_MAP.get),
        vol.Optional(ATTR_ENTRY_DELAY_AWAY): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=MIN_ENTRY_DELAY_AWAY, max=MAX_ENTRY_DELAY_AWAY),
        ),
        vol.Optional(ATTR_ENTRY_DELAY_HOME): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(max=MAX_ENTRY_DELAY_HOME),
        ),
        vol.Optional(ATTR_EXIT_DELAY_AWAY): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=MIN_EXIT_DELAY_AWAY, max=MAX_EXIT_DELAY_AWAY),
        ),
        vol.Optional(ATTR_EXIT_DELAY_HOME): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(max=MAX_EXIT_DELAY_HOME),
        ),
        vol.Optional(ATTR_LIGHT): cv.boolean,
        vol.Optional(ATTR_VOICE_PROMPT_VOLUME): vol.All(
            vol.In(VOLUME_MAP), VOLUME_MAP.get
        ),
    }
)

_verify_domain_control = verify_domain_control(DOMAIN)


@callback
def _async_get_system_for_service_call(call: ServiceCall) -> SystemType:
    """Get the SimpliSafe system related to a service call (by device ID)."""
    device_id = call.data[ATTR_DEVICE_ID]
    device_registry = dr.async_get(call.hass)

    if (
        alarm_control_panel_device_entry := device_registry.async_get(device_id)
    ) is None:
        raise vol.Invalid("Invalid device ID specified")

    assert alarm_control_panel_device_entry.via_device_id

    if (
        base_station_device_entry := device_registry.async_get(
            alarm_control_panel_device_entry.via_device_id
        )
    ) is None:
        raise ValueError("No base station registered for alarm control panel")

    [system_id_str] = [
        identity[1]
        for identity in base_station_device_entry.identifiers
        if identity[0] == DOMAIN
    ]
    system_id = int(system_id_str)

    entry: SimpliSafeConfigEntry | None
    for entry_id in base_station_device_entry.config_entries:
        if (
            (entry := call.hass.config_entries.async_get_entry(entry_id)) is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
        ):
            continue
        return entry.runtime_data.systems[system_id]

    raise ValueError(f"No system for device ID: {device_id}")


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
                f'Error while executing "{call.service}": {err}'
            ) from err

    return wrapper


@_verify_domain_control
@extract_system
async def async_remove_pin(call: ServiceCall, system: SystemType) -> None:
    """Remove a PIN."""
    await system.async_remove_pin(call.data[ATTR_PIN_LABEL_OR_VALUE])


@_verify_domain_control
@extract_system
async def async_set_pin(call: ServiceCall, system: SystemType) -> None:
    """Set a PIN."""
    await system.async_set_pin(call.data[ATTR_PIN_LABEL], call.data[ATTR_PIN_VALUE])


@_verify_domain_control
@extract_system
async def async_set_system_properties(call: ServiceCall, system: SystemType) -> None:
    """Set one or more system parameters."""
    if not isinstance(system, SystemV3):
        raise HomeAssistantError("Can only set system properties on V3 systems")

    await system.async_set_properties(
        {prop: value for prop, value in call.data.items() if prop != ATTR_DEVICE_ID}
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    for service, method, schema in (
        (SERVICE_NAME_REMOVE_PIN, async_remove_pin, SERVICE_REMOVE_PIN_SCHEMA),
        (SERVICE_NAME_SET_PIN, async_set_pin, SERVICE_SET_PIN_SCHEMA),
        (
            SERVICE_NAME_SET_SYSTEM_PROPERTIES,
            async_set_system_properties,
            SERVICE_SET_SYSTEM_PROPERTIES_SCHEMA,
        ),
    ):
        if hass.services.has_service(DOMAIN, service):
            continue
        async_register_admin_service(hass, DOMAIN, service, method, schema=schema)
