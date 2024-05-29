"""Handle Hue Service calls."""

from __future__ import annotations

import asyncio
import logging

from aiohue import HueBridgeV2
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import verify_domain_control

from .came_domotic_server import CameDomoticServer
from .const import (
    ATTR_DYNAMIC,
    ATTR_GROUP_NAME,
    ATTR_SCENE_NAME,
    ATTR_TRANSITION,
    DOMAIN,
    SERVICE_HUE_ACTIVATE_SCENE,
)

LOGGER = logging.getLogger(__name__)


def async_register_services(hass: HomeAssistant) -> None:
    """Register services for CAME Domotic API integration."""

    async def server_activate_scene(call: ServiceCall, skip_reload=True) -> None:
        """Handle activation of CAME Domotic API scene."""
        # Get parameters
        group_name = call.data[ATTR_GROUP_NAME]
        scene_name = call.data[ATTR_SCENE_NAME]
        transition = call.data.get(ATTR_TRANSITION)
        dynamic = call.data.get(ATTR_DYNAMIC, False)

        # Call the set scene function on each bridge
        tasks = [
            came_server_activate_scene(
                bridge, group_name, scene_name, transition, dynamic
            )
            for bridge in hass.data[DOMAIN].values()
            if isinstance(bridge, CameDomoticServer)
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

    if not hass.services.has_service(DOMAIN, SERVICE_HUE_ACTIVATE_SCENE):
        # Register a local handler for scene activation
        hass.services.async_register(
            DOMAIN,
            SERVICE_HUE_ACTIVATE_SCENE,
            verify_domain_control(hass, DOMAIN)(server_activate_scene),
            schema=vol.Schema(
                {
                    vol.Required(ATTR_GROUP_NAME): cv.string,
                    vol.Required(ATTR_SCENE_NAME): cv.string,
                    vol.Optional(ATTR_TRANSITION): cv.positive_int,
                    vol.Optional(ATTR_DYNAMIC): cv.boolean,
                }
            ),
        )


async def came_server_activate_scene(
    bridge: CameDomoticServer,
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
        "Unable to find scene %s for group %s",
        scene_name,
        group_name,
    )
    return False
