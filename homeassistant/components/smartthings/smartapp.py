"""
SmartApp functionality to receive cloud-push notifications.

This module defines the functions to manage the SmartApp integration
within the SmartThings ecosystem in order to receive real-time webhook-based
callbacks when device states change.
"""
import asyncio
import functools
import logging
import os
from uuid import uuid4

from aiohttp.web_exceptions import HTTPBadRequest, HTTPUnauthorized

from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.json import load_json, save_json

from .const import (
    APP_NAME_PREFIX, APP_OAUTH_SCOPES, CONF_APP_ID, CONF_INSTALLED_APP_ID,
    CONF_INSTANCE_ID, CONF_LOCATION_ID, DATA_BROKERS, DATA_MANAGER, DOMAIN,
    SETTINGS_INSTANCE_ID, SIGNAL_SMARTAPP_PREFIX, SMARTTHINGS_CONFIG_FILE,
    SUPPORTED_CAPABILITIES, URL_SMARTAPP)

_LOGGER = logging.getLogger(__name__)


async def find_app(hass: HomeAssistantType, api):
    """Find an existing SmartApp for this installation of hass."""
    apps = await api.apps()
    for app in [app for app in apps
                if app.app_name.startswith(APP_NAME_PREFIX)]:
        # Load settings to compare instance id
        settings = await app.settings()
        if settings.settings.get(SETTINGS_INSTANCE_ID) == \
                hass.data[DOMAIN][CONF_INSTANCE_ID]:
            return app


async def validate_installed_app(api, app_id: str, installed_app_id: str):
    """
    Ensure the specified installed SmartApp is valid and functioning.

    Query the API for the installed SmartApp and validate that it is tied to
    the specified app_id and is in an authorized state.
    """
    from pysmartthings import InstalledAppStatus

    installed_app = await api.installed_app(installed_app_id)
    if installed_app.installed_app_status != InstalledAppStatus.AUTHORIZED:
        raise RuntimeWarning("Installed SmartApp instance '{}' ({}) is not "
                             "AUTHORIZED but instead {}."
                             .format(installed_app.display_name,
                                     installed_app.installed_app_id,
                                     installed_app.installed_app_status))
    return installed_app


def _get_app_template(hass: HomeAssistantType):
    from pysmartthings import APP_TYPE_WEBHOOK, CLASSIFICATION_AUTOMATION

    return {
        'app_name': APP_NAME_PREFIX + str(uuid4()),
        'display_name': 'Home Assistant',
        'description': "Home Assistant at " + hass.config.api.base_url,
        'webhook_target_url': hass.config.api.base_url + URL_SMARTAPP,
        'app_type': APP_TYPE_WEBHOOK,
        'single_instance': True,
        'classifications': [CLASSIFICATION_AUTOMATION]
    }


async def create_app(hass: HomeAssistantType, api):
    """Create a SmartApp for this instance of hass."""
    from pysmartthings import App, AppOAuth, AppSettings
    from pysmartapp.const import SETTINGS_APP_ID

    # Create app from template attributes
    template = _get_app_template(hass)
    app = App()
    for key, value in template.items():
        setattr(app, key, value)
    app = (await api.create_app(app))[0]
    _LOGGER.debug("Created SmartApp '%s' (%s).", app.app_name, app.app_id)

    # Set unique hass id in settings
    settings = AppSettings(app.app_id)
    settings.settings[SETTINGS_APP_ID] = app.app_id
    settings.settings[SETTINGS_INSTANCE_ID] = \
        hass.data[DOMAIN][CONF_INSTANCE_ID]
    await api.update_app_settings(settings)
    _LOGGER.debug("Updated App Settings for SmartApp '%s' (%s).",
                  app.app_name, app.app_id)

    # Set oauth scopes
    oauth = AppOAuth(app.app_id)
    oauth.client_name = 'Home Assistant'
    oauth.scope.extend(APP_OAUTH_SCOPES)
    await api.update_app_oauth(oauth)
    _LOGGER.debug("Updated App OAuth for SmartApp '%s' (%s).",
                  app.app_name, app.app_id)
    return app


async def update_app(hass: HomeAssistantType, app):
    """Ensure the SmartApp is up-to-date and update if necessary."""
    await app.refresh()  # load all attributes
    template = _get_app_template(hass)
    template.pop('app_name')  # don't update this
    update_required = False
    for key, value in template.items():
        if getattr(app, key) != value:
            update_required = True
            setattr(app, key, value)
    if update_required:
        await app.save()
        _LOGGER.debug("SmartApp '%s' (%s) updated with latest settings.",
                      app.app_name, app.app_id)


