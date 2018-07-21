"""
Support for playing media by shell command
"""
import asyncio
import logging
import shlex

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_PLAY, SUPPORT_PLAY_MEDIA,
    MediaPlayerDevice, PLATFORM_SCHEMA, MEDIA_TYPE_MUSIC)
from homeassistant.const import ( CONF_COMMAND, CONF_NAME, STATE_ON)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template


_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Shell player'

SUPPORT_FEATURES = SUPPORT_PLAY | SUPPORT_PLAY_MEDIA

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COMMAND): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Shell Player platform."""

    if discovery_info is not None:
        return

    shell_command = config.get(CONF_COMMAND)
    name = config.get(CONF_NAME)

    async_add_devices([ShellPlayer(shell_command, name)])

class ShellPlayer(MediaPlayerDevice):
    """Representation of a Shell player."""

    def __init__(self, cmd, name):
        """Initialize the Shell player."""
        self._name = name
        self._cmd = cmd

    async def async_added_to_hass(self):
        """Prepare arguments."""

        if ' ' not in self._cmd:
            self._prog = self._cmd
            self._args = None
            self._args_compiled = None
        else:
            self._prog, self._args = self._cmd.split(' ', 1)
            self._args_compiled = template.Template(self._args, self.hass)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return STATE_ON

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_FEATURES

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Support changing a channel."""

        if media_type != MEDIA_TYPE_MUSIC:
            _LOGGER.error('Unsupported media type')
            return

        if self._args_compiled:
            try:
                rendered_args = self._args_compiled.async_render({'media_id':media_id})
            except TemplateError as ex:
                _LOGGER.exception("Error rendering command template: %s", ex)
                return

        if rendered_args == self._args:
            # No template used. default behavior

            _LOGGER.info("Executing: %s", self._cmd)

            # pylint: disable=no-member
            await asyncio.subprocess.create_subprocess_shell(
                    self._cmd,
                    loop=self.hass.loop,
                    stdin=None
                    )
        else:
            # Template used. Break into list and use create_subprocess_exec
            # (which uses shell=False) for security
            shlexed_cmd = [self._prog] + shlex.split(rendered_args)

            _LOGGER.info("Executing template: %s", rendered_args)
            # pylint: disable=no-member
            await asyncio.subprocess.create_subprocess_exec(
                    *shlexed_cmd,
                    loop=self.hass.loop,
                    stdin=None
                    )

