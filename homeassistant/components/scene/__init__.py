"""
Allow users to set and activate scenes.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/scene/
"""
import asyncio
import importlib
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_PLATFORM, SERVICE_TURN_ON)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.state import HASS_DOMAIN

DOMAIN = 'scene'
STATE = 'scening'
STATES = 'states'


def _hass_domain_validator(config):
    """Validate platform in config for homeassistant domain."""
    if CONF_PLATFORM not in config:
        config = {
            CONF_PLATFORM: HASS_DOMAIN, STATES: config}

    return config


def _platform_validator(config):
    """Validate it is a valid  platform."""
    try:
        platform = importlib.import_module(
            'homeassistant.components.scene.{}'.format(
                config[CONF_PLATFORM]))
    except ImportError:
        raise vol.Invalid('Invalid platform specified') from None

    if not hasattr(platform, 'PLATFORM_SCHEMA'):
        return config

    return platform.PLATFORM_SCHEMA(config)


PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        _hass_domain_validator,
        vol.Schema({
            vol.Required(CONF_PLATFORM): str
        }, extra=vol.ALLOW_EXTRA),
        _platform_validator
    ), extra=vol.ALLOW_EXTRA)

SCENE_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


async def async_setup(hass, config):
    """Set up the scenes."""
    logger = logging.getLogger(__name__)
    component = hass.data[DOMAIN] = EntityComponent(logger, DOMAIN, hass)

    await component.async_setup(config)

    async def async_handle_scene_service(service):
        """Handle calls to the switch services."""
        target_scenes = component.async_extract_from_service(service)

        tasks = [scene.async_activate() for scene in target_scenes]
        if tasks:
            await asyncio.wait(tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, async_handle_scene_service,
        schema=SCENE_SERVICE_SCHEMA)

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class Scene(Entity):
    """A scene is a group of entities and the states we want them to be."""

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def state(self):
        """Return the state of the scene."""
        return STATE

    def activate(self):
        """Activate scene. Try to get entities into requested state."""
        raise NotImplementedError()

    def async_activate(self):
        """Activate scene. Try to get entities into requested state.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.activate)
