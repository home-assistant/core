"""Handle Hue Service calls."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohue import HueBridgeV1, HueBridgeV2
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.service import verify_domain_control

from .bridge import HueBridge, HueConfigEntry
from .const import (
    ATTR_DYNAMIC,
    ATTR_GROUP_NAME,
    ATTR_GROUPS,
    ATTR_SCENE_BRIGHTNESS,
    ATTR_SCENE_ENTITY_ID,
    ATTR_SCENE_MODE,
    ATTR_SCENE_NAME,
    ATTR_SCENE_SPEED,
    ATTR_SMART_SCENE_ENTITY_ID,
    ATTR_TRANSITION,
    DOMAIN,
    SERVICE_CAPTURE_GROUP_SCENE,
    SERVICE_HUE_ACTIVATE_SCENE,
    SERVICE_RESTORE_GROUP_SCENE,
)
from .scene import (
    ATTR_BRIGHTNESS as SCENE_ATTR_BRIGHTNESS,
    ATTR_DYNAMIC as SCENE_ATTR_DYNAMIC,
    ATTR_SPEED as SCENE_ATTR_SPEED,
    SERVICE_ACTIVATE_SCENE as SCENE_ENTITY_SERVICE_ACTIVATE,
)
from .v1.light import ATTR_IS_HUE_GROUP
from .v2.scene_activity import get_or_create_scene_activity_manager

LOGGER = logging.getLogger(__name__)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for Hue integration."""

    async def hue_activate_scene(call: ServiceCall, skip_reload=True) -> None:
        """Handle activation of Hue scene."""
        # Get parameters
        group_name = call.data[ATTR_GROUP_NAME]
        scene_name = call.data[ATTR_SCENE_NAME]
        transition = call.data.get(ATTR_TRANSITION)
        dynamic = call.data.get(ATTR_DYNAMIC, False)

        # Call the set scene function on each bridge
        entries: list[HueConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
        tasks = [
            hue_activate_scene_v1(
                entry.runtime_data, group_name, scene_name, transition
            )
            if entry.runtime_data.api_version == 1
            else hue_activate_scene_v2(
                entry.runtime_data, group_name, scene_name, transition, dynamic
            )
            for entry in entries
        ]
        results = await asyncio.gather(*tasks)

        # Did *any* bridge succeed?
        # Note that we'll get a "True" value for a successful call
        if True not in results:
            LOGGER.warning(
                "No bridge was able to activate scene %s in group %s",
                scene_name,
                group_name,
            )

    # Register a local handler for scene activation
    hass.services.async_register(
        DOMAIN,
        SERVICE_HUE_ACTIVATE_SCENE,
        verify_domain_control(DOMAIN)(hue_activate_scene),
        schema=vol.Schema(
            {
                vol.Required(ATTR_GROUP_NAME): cv.string,
                vol.Required(ATTR_SCENE_NAME): cv.string,
                vol.Optional(ATTR_TRANSITION): cv.positive_int,
                vol.Optional(ATTR_DYNAMIC): cv.boolean,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CAPTURE_GROUP_SCENE,
        verify_domain_control(DOMAIN)(capture_group_scene),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTORE_GROUP_SCENE,
        verify_domain_control(DOMAIN)(restore_group_scene),
        schema=vol.Schema({vol.Required(ATTR_GROUPS): dict}),
    )


async def hue_activate_scene_v1(
    bridge: HueBridge,
    group_name: str,
    scene_name: str,
    transition: int | None = None,
    is_retry: bool = False,
) -> bool:
    """Service for V1 bridge to call directly into bridge to set scenes."""
    api: HueBridgeV1 = bridge.api
    if api.scenes is None:
        LOGGER.warning("Hub %s does not support scenes", api.host)
        return False

    group = next(
        (group for group in api.groups.values() if group.name == group_name),
        None,
    )
    # Additional scene logic to handle duplicate scene names across groups
    scene = next(
        (
            scene
            for scene in api.scenes.values()
            if scene.name == scene_name
            and group is not None
            and sorted(scene.lights) == sorted(group.lights)
        ),
        None,
    )
    # If we can't find it, fetch latest info and try again
    if not is_retry and (group is None or scene is None):
        await bridge.async_request_call(api.groups.update)
        await bridge.async_request_call(api.scenes.update)
        return await hue_activate_scene_v1(
            bridge, group_name, scene_name, transition, is_retry=True
        )

    if group is None or scene is None:
        LOGGER.debug(
            "Unable to find scene %s for group %s on bridge %s",
            scene_name,
            group_name,
            bridge.host,
        )
        return False

    await bridge.async_request_call(
        group.set_action, scene=scene.id, transitiontime=transition
    )
    return True


async def hue_activate_scene_v2(
    bridge: HueBridge,
    group_name: str,
    scene_name: str,
    transition: int | None = None,
    dynamic: bool = True,
) -> bool:
    """Service for V2 bridge to call scene by name."""
    LOGGER.warning(
        (
            "Use of service_call '%s' is deprecated and will be removed "
            "in a future release. Please use scene entities instead"
        ),
        SERVICE_HUE_ACTIVATE_SCENE,
    )
    api: HueBridgeV2 = bridge.api
    for scene in api.scenes:
        if scene.metadata.name.lower() != scene_name.lower():
            continue
        group = api.scenes.get_group(scene.id)
        if group.metadata.name.lower() != group_name.lower():
            continue
        # found match!
        if transition:
            transition = transition * 1000  # transition is in ms
        await bridge.async_request_call(
            api.scenes.recall, scene.id, dynamic=dynamic, duration=transition
        )
        return True
    LOGGER.debug(
        "Unable to find scene %s for group %s on bridge %s",
        scene_name,
        group_name,
        bridge.host,
    )
    return False


async def capture_group_scene(call: ServiceCall) -> dict[str, Any]:
    """Capture currently active (regular or smart) Hue scenes for grouped lights."""
    hass = call.hass
    entity_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    def _resolve_grouped_light_entities() -> set[str]:
        """Resolve valid grouped light entity_ids from call data (entities + devices)."""
        resolved: set[str] = set()

        def _is_grouped_light(entity_id: str) -> bool:
            state = hass.states.get(entity_id)
            if state is None:
                return False
            return bool(state.attributes.get(ATTR_IS_HUE_GROUP))

        entity_ids: list[str] | None = call.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            resolved.update(
                entity_id for entity_id in entity_ids if _is_grouped_light(entity_id)
            )

        device_ids: list[str] | None = call.data.get("device_id")
        if device_ids:
            resolved.update(
                entity.entity_id
                for device_id in device_ids
                for entity in er.async_entries_for_device(entity_reg, device_id)
                if _is_grouped_light(entity.entity_id)
            )

        return resolved

    def _capture_grouped_light_scene(
        entity_id: str,
    ) -> tuple[str, dict[str, Any]] | None:
        entity_entry = entity_reg.async_get(entity_id)
        if entity_entry is None:
            return None
        config_entry_id = entity_entry.config_entry_id
        if not config_entry_id:
            return None
        config_entry = hass.config_entries.async_get_entry(config_entry_id)
        if config_entry is None:
            return None
        bridge: HueBridge = config_entry.runtime_data
        if bridge.api_version != 2:  # only V2 has scene activity tracking
            return None
        manager = get_or_create_scene_activity_manager(hass, bridge.api)
        device_id = entity_entry.device_id
        if not device_id:
            return None
        device = dev_reg.async_get(device_id)
        if device is None:
            return None
        group_id = next(
            (ident for domain, ident in device.identifiers if domain == DOMAIN), None
        )
        if not group_id:
            return None
        group_state = manager.get_group_state(group_id)
        if (
            not group_state.active_scene_entity_id
            and not group_state.active_smart_scene_entity_id
        ):
            return None
        scene_state: dict[str, Any] = {}
        if group_state.active_scene_entity_id:
            scene_state[ATTR_SCENE_ENTITY_ID] = group_state.active_scene_entity_id
        if group_state.active_scene_mode:
            scene_state[ATTR_SCENE_MODE] = group_state.active_scene_mode
        if group_state.active_scene_speed:
            scene_state[ATTR_SCENE_SPEED] = group_state.active_scene_speed
        if group_state.active_scene_brightness:
            scene_state[ATTR_SCENE_BRIGHTNESS] = group_state.active_scene_brightness
        if group_state.active_smart_scene_entity_id:
            scene_state[ATTR_SMART_SCENE_ENTITY_ID] = (
                group_state.active_smart_scene_entity_id
            )
        return (entity_id, scene_state)

    grouped_lights: dict[str, Any] = {}
    for entity_id in _resolve_grouped_light_entities():
        result = _capture_grouped_light_scene(entity_id)
        if result:
            grouped_lights[result[0]] = result[1]
    return {ATTR_GROUPS: grouped_lights}


async def restore_group_scene(call: ServiceCall) -> bool:
    """Restore grouped light scenes state."""
    hass = call.hass
    grouped_lights = call.data.get(ATTR_GROUPS)
    if not grouped_lights or not isinstance(grouped_lights, dict):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_scene_to_restore"
        )
    entity_reg = er.async_get(hass)

    for entity_id, scene_state in grouped_lights.items():
        if not isinstance(scene_state, dict):
            continue
        entity_entry = entity_reg.async_get(entity_id)
        if (
            not entity_entry
            or entity_entry.domain != "light"
            or entity_entry.platform != DOMAIN
        ):
            continue

        # Prefer smart scene over regular scene when both are present
        if smart_scene_entity_id := scene_state.get(ATTR_SMART_SCENE_ENTITY_ID):
            service_data = {ATTR_ENTITY_ID: smart_scene_entity_id}
        elif regular_scene_entity_id := scene_state.get(ATTR_SCENE_ENTITY_ID):
            service_data = {ATTR_ENTITY_ID: regular_scene_entity_id}
            if scene_state.get(ATTR_SCENE_MODE) == "dynamic_palette":
                service_data[SCENE_ATTR_DYNAMIC] = True
            if speed := scene_state.get(ATTR_SCENE_SPEED):
                # 'activate_scene' speed accepts 0-100 range instead of a float
                service_data[SCENE_ATTR_SPEED] = speed * 100
            if brightness := scene_state.get(ATTR_SCENE_BRIGHTNESS):
                service_data[SCENE_ATTR_BRIGHTNESS] = brightness

        if service_data is None:
            continue

        await hass.services.async_call(
            DOMAIN,
            SCENE_ENTITY_SERVICE_ACTIVATE,
            service_data,
            blocking=True,
        )
    return True
