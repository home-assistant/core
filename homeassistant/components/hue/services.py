"""Handle Hue Service calls."""

import asyncio
from datetime import timedelta
import logging

from aiohue import HueBridgeV1, HueBridgeV2
from aiohue.v2.models.feature import (
    ColorFeaturePut,
    ColorPoint,
    Signal,
    SignalingFeaturePut,
)
import probatio

from homeassistant.components.light import ATTR_RGB_COLOR, DOMAIN as LIGHT_DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.service import (
    async_register_batched_platform_entity_service,
    async_register_platform_entity_service,
    verify_domain_control,
)
from homeassistant.helpers.typing import VolDictType
from homeassistant.util import color as color_util

from .bridge import HueBridge, HueConfigEntry
from .const import (
    ATTR_BRIGHTNESS,
    ATTR_DURATION,
    ATTR_DYNAMIC,
    ATTR_GROUP_NAME,
    ATTR_SCENE_NAME,
    ATTR_SECOND_RGB_COLOR,
    ATTR_SPEED,
    ATTR_TRANSITION,
    DOMAIN,
    SERVICE_ACTIVATE_SCENE,
    SERVICE_FLASH,
    SERVICE_HUE_ACTIVATE_SCENE,
    SERVICE_STOP_FLASH,
)
from .v2.group import GroupedHueLight
from .v2.light import HueLight

ACTIVATE_SCENE_SCHEMA: VolDictType = {
    probatio.Optional(ATTR_DYNAMIC): probatio.Coerce(bool),
    probatio.Optional(ATTR_SPEED): probatio.All(
        probatio.Coerce(int), probatio.Percentage()
    ),
    probatio.Optional(ATTR_TRANSITION): probatio.All(
        probatio.Coerce(float), probatio.Range(min=0, max=3600)
    ),
    probatio.Optional(ATTR_BRIGHTNESS): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1, max=255)
    ),
}

RGB_COLOR_SCHEMA = probatio.All(
    probatio.Coerce(tuple), probatio.ExactSequence((cv.byte,) * 3)
)
FLASH_SCHEMA: VolDictType = {
    probatio.Required(ATTR_DURATION): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(seconds=1), max=timedelta(seconds=65534)),
    ),
    probatio.Optional(ATTR_RGB_COLOR): RGB_COLOR_SCHEMA,
    probatio.Optional(ATTR_SECOND_RGB_COLOR): RGB_COLOR_SCHEMA,
}
FLASH_SIGNAL_BY_COLOR_COUNT = {
    0: Signal.ON_OFF,
    1: Signal.ON_OFF_COLOR,
    2: Signal.ALTERNATING,
}
SIGNAL_NOT_SUPPORTED_TRANSLATION_KEYS = {
    Signal.NO_SIGNAL: "stop_flash_not_supported",
    Signal.ON_OFF: "flash_not_supported",
    Signal.ON_OFF_COLOR: "flash_color_not_supported",
    Signal.ALTERNATING: "flash_two_colors_not_supported",
}

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
        schema=probatio.Schema(
            {
                probatio.Required(ATTR_GROUP_NAME): cv.string,
                probatio.Required(ATTR_SCENE_NAME): cv.string,
                probatio.Optional(ATTR_TRANSITION): cv.positive_int,
                probatio.Optional(ATTR_DYNAMIC): cv.boolean,
            }
        ),
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ACTIVATE_SCENE,
        entity_domain=SCENE_DOMAIN,
        func="_async_activate",
        schema=ACTIVATE_SCENE_SCHEMA,
    )
    async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_FLASH,
        entity_domain=LIGHT_DOMAIN,
        func=hue_flash,
        schema=FLASH_SCHEMA,
    )
    async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_STOP_FLASH,
        entity_domain=LIGHT_DOMAIN,
        func=hue_stop_flash,
        schema=None,
    )


async def hue_flash(entities: list[Entity], call: ServiceCall) -> None:
    """Flash Hue lights and grouped lights (V2 only)."""
    if ATTR_SECOND_RGB_COLOR in call.data and ATTR_RGB_COLOR not in call.data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="second_color_without_color",
        )
    colors = [
        ColorFeaturePut(xy=ColorPoint(*color_util.color_RGB_to_xy(*call.data[field])))
        for field in (ATTR_RGB_COLOR, ATTR_SECOND_RGB_COLOR)
        if field in call.data
    ]
    await _async_set_signal(
        entities,
        SignalingFeaturePut(
            signal=FLASH_SIGNAL_BY_COLOR_COUNT[len(colors)],
            duration=int(call.data[ATTR_DURATION].total_seconds() * 1000),
            colors=colors or None,
        ),
    )


async def hue_stop_flash(entities: list[Entity], call: ServiceCall) -> None:
    """Stop flashing Hue lights and grouped lights (V2 only)."""
    # The Hue API requires a duration, but ignores it when stopping
    await _async_set_signal(
        entities, SignalingFeaturePut(signal=Signal.NO_SIGNAL, duration=0)
    )


async def _async_set_signal(
    entities: list[Entity], signaling: SignalingFeaturePut
) -> None:
    """Send a signal to the entities that support it."""
    lights = [
        entity
        for entity in entities
        if isinstance(entity, (HueLight, GroupedHueLight))
        and entity.resource.signaling
        and signaling.signal in entity.resource.signaling.signal_values
    ]
    if not lights:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=SIGNAL_NOT_SUPPORTED_TRANSLATION_KEYS[signaling.signal],
            translation_placeholders={
                "entities": ", ".join(sorted(entity.entity_id for entity in entities))
            },
        )

    await asyncio.gather(*(light.async_set_signal(signaling) for light in lights))


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
