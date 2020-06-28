"""Config flow to configure SmartThings."""
import logging

from aiohttp import ClientResponseError
from pysmartthings import APIResponseError, AppOAuth, SmartThings
from pysmartthings.installedapp import format_install_url
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    HTTP_FORBIDDEN,
    HTTP_UNAUTHORIZED,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# pylint: disable=unused-import
from .const import (
    APP_OAUTH_CLIENT_NAME,
    APP_OAUTH_SCOPES,
    CONF_APP_ID,
    CONF_INSTALLED_APP_ID,
    CONF_LOCATION_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    VAL_UID_MATCHER,
)
from .smartapp import (
    create_app,
    find_app,
    format_unique_id,
    get_webhook_url,
    setup_smartapp,
    setup_smartapp_endpoint,
    update_app,
    validate_webhook_requirements,
)

_LOGGER = logging.getLogger(__name__)


class SmartThingsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle configuration of SmartThings integrations."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Create a new instance of the flow handler."""
        self.access_token = None
        self.app_id = None
        self.api = None
        self.oauth_client_secret = None
        self.oauth_client_id = None
        self.installed_app_id = None
        self.refresh_token = None
        self.location_id = None

    async def async_step_import(self, user_input=None):
        """Occurs when a previously entry setup fails and is re-initiated."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Validate and confirm webhook setup."""
        await setup_smartapp_endpoint(self.hass)
        webhook_url = get_webhook_url(self.hass)

        # Abort if the webhook is invalid
        if not validate_webhook_requirements(self.hass):
            return self.async_abort(
                reason="invalid_webhook_url",
                description_placeholders={
                    "webhook_url": webhook_url,
                    "component_url": "https://www.home-assistant.io/integrations/smartthings/",
                },
            )

        # Show the confirmation
        if user_input is None:
            return self.async_show_form(
                step_id="user", description_placeholders={"webhook_url": webhook_url},
            )

        # Show the next screen
        return await self.async_step_pat()

    async def async_step_pat(self, user_input=None):
        """Get the Personal Access Token and validate it."""
        errors = {}
        if user_input is None or CONF_ACCESS_TOKEN not in user_input:
            return self._show_step_pat(errors)

        self.access_token = user_input[CONF_ACCESS_TOKEN]

        # Ensure token is a UUID
        if not VAL_UID_MATCHER.match(self.access_token):
            errors[CONF_ACCESS_TOKEN] = "token_invalid_format"
            return self._show_step_pat(errors)

        # Setup end-point
        self.api = SmartThings(async_get_clientsession(self.hass), self.access_token)
        try:
            app = await find_app(self.hass, self.api)
            if app:
                await app.refresh()  # load all attributes
                await update_app(self.hass, app)
                # Find an existing entry to copy the oauth client
                existing = next(
                    (
                        entry
                        for entry in self._async_current_entries()
                        if entry.data[CONF_APP_ID] == app.app_id
                    ),
                    None,
                )
                if existing:
                    self.oauth_client_id = existing.data[CONF_CLIENT_ID]
                    self.oauth_client_secret = existing.data[CONF_CLIENT_SECRET]
                else:
                    # Get oauth client id/secret by regenerating it
                    app_oauth = AppOAuth(app.app_id)
                    app_oauth.client_name = APP_OAUTH_CLIENT_NAME
                    app_oauth.scope.extend(APP_OAUTH_SCOPES)
                    client = await self.api.generate_app_oauth(app_oauth)
                    self.oauth_client_secret = client.client_secret
                    self.oauth_client_id = client.client_id
            else:
                app, client = await create_app(self.hass, self.api)
                self.oauth_client_secret = client.client_secret
                self.oauth_client_id = client.client_id
            setup_smartapp(self.hass, app)
            self.app_id = app.app_id

        except APIResponseError as ex:
            if ex.is_target_error():
                errors["base"] = "webhook_error"
            else:
                errors["base"] = "app_setup_error"
            _LOGGER.exception(
                "API error setting up the SmartApp: %s", ex.raw_error_response
            )
            return self._show_step_pat(errors)
        except ClientResponseError as ex:
            if ex.status == HTTP_UNAUTHORIZED:
                errors[CONF_ACCESS_TOKEN] = "token_unauthorized"
                _LOGGER.debug(
                    "Unauthorized error received setting up SmartApp", exc_info=True
                )
            elif ex.status == HTTP_FORBIDDEN:
                errors[CONF_ACCESS_TOKEN] = "token_forbidden"
                _LOGGER.debug(
                    "Forbidden error received setting up SmartApp", exc_info=True
                )
            else:
                errors["base"] = "app_setup_error"
                _LOGGER.exception("Unexpected error setting up the SmartApp")
            return self._show_step_pat(errors)
        except Exception:  # pylint:disable=broad-except
            errors["base"] = "app_setup_error"
            _LOGGER.exception("Unexpected error setting up the SmartApp")
            return self._show_step_pat(errors)

        return await self.async_step_select_location()

    async def async_step_select_location(self, user_input=None):
        """Ask user to select the location to setup."""
        if user_input is None or CONF_LOCATION_ID not in user_input:
            # Get available locations
            existing_locations = [
                entry.data[CONF_LOCATION_ID] for entry in self._async_current_entries()
            ]
            locations = await self.api.locations()
            locations_options = {
                location.location_id: location.name
                for location in locations
                if location.location_id not in existing_locations
            }
            if not locations_options:
                return self.async_abort(reason="no_available_locations")

            return self.async_show_form(
                step_id="select_location",
                data_schema=vol.Schema(
                    {vol.Required(CONF_LOCATION_ID): vol.In(locations_options)}
                ),
            )

        self.location_id = user_input[CONF_LOCATION_ID]
        await self.async_set_unique_id(format_unique_id(self.app_id, self.location_id))
        return await self.async_step_authorize()

    async def async_step_authorize(self, user_input=None):
        """Wait for the user to authorize the app installation."""
        user_input = {} if user_input is None else user_input
        self.installed_app_id = user_input.get(CONF_INSTALLED_APP_ID)
        self.refresh_token = user_input.get(CONF_REFRESH_TOKEN)
        if self.installed_app_id is None:
            # Launch the external setup URL
            url = format_install_url(self.app_id, self.location_id)
            return self.async_external_step(step_id="authorize", url=url)

        return self.async_external_step_done(next_step_id="install")

    def _show_step_pat(self, errors):
        if self.access_token is None:
            # Get the token from an existing entry to make it easier to setup multiple locations.
            self.access_token = next(
                (
                    entry.data.get(CONF_ACCESS_TOKEN)
                    for entry in self._async_current_entries()
                ),
                None,
            )

        return self.async_show_form(
            step_id="pat",
            data_schema=vol.Schema(
                {vol.Required(CONF_ACCESS_TOKEN, default=self.access_token): str}
            ),
            errors=errors,
            description_placeholders={
                "token_url": "https://account.smartthings.com/tokens",
                "component_url": "https://www.home-assistant.io/integrations/smartthings/",
            },
        )

    async def async_step_install(self, data=None):
        """Create a config entry at completion of a flow and authorization of the app."""
        data = {
            CONF_ACCESS_TOKEN: self.access_token,
            CONF_REFRESH_TOKEN: self.refresh_token,
            CONF_CLIENT_ID: self.oauth_client_id,
            CONF_CLIENT_SECRET: self.oauth_client_secret,
            CONF_LOCATION_ID: self.location_id,
            CONF_APP_ID: self.app_id,
            CONF_INSTALLED_APP_ID: self.installed_app_id,
        }

        location = await self.api.location(data[CONF_LOCATION_ID])

        return self.async_create_entry(title=location.name, data=data)
