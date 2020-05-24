"""The netwave-camera integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import ATTR_COMMAND, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from ...config_entries import ConfigEntry
from ...helpers.typing import HomeAssistantType
from .const import (
    ATTR_MOVE_DURATION,
    ATTR_PARAMETER,
    ATTR_VALUE,
    COMMAND_FACTORY_RESET_CAMERA,
    COMMAND_MOVE_CENTER,
    COMMAND_MOVE_DOWN,
    COMMAND_MOVE_DOWN_LEFT,
    COMMAND_MOVE_DOWN_RIGHT,
    COMMAND_MOVE_LEFT,
    COMMAND_MOVE_RIGHT,
    COMMAND_MOVE_UP,
    COMMAND_MOVE_UP_LEFT,
    COMMAND_MOVE_UP_RIGHT,
    COMMAND_PATROL_HORIZONTAL,
    COMMAND_PATROL_VERTICAL,
    COMMAND_PELCO_PATROL_HORIZONTAL,
    COMMAND_PELCO_STOP_PATROL_HORIZONTAL,
    COMMAND_RECALL_PRESET,
    COMMAND_RESTART_CAMERA,
    COMMAND_SET_PRESET,
    COMMAND_STOP_MOVEMENT,
    COMMAND_STOP_PATROL_HORIZONTAL,
    COMMAND_STOP_PATROL_VERTICAL,
    COMMAND_TURN_IO_OFF,
    COMMAND_TURN_IO_ON,
    DEFAULT_PRESET,
    DOMAIN,
    PARAMETER_BRIGHTNESS,
    PARAMETER_CONTRAST,
    PARAMETER_MODE,
    PARAMETER_ORIENTATION,
    PARAMETER_RESOLUTION,
    SERVICE_COMMAND,
    SERVICE_INFO,
    SERVICE_PARAMETER,
    SERVICE_REFRESH,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]

SERVICE_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_COMMAND): vol.In(
            [
                COMMAND_STOP_MOVEMENT,
                COMMAND_MOVE_LEFT,
                COMMAND_MOVE_RIGHT,
                COMMAND_MOVE_UP,
                COMMAND_MOVE_DOWN,
                COMMAND_MOVE_UP_LEFT,
                COMMAND_MOVE_UP_RIGHT,
                COMMAND_MOVE_DOWN_LEFT,
                COMMAND_MOVE_DOWN_RIGHT,
                COMMAND_MOVE_CENTER,
                COMMAND_PATROL_VERTICAL,
                COMMAND_STOP_PATROL_VERTICAL,
                COMMAND_PATROL_HORIZONTAL,
                COMMAND_STOP_PATROL_HORIZONTAL,
                COMMAND_PELCO_PATROL_HORIZONTAL,
                COMMAND_PELCO_STOP_PATROL_HORIZONTAL,
                COMMAND_TURN_IO_ON,
                COMMAND_TURN_IO_OFF,
                COMMAND_SET_PRESET,
                COMMAND_RECALL_PRESET,
                COMMAND_RESTART_CAMERA,
                COMMAND_FACTORY_RESET_CAMERA,
            ]
        ),
        vol.Optional(ATTR_PARAMETER, default=DEFAULT_PRESET): vol.Range(1, 15),
        vol.Optional(ATTR_MOVE_DURATION, default=None): vol.Any(int, float, None),
    }
)

SERVICE_PARAMETER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_PARAMETER): vol.In(
            [
                PARAMETER_BRIGHTNESS,
                PARAMETER_CONTRAST,
                PARAMETER_MODE,
                PARAMETER_ORIENTATION,
                PARAMETER_RESOLUTION,
            ]
        ),
        vol.Required(ATTR_VALUE): vol.Or(cv.string, cv.positive_int),
    }
)

SERVICE_INFO_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_ids})


async def _setup_services(hass: HomeAssistant):
    """Initialize the services for NetWave."""
    hass.data.setdefault(DOMAIN, {})

    async def async_handle_command(call):
        """Handle request to send a command."""
        for entity in call.data[ATTR_ENTITY_ID]:
            camera = hass.data[DOMAIN][entity]
            await hass.async_add_executor_job(
                camera.send_command, call.data[ATTR_COMMAND], call.data[ATTR_PARAMETER]
            )
            duration = (
                camera.move_duration
                if call.data[ATTR_MOVE_DURATION] is None
                else call.data[ATTR_MOVE_DURATION]
            )
            if (
                "move_" in call.data[ATTR_COMMAND]
                and "center" not in call.data[ATTR_COMMAND]
                and duration > 0
            ):
                await asyncio.sleep(duration)
                await hass.async_add_executor_job(
                    camera.send_command, COMMAND_STOP_MOVEMENT
                )

    async def async_handle_parameter(call):
        """Handle request to update a camera parameter value."""
        for entity in call.data[ATTR_ENTITY_ID]:
            await hass.async_add_executor_job(
                hass.data[DOMAIN][entity].send_parameter,
                call.data[ATTR_PARAMETER],
                call.data[ATTR_VALUE],
            )

    async def async_handle_info(call):
        """Handle request to update info for a camera."""
        for entity in call.data[ATTR_ENTITY_ID]:
            await hass.async_add_executor_job(hass.data[DOMAIN][entity].get_info)

    async def async_handle_refresh(call):
        """Handle request to refresh all camera info."""
        for _, camera in hass.data[DOMAIN].items():
            await hass.async_add_executor_job(camera.get_info)

    hass.services.async_register(
        DOMAIN, SERVICE_COMMAND, async_handle_command, schema=SERVICE_COMMAND_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PARAMETER,
        async_handle_parameter,
        schema=SERVICE_PARAMETER_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_INFO, async_handle_info, schema=SERVICE_INFO_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_REFRESH, async_handle_refresh)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the netwave-camera component."""
    await _setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up camera from a config entry."""
    await _setup_services(hass)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "camera")
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload camrta config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "camera")

    _LOGGER.error(hass.data[DOMAIN])
    _LOGGER.error(entry.unique_id)

    for _, camera in hass.data[DOMAIN].items():
        _LOGGER.error(camera.unique_id)
        if camera.unique_id == entry.unique_id:
            hass.data[DOMAIN].pop(camera.entity_id)
            _LOGGER.error(camera.entity_id)
            break

    _LOGGER.error(hass.data[DOMAIN])

    # Remove services if no cameras are left
    if len(hass.data[DOMAIN]) == 0:
        for service in [
            SERVICE_INFO,
            SERVICE_REFRESH,
            SERVICE_PARAMETER,
            SERVICE_COMMAND,
        ]:
            hass.services.async_remove(DOMAIN, service)
    return True