def setup_smartapp(hass, app):
    """
    Configure an individual SmartApp in hass.

    Register the SmartApp with the SmartAppManager so that hass will service
    lifecycle events (install, event, etc...).  A unique SmartApp is created
    for each SmartThings account that is configured in hass.
    """
    manager = hass.data[DOMAIN][DATA_MANAGER]
    smartapp = manager.smartapps.get(app.app_id)
    if smartapp:
        # already setup
        return smartapp
    smartapp = manager.register(app.app_id, app.webhook_public_key)
    smartapp.name = app.display_name
    smartapp.description = app.description
    smartapp.permissions.extend(APP_OAUTH_SCOPES)
    return smartapp


async def setup_smartapp_endpoint(hass: HomeAssistantType):
    """
    Configure the SmartApp webhook in hass.

    SmartApps are an extension point within the SmartThings ecosystem and
    is used to receive push updates (i.e. device updates) from the cloud.
    """
    from pysmartapp import Dispatcher, SmartAppManager

    data = hass.data.get(DOMAIN)
    if data:
        # already setup
        return

    # Get/create config to store a unique id for this hass instance.
    path = hass.config.path(SMARTTHINGS_CONFIG_FILE)
    if not await hass.async_add_job(os.path.isfile, path):
        # Create config
        config = {
            CONF_INSTANCE_ID: str(uuid4())
        }
        await hass.async_add_job(save_json, path, config)
    else:
        config = await hass.async_add_job(load_json, path)

    # SmartAppManager uses a dispatcher to invoke callbacks when push events
    # occur. Use hass' implementation instead of the built-in one.
    dispatcher = Dispatcher(
        signal_prefix=SIGNAL_SMARTAPP_PREFIX,
        connect=functools.partial(async_dispatcher_connect, hass),
        send=functools.partial(async_dispatcher_send, hass))
    manager = SmartAppManager(URL_SMARTAPP, dispatcher=dispatcher)
    manager.connect_install(functools.partial(smartapp_install, hass))
    manager.connect_uninstall(functools.partial(smartapp_uninstall, hass))

    hass.http.register_view(APISmartAppView(manager))

    hass.data[DOMAIN] = {
        DATA_MANAGER: manager,
        CONF_INSTANCE_ID: config[CONF_INSTANCE_ID],
        DATA_BROKERS: {}
    }


async def smartapp_install(hass: HomeAssistantType, req, resp, app):
    """
    Handle when a SmartApp is installed by the user into a location.

    Setup subscriptions using the access token SmartThings provided in the
    event. An explicit subscription is required for each 'capability' in order
    to receive the related attribute updates.  Finally, create a config entry
    representing the installation.
    """
    from pysmartthings import SmartThings, Subscription, SourceType

    api = SmartThings(async_get_clientsession(hass), req.auth_token)
    coroutines = []
    for capability in SUPPORTED_CAPABILITIES:
        sub = Subscription()
        sub.installed_app_id = req.installed_app_id
        sub.location_id = req.location_id
        sub.source_type = SourceType.CAPABILITY
        sub.capability = capability
        coroutines.append(api.create_subscription(sub))
    await asyncio.gather(*coroutines)
    _LOGGER.debug("SmartApp '%s' under parent app '%s' was installed.",
                  req.installed_app_id, app.app_id)

    # Add as job not needed because the current coroutine was invoked
    # from the dispatcher and is not being awaited.
    await hass.config_entries.flow.async_init(
        DOMAIN, context={'source': 'install'},
        data={
            CONF_APP_ID: app.app_id,
            CONF_INSTALLED_APP_ID: req.installed_app_id,
            CONF_LOCATION_ID: req.location_id
        })


async def smartapp_uninstall(hass: HomeAssistantType, req, resp, app):
    """
    Handle when a SmartApp is removed from a location by the user.

    Find and delete the config entry representing the integration.
    """
    entry = next((entry for entry in hass.config_entries.async_entries(DOMAIN)
                  if entry.data.get(CONF_INSTALLED_APP_ID) ==
                  req.installed_app_id),
                 None)
    if entry:
        _LOGGER.debug("SmartApp '%s' under parent app '%s' was removed.",
                      req.installed_app_id, app.app_id)
        # Add as job not needed because the current coroutine was invoked
        # from the dispatcher and is not being awaited.
        await hass.config_entries.async_remove(entry.entry_id)


class APISmartAppView(HomeAssistantView):
    """View that routes requests to the SmartAppManager."""

    def __init__(self, manager):
        """Create a new instance of the view."""
        self._manager = manager

    url = URL_SMARTAPP
    name = 'api:smartapp'
    requires_auth = False

    async def post(self, request):
        """Process smartapp lifecycle event."""
        from pysmartapp import SignatureVerificationError

        try:
            data = await request.json()
            resp = await self._manager.handle_request(data, request.headers)
        except SignatureVerificationError as ex:
            raise HTTPUnauthorized from ex
        except Exception as ex:
            raise HTTPBadRequest from ex
        return self.json(resp)
