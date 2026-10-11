"""Integration providing core pieces of infrastructure."""

import asyncio
from collections.abc import Callable, Coroutine
import struct
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, RESTART_EXIT_CODE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.signal import KEY_HA_STOP
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.helpers.typing import ConfigType

# The scene integration will do a late import of scene
# so we want to make sure its loaded with the component
# so its already in memory when its imported so the import
# does not do blocking I/O in the event loop.
from . import scene as scene_pre_import  # noqa: F401
from .const import (
    DATA_EXPOSED_ENTITIES,
    DATA_STOP_HANDLER,
    DOMAIN,
    SERVICE_HOMEASSISTANT_RESTART,  # noqa: F401
    SERVICE_HOMEASSISTANT_STOP,  # noqa: F401
    HomeAssistantService,
)
from .exposed_entities import ExposedEntities, async_should_expose  # noqa: F401
from .services import async_setup_services

# To be deprecated at a later stage, replaced by HomeAssistantService
SERVICE_RELOAD_CORE_CONFIG = HomeAssistantService.RELOAD_CORE_CONFIG.value
SERVICE_RELOAD_CONFIG_ENTRY = HomeAssistantService.RELOAD_CONFIG_ENTRY.value
SERVICE_RELOAD_CUSTOM_TEMPLATES = HomeAssistantService.RELOAD_CUSTOM_TEMPLATES.value
SERVICE_CHECK_CONFIG = HomeAssistantService.CHECK_CONFIG.value
SERVICE_UPDATE_ENTITY = HomeAssistantService.UPDATE_ENTITY.value
SERVICE_SET_LOCATION = HomeAssistantService.SET_LOCATION.value
SERVICE_RELOAD_ALL = HomeAssistantService.RELOAD_ALL.value

DEPRECATION_URL = (
    "https://www.home-assistant.io/blog/2025/05/22/"
    "deprecating-core-and-supervised-installation-methods-and-32-bit-systems/"
)


def _is_32_bit() -> bool:
    size = struct.calcsize("P")
    return size * 8 == 32


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up general services related to Home Assistant."""

    async_setup_services(hass)

    exposed_entities = ExposedEntities(hass)
    await exposed_entities.async_initialize()
    hass.data[DATA_EXPOSED_ENTITIES] = exposed_entities
    async_set_stop_handler(hass)

    async def _async_check_deprecation(event: Event) -> None:
        """Check and create deprecation issues after startup."""
        info = await async_get_system_info(hass)

        installation_type = info["installation_type"][15:]
        if installation_type in {"Core", "Container"}:
            deprecated_method = installation_type == "Core"
            bit32 = _is_32_bit()
            arch = info["arch"]
            if bit32 and installation_type == "Container":
                arch = info.get("container_arch", arch)
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    "deprecated_container",
                    learn_more_url=DEPRECATION_URL,
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_container",
                    translation_placeholders={"arch": arch},
                )
            deprecated_architecture = bit32 and installation_type != "Container"
            if deprecated_method or deprecated_architecture:
                issue_id = "deprecated"
                if deprecated_method:
                    issue_id += "_method"
                if deprecated_architecture:
                    issue_id += "_architecture"
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    issue_id,
                    learn_more_url=DEPRECATION_URL,
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key=issue_id,
                    translation_placeholders={
                        "installation_type": installation_type,
                        "arch": arch,
                    },
                )
        if not info["docker"] and not info["virtualenv"]:
            ir.async_create_issue(
                hass,
                DOMAIN,
                "unsupported_local_deps",
                breaks_in_ha_version="2026.11.0",
                learn_more_url=DEPRECATION_URL,
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="unsupported_local_deps",
            )

    # Delay deprecation check to make sure installation method is determined correctly
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_check_deprecation)

    return True


async def _async_stop(hass: HomeAssistant, restart: bool) -> None:
    """Stop home assistant."""
    exit_code = RESTART_EXIT_CODE if restart else 0
    # Track trask in hass.data. No need to cleanup, we're stopping.
    hass.data[KEY_HA_STOP] = asyncio.create_task(hass.async_stop(exit_code))


@callback
def async_set_stop_handler(
    hass: HomeAssistant,
    stop_handler: Callable[[HomeAssistant, bool], Coroutine[Any, Any, None]]
    | None = None,
) -> None:
    """Set function which is called by the stop and restart services.

    If stop handler is omitted it will restore the default stop handler.
    """
    hass.data[DATA_STOP_HANDLER] = _async_stop if stop_handler is None else stop_handler
