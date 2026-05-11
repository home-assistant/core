"""Set up the Elke27 integration."""

import contextlib
import logging
from typing import TYPE_CHECKING

from elke27_lib import ArmMode
from elke27_lib.errors import (
    Elke27ConnectionError,
    Elke27DisconnectedError,
    Elke27LinkRequiredError,
    Elke27TimeoutError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)

from .const import CONF_INTEGRATION_SERIAL, CONF_LINK_KEYS_JSON, CONF_PANEL, DOMAIN
from .coordinator import Elke27DataUpdateCoordinator
from .entity import unique_base
from .hub import Elke27Hub
from .identity import async_get_integration_serial
from .models import Elke27RuntimeData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

SERVICE_ALARM_ARM_AUTOMATIC = "alarm_arm_automatic"
ATTR_MODE = "mode"
ATTR_CODE = "code"

SERVICE_ALARM_ARM_AUTOMATIC_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_MODE): vol.In(("away", "home")),
        vol.Required(ATTR_CODE): cv.string,
    }
)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
]


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the Elke27 domain services."""
    if not hass.services.has_service(DOMAIN, SERVICE_ALARM_ARM_AUTOMATIC):

        async def _handle_alarm_arm_automatic(call: ServiceCall) -> None:
            await _async_handle_alarm_arm_automatic(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_ALARM_ARM_AUTOMATIC,
            _handle_alarm_arm_automatic,
            schema=SERVICE_ALARM_ARM_AUTOMATIC_SCHEMA,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elke27 from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    link_keys_json = entry.data.get(CONF_LINK_KEYS_JSON)
    panel_name = _panel_name_from_entry(entry.data.get(CONF_PANEL))
    if not link_keys_json:
        msg = "Link keys are missing; relink required"
        raise ConfigEntryAuthFailed(msg)
    integration_serial = entry.data.get(CONF_INTEGRATION_SERIAL)
    entry_data = dict(entry.data)
    pin_removed = entry_data.pop("pin", None)
    if not integration_serial:
        integration_serial = await async_get_integration_serial(hass, host)
        entry_data[CONF_INTEGRATION_SERIAL] = integration_serial
        hass.config_entries.async_update_entry(entry, data=entry_data)
    elif pin_removed is not None:
        hass.config_entries.async_update_entry(entry, data=entry_data)
    if panel_name:
        _LOGGER.debug("Discovered panel name: %s", panel_name)
    hub = Elke27Hub(
        hass,
        host,
        port,
        link_keys_json,
        integration_serial,
        panel_name,
    )
    try:
        await hub.async_connect()
    except Elke27LinkRequiredError as err:
        msg = "Linking credentials are invalid; relink required"
        raise ConfigEntryAuthFailed(msg) from err
    except (Elke27ConnectionError, Elke27TimeoutError, Elke27DisconnectedError) as err:
        _LOGGER.exception("Failed to set up connection to %s:%s", host, port)
        with contextlib.suppress(Exception):
            await hub.async_disconnect()
        msg = "The client did not become ready; check host and port"
        raise ConfigEntryNotReady(msg) from err

    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    await coordinator.async_start()
    await coordinator.async_refresh_now()

    snapshot = hub.get_snapshot() if hasattr(hub, "get_snapshot") else None
    if hasattr(coordinator, "async_set_updated_data"):
        coordinator.async_set_updated_data(snapshot)
    else:
        coordinator.data = snapshot
    await _async_migrate_unique_ids(hass, entry, unique_base(hub, coordinator, entry))
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Elke27 config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data: Elke27RuntimeData | None = entry.runtime_data
    if data is not None:
        await data.coordinator.async_stop()
        await data.hub.async_disconnect()
    return unload_ok


def _panel_name_from_entry(panel: object | None) -> str | None:
    if isinstance(panel, dict):
        return panel.get("panel_name") or panel.get("name")
    return None


async def _async_migrate_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, base: str
) -> None:
    """Migrate legacy unique IDs to the <base>:<domain>:<id> format."""
    registry = er.async_get(hass)
    prefix = f"{base}_"
    for entity in registry.entities.values():
        if entity.platform != DOMAIN:
            continue
        if entity.config_entry_id != entry.entry_id:
            continue
        unique_id = entity.unique_id
        if not unique_id.startswith(prefix):
            continue
        rest = unique_id[len(prefix) :]
        if "_" not in rest:
            continue
        domain, numeric_id = rest.rsplit("_", 1)
        new_unique_id = f"{base}:{domain}:{numeric_id}"
        if registry.async_get_entity_id(entity.domain, DOMAIN, new_unique_id):
            _LOGGER.debug(
                "Unique ID migration skipped for %s; %s already exists",
                entity.entity_id,
                new_unique_id,
            )
            continue
        registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)


async def _async_handle_alarm_arm_automatic(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handle the Elke27 automation arming service."""
    mode_name = call.data[ATTR_MODE]
    code = call.data[ATTR_CODE]

    entity_ids = _entity_ids_from_service_call(hass, call)
    if not entity_ids:
        msg = "No Elke27 alarm control panel target was provided"
        raise ServiceValidationError(msg)

    for entity_id in entity_ids:
        await _async_arm_automatic_entity(
            hass,
            entity_id,
            mode_name,
            code,
        )


