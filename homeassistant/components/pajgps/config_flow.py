"""Config flow for PAJ GPS Tracker integration."""
from __future__ import annotations
import logging
import uuid
from typing import Any, Dict, Optional
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from pajgps_api import PajGpsApi
from pajgps_api.pajgps_api_error import AuthenticationError, TokenRefreshError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _build_config_schema(
    entry_name: str = 'My Paj GPS Account',
    email: str = '',
    password: str = '',
    mark_alerts_as_read: bool = True,
    fetch_elevation: bool = False,
    force_battery: bool = False,
) -> vol.Schema:
    """Build config schema with optional pre-filled defaults."""
    return vol.Schema(
        {
            vol.Required('entry_name', default=entry_name): cv.string,
            vol.Required('email', default=email): cv.string,
            vol.Required('password', default=password): cv.string,
            vol.Required('mark_alerts_as_read', default=mark_alerts_as_read): cv.boolean,
            vol.Required('fetch_elevation', default=fetch_elevation): cv.boolean,
            vol.Required('force_battery', default=force_battery): cv.boolean,
        }
    )

async def _validate_credentials(email: str, password: str) -> str | None:
    """
    Attempt a real login with the given credentials.
    Returns an error key string on failure, or None on success.
    """
    try:
        api = PajGpsApi(email=email, password=password)
        await api.login()
    except (AuthenticationError, TokenRefreshError):
        return "invalid_auth"
    except Exception:  # noqa: BLE001
        return "cannot_connect"
    return None


class CustomFlow(config_entries.ConfigFlow, domain=DOMAIN):
    data: Optional[Dict[str, Any]]

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            self.data = user_input
            # Create new guid for the entry
            self.data['guid'] = str(uuid.uuid4())
            # If entry_name is null or empty string, add error
            if not self.data['entry_name'] or self.data['entry_name'] == '':
                errors['base'] = 'entry_name_required'
            # If email is null or empty string, add error
            if not self.data['email'] or self.data['email'] == '':
                errors['base'] = 'email_required'
            # If password is null or empty string, add error
            if not self.data['password'] or self.data['password'] == '':
                errors['base'] = 'password_required'
            if not errors:
                self._async_abort_entries_match({"email": self.data["email"]})
                error_key = await _validate_credentials(self.data['email'], self.data['password'])
                if error_key:
                    errors['base'] = error_key
            if not errors:
                return self.async_create_entry(title=f"{self.data['entry_name']}", data=self.data)

            return self.async_show_form(
                step_id="user",
                data_schema=_build_config_schema(
                    entry_name=user_input.get('entry_name', ''),
                    email=user_input.get('email', ''),
                    password=user_input.get('password', ''),
                    mark_alerts_as_read=user_input.get('mark_alerts_as_read', True),
                    fetch_elevation=user_input.get('fetch_elevation', False),
                    force_battery=user_input.get('force_battery', False),
                ),
                errors=errors,
            )

        return self.async_show_form(step_id="user", data_schema=_build_config_schema(), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        errors: Dict[str, str] = {}

        default_entry_name = ''
        if 'entry_name' in self._config_entry.data:
            default_entry_name = self._config_entry.data['entry_name']
        if 'entry_name' in self._config_entry.options:
            default_entry_name = self._config_entry.options['entry_name']
        default_email = ''
        if 'email' in self._config_entry.data:
            default_email = self._config_entry.data['email']
        if 'email' in self._config_entry.options:
            default_email = self._config_entry.options['email']
        default_password = ''
        if 'password' in self._config_entry.data:
            default_password = self._config_entry.data['password']
        if 'password' in self._config_entry.options:
            default_password = self._config_entry.options['password']
        default_mark_alerts_as_read = True
        if 'mark_alerts_as_read' in self._config_entry.data:
            default_mark_alerts_as_read = self._config_entry.data['mark_alerts_as_read']
        if 'mark_alerts_as_read' in self._config_entry.options:
            default_mark_alerts_as_read = self._config_entry.options['mark_alerts_as_read']
        default_fetch_elevation = False
        if 'fetch_elevation' in self._config_entry.data:
            default_fetch_elevation = self._config_entry.data['fetch_elevation']
        if 'fetch_elevation' in self._config_entry.options:
            default_fetch_elevation = self._config_entry.options['fetch_elevation']
        default_force_battery = False
        if 'force_battery' in self._config_entry.data:
            default_force_battery = self._config_entry.data['force_battery']
        if 'force_battery' in self._config_entry.options:
            default_force_battery = self._config_entry.options['force_battery']

        if user_input is not None:
            # If email is null or empty string, add error
            if not user_input['email'] or user_input['email'] == '':
                errors['base'] = 'email_required'
            # If password is null or empty string, add error
            if not user_input['password'] or user_input['password'] == '':
                errors['base'] = 'password_required'
            if not errors:
                error_key = await _validate_credentials(user_input['email'], user_input['password'])
                if error_key:
                    errors['base'] = error_key
            if not errors:
                # Update the config entry with the new data and let the
                # _async_update_listener in __init__.py reload the coordinator.
                new_data = {
                    'guid': self._config_entry.data['guid'],
                    'entry_name': user_input['entry_name'],
                    'email': user_input['email'],
                    'password': user_input['password'],
                    'mark_alerts_as_read': user_input['mark_alerts_as_read'],
                    'fetch_elevation': user_input['fetch_elevation'],
                    'force_battery': user_input['force_battery'],
                }

                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data=new_data,
                    title=new_data['entry_name'],
                )

                return self.async_create_entry(title=new_data['entry_name'], data=new_data)

            return self.async_show_form(
                step_id="init",
                data_schema=_build_config_schema(
                    entry_name=user_input.get('entry_name', default_entry_name),
                    email=user_input.get('email', default_email),
                    password=user_input.get('password', default_password),
                    mark_alerts_as_read=user_input.get('mark_alerts_as_read', default_mark_alerts_as_read),
                    fetch_elevation=user_input.get('fetch_elevation', default_fetch_elevation),
                    force_battery=user_input.get('force_battery', default_force_battery),
                ),
                errors=errors,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_build_config_schema(
                entry_name=default_entry_name,
                email=default_email,
                password=default_password,
                mark_alerts_as_read=default_mark_alerts_as_read,
                fetch_elevation=default_fetch_elevation,
                force_battery=default_force_battery,
            ),
            errors=errors,
        )