"""Config flow to configure SmartThings."""
import logging

from aiohttp import ClientResponseError
from pysmartthings import APIResponseError, AppOAuth, SmartThings
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN, HTTP_FORBIDDEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    APP_OAUTH_CLIENT_NAME,
    APP_OAUTH_SCOPES,
    CONF_APP_ID,
    CONF_INSTALLED_APPS,
    CONF_LOCATION_ID,
    CONF_OAUTH_CLIENT_ID,
    CONF_OAUTH_CLIENT_SECRET,
    DOMAIN,
    VAL_UID_MATCHER,
)
from .smartapp import (
    create_app,
    find_app,
    setup_smartapp,
    setup_smartapp_endpoint,
    update_app,
    validate_webhook_requirements,
)

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class SmartThingsFlowHandler(config_entries.ConfigFlow):
    """
    Handle configuration of SmartThings integrations.

    Any number of integrations are supported.  The high level flow follows:
    1) Flow initiated
        a) User initiates through the UI
        b) Re-configuration of a failed entry setup
    2) Enter access token
        a) Check not already setup
        b) Validate format
        c) Setup SmartApp
    3) Wait for Installation
        a) Check user installed into one or more locations
        b) Config entries setup for all installations
    """

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Create a new instance of the flow handler."""
        self.access_token = None
        self.app_id = None
        self.api = None
        self.oauth_client_secret = None
        self.oauth_client_id = None

    async def async_step_import(self, user_input=None):
        """Occurs when a previously entry setup fails and is re-initiated."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Get access token and validate it."""
        errors = {}
        if user_input is None or CONF_ACCESS_TOKEN not in user_input:
            return self._show_step_user(errors)

        self.access_token = user_input.get(CONF_ACCESS_TOKEN, "")
        self.api = SmartThings(async_get_clientsession(self.hass), self.access_token)

        # Ensure token is a UUID
        if not VAL_UID_MATCHER.match(self.access_token):
            errors[CONF_ACCESS_TOKEN] = "token_invalid_format"
            return self._show_step_user(errors)
        # Check not already setup in another entry
        if any(
            entry.data.get(CONF_ACCESS_TOKEN) == self.access_token
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        ):
            errors[CONF_ACCESS_TOKEN] = "token_already_setup"
            return self._show_step_user(errors)

        # Setup end-point
        await setup_smartapp_endpoint(self.hass)

        if not validate_webhook_requirements(self.hass):
            errors["base"] = "base_url_not_https"
            return self._show_step_user(errors)

        try:
            app = await find_app(self.hass, self.api)
            if app:
                await app.refresh()  # load all attributes
                await update_app(self.hass, app)
                # Get oauth client id/secret by regenerating it
                app_oauth = AppOAuth(app.app_id)
                app_oauth.client_name = APP_OAUTH_CLIENT_NAME
                app_oauth.scope.extend(APP_OAUTH_SCOPES)
                client = await self.api.generate_app_oauth(app_oauth)
            else:
                app, client = await create_app(self.hass, self.api)
            setup_smartapp(self.hass, app)
            self.app_id = app.app_id
            self.oauth_client_secret = client.client_secret
            self.oauth_client_id = client.client_id

        except APIResponseError as ex:
            if ex.is_target_error():
                errors["base"] = "webhook_error"
            else:
                errors["base"] = "app_setup_error"
            _LOGGER.exception(
                "API error setting up the SmartApp: %s", ex.raw_error_response
            )
            return self._show_step_user(errors)
        except ClientResponseError as ex:
            if ex.status == 401:
                errors[CONF_ACCESS_TOKEN] = "token_unauthorized"
            elif ex.status == HTTP_FORBIDDEN:
                errors[CONF_ACCESS_TOKEN] = "token_forbidden"
            else:
                errors["base"] = "app_setup_error"
                _LOGGER.exception("Unexpected error setting up the SmartApp")
            return self._show_step_user(errors)
        except Exception:  # pylint:disable=broad-except
            errors["base"] = "app_setup_error"
            _LOGGER.exception("Unexpected error setting up the SmartApp")
            return self._show_step_user(errors)

        return await self.async_step_wait_install()

    async def async_step_wait_install(self, user_input=None):
        """Wait for SmartApp installation."""
        errors = {}
        if user_input is None:
            return self._show_step_wait_install(errors)

        # Find installed apps that were authorized
        installed_apps = self.hass.data[DOMAIN][CONF_INSTALLED_APPS].copy()
        if not installed_apps:
            errors["base"] = "app_not_installed"
            return self._show_step_wait_install(errors)
        self.hass.data[DOMAIN][CONF_INSTALLED_APPS].clear()

        # Enrich the data
        for installed_app in installed_apps:
            installed_app[CONF_APP_ID] = self.app_id
            installed_app[CONF_ACCESS_TOKEN] = self.access_token
            installed_app[CONF_OAUTH_CLIENT_ID] = self.oauth_client_id
            installed_app[CONF_OAUTH_CLIENT_SECRET] = self.oauth_client_secret

        # User may have installed the SmartApp in more than one SmartThings
        # location. Config flows are created for the additional installations
        for installed_app in installed_apps[1:]:
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "install"}, data=installed_app
                )
            )

        # Create config entity for the first one.
        return await self.async_step_install(installed_apps[0])

    def _show_step_user(self, errors):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ACCESS_TOKEN, default=self.access_token): str}
            ),
            errors=errors,
            description_placeholders={
                "token_url": "https://account.smartthings.com/tokens",
                "component_url": "https://www.home-assistant.io/integrations/smartthings/",
            },
        )

    def _show_step_wait_install(self, errors):
        return self.async_show_form(step_id="wait_install", errors=errors)

    async def async_step_install(self, data=None):
        """
        Create a config entry at completion of a flow.

        Launched when the user completes the flow or when the SmartApp
        is installed into an additional location.
        """
        if not self.api:
            # Launched from the SmartApp install event handler
            self.api = SmartThings(
                async_get_clientsession(self.hass), data[CONF_ACCESS_TOKEN]
            )

        location = await self.api.location(data[CONF_LOCATION_ID])
        return self.async_create_entry(title=location.name, data=data)