def _entity_ids_from_service_call(hass: HomeAssistant, call: ServiceCall) -> list[str]:
    """Extract target entity IDs from a service call."""
    referenced = async_extract_referenced_entity_ids(hass, TargetSelection(call.data))
    return sorted(referenced.referenced | referenced.indirectly_referenced)


async def _async_arm_automatic_entity(
    hass: HomeAssistant,
    entity_id: str,
    mode_name: str,
    code: str,
) -> None:
    """Handle the automatic arming service for one entity."""
    entity_entry = er.async_get(hass).async_get(entity_id)
    if (
        entity_entry is None
        or entity_entry.platform != DOMAIN
        or entity_entry.domain != Platform.ALARM_CONTROL_PANEL
    ):
        msg = f"Entity {entity_id} is not an Elke27 alarm control panel"
        raise ServiceValidationError(msg)

    if entity_entry.config_entry_id is None:
        msg = f"Config entry for {entity_id} was not found"
        raise ServiceValidationError(msg)

    config_entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
    if config_entry is None:
        msg = f"Config entry for {entity_id} was not found"
        raise ServiceValidationError(msg)
    if config_entry.state is not ConfigEntryState.LOADED:
        msg = f"Config entry for {entity_id} is not loaded"
        raise ServiceValidationError(msg)

    runtime_data: Elke27RuntimeData | None = config_entry.runtime_data
    if runtime_data is None:
        msg = f"Runtime data for {entity_id} is unavailable"
        raise ServiceValidationError(msg)

    await runtime_data.hub.async_arm_area(
        _area_id_from_unique_id(entity_entry.unique_id),
        _service_mode_to_arm_mode(mode_name),
        code,
        auto_stay_cancel=True,
        exit_delay_cancel=True,
    )


def _service_mode_to_arm_mode(mode_name: str) -> ArmMode:
    """Map service mode names to library arm modes."""
    if mode_name == "away":
        return ArmMode.ARMED_AWAY
    if mode_name == "home":
        return ArmMode.ARMED_STAY
    msg = f"Unsupported arming mode: {mode_name}"
    raise ServiceValidationError(msg)


def _area_id_from_unique_id(unique_id: str) -> int:
    """Extract an area ID from an Elke27 alarm entity unique ID."""
    prefix = ":area:"
    if prefix not in unique_id:
        msg = "Entity unique ID is not a recognized Elke27 area identifier"
        raise ServiceValidationError(msg)
    area_id_str = unique_id.rsplit(prefix, 1)[1]
    try:
        return int(area_id_str)
    except ValueError as err:
        msg = f"Invalid Elke27 area ID in unique ID: {unique_id}"
        raise ServiceValidationError(msg) from err
