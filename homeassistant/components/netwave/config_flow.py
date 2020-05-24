"""Config flow for Netwave camera integration."""
import logging

from netwave import NetwaveCamera as NetwaveCameraAPI
import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    ATTR_ID,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
)

from .const import (  # pylint: disable=unused-import
    CONF_FRAMERATE,
    CONF_HORIZONTAL_MIRROR,
    CONF_MOVE_DURATION,
    CONF_VERTICAL_MIRROR,
    DEFAULT_FRAMERATE,
    DEFAULT_MOVE_DURATION,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_TIMEOUT,
    DEFAULT_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def test_camera(camera):
    """Tests a camera connection and returns None or an error."""
    try:
        camera.update_info()
        return None
    except requests.RequestException:
        return "connection_error"
    except RuntimeError:
        return "auth_failed"


class NetwaveFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Netwave camera."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            camera = NetwaveCameraAPI(
                user_input[CONF_ADDRESS],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_TIMEOUT],
            )
            result = await self.hass.async_add_executor_job(test_camera, camera)
            if result is None:
                # Success, create camera config entry.
                await self.async_set_unique_id(camera.get_info()[ATTR_ID])
                self._abort_if_unique_id_configured()
                config = user_input.copy()
                try:
                    config[CONF_MOVE_DURATION] = float(user_input[CONF_MOVE_DURATION])
                    return self.async_create_entry(
                        title=user_input[CONF_NAME], data=config
                    )
                except ValueError:
                    errors["base"] = "duration_type_error"
            else:
                errors["base"] = result

        # Show configuration form (default form in case of no user_input,
        # form filled with user_input and eventually with errors otherwise).
        return self._show_config_form(user_input, errors)

    def _show_config_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS, default=user_input.get(CONF_ADDRESS, "")
                    ): str,
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(
                        CONF_USERNAME,
                        default=user_input.get(CONF_USERNAME, DEFAULT_USERNAME),
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD),
                    ): str,
                    vol.Required(
                        CONF_TIMEOUT,
                        default=user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    ): int,
                    vol.Required(
                        CONF_VERTICAL_MIRROR,
                        default=user_input.get(CONF_VERTICAL_MIRROR, False),
                    ): bool,
                    vol.Required(
                        CONF_HORIZONTAL_MIRROR,
                        default=user_input.get(CONF_HORIZONTAL_MIRROR, False),
                    ): bool,
                    vol.Required(
                        CONF_FRAMERATE,
                        default=user_input.get(CONF_FRAMERATE, DEFAULT_FRAMERATE),
                    ): int,
                    vol.Required(
                        CONF_MOVE_DURATION,
                        default=user_input.get(
                            CONF_MOVE_DURATION, DEFAULT_MOVE_DURATION
                        ),
                    ): str,
                }
            ),
            errors=errors,
        )
