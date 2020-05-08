"""SmartApp functionality to receive cloud-push notifications."""
import asyncio
import functools
import logging
import secrets
from urllib.parse import urlparse
from uuid import uuid4

from aiohttp import web
from pysmartapp import Dispatcher, SmartAppManager
from pysmartapp.const import SETTINGS_APP_ID
from pysmartthings import (
    APP_TYPE_WEBHOOK,
    CAPABILITIES,
    CLASSIFICATION_AUTOMATION,
    App,
    AppOAuth,
    AppSettings,
    InstalledAppStatus,
    SmartThings,
    SourceType,
    Subscription,
    SubscriptionEntity,
)

from homeassistant.components import webhook
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.network import NoURLAvailableError, async_get_url
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    APP_NAME_PREFIX,
    APP_OAUTH_CLIENT_NAME,
    APP_OAUTH_SCOPES,
    CONF_CLOUDHOOK_URL,
    CONF_INSTALLED_APP_ID,
    CONF_INSTANCE_ID,
    CONF_REFRESH_TOKEN,
    DATA_BROKERS,
    DATA_MANAGER,
    DOMAIN,
    SETTINGS_INSTANCE_ID,
    SIGNAL_SMARTAPP_PREFIX,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def format_unique_id(app_id: str, location_id: str) -> str:
    """Format the unique id for a config entry."""
    return f"{app_id}_{location_id}"


async def find_app(hass: HomeAssistantType, api):
    """Find an existing SmartApp for this installation of hass."""
    apps = await api.apps()
    for app in [app for app in apps if app.app_name.startswith(APP_NAME_PREFIX)]:
        # Load settings to compare instance id
        settings = await app.settings()
        if (
            settings.settings.get(SETTINGS_INSTANCE_ID)
            == hass.data[DOMAIN][CONF_INSTANCE_ID]
        ):
            return app


async def validate_installed_app(api, installed_app_id: str):
    """
    Ensure the specified installed SmartApp is valid and functioning.

    Query the API for the installed SmartApp and validate that it is tied to
    the specified app_id and is in an authorized state.
    """
    installed_app = await api.installed_app(installed_app_id)
    if installed_app.installed_app_status != InstalledAppStatus.AUTHORIZED:
        raise RuntimeWarning(
            "Installed SmartApp instance '{}' ({}) is not AUTHORIZED but instead {}".format(
                installed_app.display_name,
                installed_app.installed_app_id,
                installed_app.installed_app_status,
            )
        )
    return installed_app


def validate_webhook_requirements(hass: HomeAssistantType) -> bool:
    """Ensure Home Assistant is setup properly to receive webhooks."""
    if hass.components.cloud.async_active_subscription():
        return True
    if hass.data[DOMAIN][CONF_CLOUDHOOK_URL] is not None:
        return True
    return get_webhook_url(hass).lower().startswith("https://")


def get_webhook_url(hass: HomeAssistantType) -> str:
    """
    Get the URL of the webhook.

    Return the cloudhook if available, otherwise local webhook.
    """
    cloudhook_url = hass.data[DOMAIN][CONF_CLOUDHOOK_URL]
    if hass.components.cloud.async_active_subscription() and cloudhook_url is not None:
        return cloudhook_url
    return webhook.async_generate_url(hass, hass.data[DOMAIN][CONF_WEBHOOK_ID])


def _get_app_template(hass: HomeAssistantType):
    try:
        endpoint = f"at {async_get_url(hass, allow_cloud=False, prefer_external=True)}"
    except NoURLAvailableError:
        endpoint = ""

    cloudhook_url = hass.data[DOMAIN][CONF_CLOUDHOOK_URL]
    if cloudhook_url is not None:
        endpoint = "via Nabu Casa"
    description = f"{hass.config.location_name} {endpoint}"

    return {
        "app_name": APP_NAME_PREFIX + str(uuid4()),
        "display_name": "Home Assistant",
        "description": description,
        "webhook_target_url": get_webhook_url(hass),
        "app_type": APP_TYPE_WEBHOOK,
        "single_instance": True,
        "classifications": [CLASSIFICATION_AUTOMATION],
    }


async def create_app(hass: HomeAssistantType, api):
    """Create a SmartApp for this instance of hass."""
    # Create app from template attributes
    template = _get_app_template(hass)
    app = App()
    for key, value in template.items():
        setattr(app, key, value)
    app, client = await api.create_app(app)
    _LOGGER.debug("Created SmartApp '%s' (%s)", app.app_name, app.app_id)

    # Set unique hass id in settings
    settings = AppSettings(app.app_id)
    settings.settings[SETTINGS_APP_ID] = app.app_id
    settings.settings[SETTINGS_INSTANCE_ID] = hass.data[DOMAIN][CONF_INSTANCE_ID]
    await api.update_app_settings(settings)
    _LOGGER.debug(
        "Updated App Settings for SmartApp '%s' (%s)", app.app_name, app.app_id
    )

    # Set oauth scopes
    oauth = AppOAuth(app.app_id)
    oauth.client_name = APP_OAUTH_CLIENT_NAME
    oauth.scope.extend(APP_OAUTH_SCOPES)
    await api.update_app_oauth(oauth)
    _LOGGER.debug("Updated App OAuth for SmartApp '%s' (%s)", app.app_name, app.app_id)
    return app, client


async def update_app(hass: HomeAssistantType, app):
    """Ensure the SmartApp is up-to-date and update if necessary."""
    template = _get_app_template(hass)
    template.pop("app_name")  # don't update this
    update_required = False
    for key, value in template.items():
        if getattr(app, key) != value:
            update_required = True
            setattr(app, key, value)
    if update_required:
        await app.save()
        _LOGGER.debug(
            "SmartApp '%s' (%s) updated with latest settings", app.app_name, app.app_id
        )


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
    data = hass.data.get(DOMAIN)
    if data:
        # already setup
        return

    # Get/create config to store a unique id for this hass instance.
    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    config = await store.async_load()
    if not config:
        # Create config
        config = {
            CONF_INSTANCE_ID: str(uuid4()),
            CONF_WEBHOOK_ID: secrets.token_hex(),
            CONF_CLOUDHOOK_URL: None,
        }
        await store.async_save(config)

    # Register webhook
    webhook.async_register(
        hass, DOMAIN, "SmartApp", config[CONF_WEBHOOK_ID], smartapp_webhook
    )

    # Create webhook if eligible
    cloudhook_url = config.get(CONF_CLOUDHOOK_URL)
    if (
        cloudhook_url is None
        and hass.components.cloud.async_active_subscription()
        and not hass.config_entries.async_entries(DOMAIN)
    ):
        cloudhook_url = await hass.components.cloud.async_create_cloudhook(
            config[CONF_WEBHOOK_ID]
        )
        config[CONF_CLOUDHOOK_URL] = cloudhook_url
        await store.async_save(config)
        _LOGGER.debug("Created cloudhook '%s'", cloudhook_url)

    # SmartAppManager uses a dispatcher to invoke callbacks when push events
    # occur. Use hass' implementation instead of the built-in one.
    dispatcher = Dispatcher(
        signal_prefix=SIGNAL_SMARTAPP_PREFIX,
        connect=functools.partial(async_dispatcher_connect, hass),
        send=functools.partial(async_dispatcher_send, hass),
    )
    # Path is used in digital signature validation
    path = (
        urlparse(cloudhook_url).path
        if cloudhook_url
        else webhook.async_generate_path(config[CONF_WEBHOOK_ID])
    )
    manager = SmartAppManager(path, dispatcher=dispatcher)
    manager.connect_install(functools.partial(smartapp_install, hass))
    manager.connect_update(functools.partial(smartapp_update, hass))
    manager.connect_uninstall(functools.partial(smartapp_uninstall, hass))

    hass.data[DOMAIN] = {
        DATA_MANAGER: manager,
        CONF_INSTANCE_ID: config[CONF_INSTANCE_ID],
        DATA_BROKERS: {},
        CONF_WEBHOOK_ID: config[CONF_WEBHOOK_ID],
        # Will not be present if not enabled
        CONF_CLOUDHOOK_URL: config.get(CONF_CLOUDHOOK_URL),
    }
    _LOGGER.debug(
        "Setup endpoint for %s",
        cloudhook_url
        if cloudhook_url
        else webhook.async_generate_url(hass, config[CONF_WEBHOOK_ID]),
    )


async def unload_smartapp_endpoint(hass: HomeAssistantType):
    """Tear down the component configuration."""
    if DOMAIN not in hass.data:
        return
    # Remove the cloudhook if it was created
    cloudhook_url = hass.data[DOMAIN][CONF_CLOUDHOOK_URL]
    if cloudhook_url and hass.components.cloud.async_is_logged_in():
        await hass.components.cloud.async_delete_cloudhook(
            hass.data[DOMAIN][CONF_WEBHOOK_ID]
        )
        # Remove cloudhook from storage
        store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        await store.async_save(
            {
                CONF_INSTANCE_ID: hass.data[DOMAIN][CONF_INSTANCE_ID],
                CONF_WEBHOOK_ID: hass.data[DOMAIN][CONF_WEBHOOK_ID],
                CONF_CLOUDHOOK_URL: None,
            }
        )
        _LOGGER.debug("Cloudhook '%s' was removed", cloudhook_url)
    # Remove the webhook
    webhook.async_unregister(hass, hass.data[DOMAIN][CONF_WEBHOOK_ID])
    # Disconnect all brokers
    for broker in hass.data[DOMAIN][DATA_BROKERS].values():
        broker.disconnect()
    # Remove all handlers from manager
    hass.data[DOMAIN][DATA_MANAGER].dispatcher.disconnect_all()
    # Remove the component data
    hass.data.pop(DOMAIN)


async def smartapp_sync_subscriptions(
    hass: HomeAssistantType,
    auth_token: str,
    location_id: str,
    installed_app_id: str,
    devices,
):
    """Synchronize subscriptions of an installed up."""
    api = SmartThings(async_get_clientsession(hass), auth_token)
    tasks = []

    async def create_subscription(target: str):
        sub = Subscription()
        sub.installed_app_id = installed_app_id
        sub.location_id = location_id
        sub.source_type = SourceType.CAPABILITY
        sub.capability = target
        try:
            await api.create_subscription(sub)
            _LOGGER.debug(
                "Created subscription for '%s' under app '%s'", target, installed_app_id
            )
        except Exception as error:  # pylint:disable=broad-except
            _LOGGER.error(
                "Failed to create subscription for '%s' under app '%s': %s",
                target,
                installed_app_id,
                error,
            )

    async def delete_subscription(sub: SubscriptionEntity):
        try:
            await api.delete_subscription(installed_app_id, sub.subscription_id)
            _LOGGER.debug(
                "Removed subscription for '%s' under app '%s' because it was no longer needed",
                sub.capability,
                installed_app_id,
            )
        except Exception as error:  # pylint:disable=broad-except
            _LOGGER.error(
                "Failed to remove subscription for '%s' under app '%s': %s",
                sub.capability,
                installed_app_id,
                error,
            )

    # Build set of capabilities and prune unsupported ones
    capabilities = set()
    for device in devices:
        capabilities.update(device.capabilities)
    capabilities.intersection_update(CAPABILITIES)

    # Get current subscriptions and find differences
    subscriptions = await api.subscriptions(installed_app_id)
    for subscription in subscriptions:
        if subscription.capability in capabilities:
            capabilities.remove(subscription.capability)
        else:
            # Delete the subscription
            tasks.append(delete_subscription(subscription))

    # Remaining capabilities need subscriptions created
    tasks.extend([create_subscription(c) for c in capabilities])

    if tasks:
        await asyncio.gather(*tasks)
    else:
        _LOGGER.debug("Subscriptions for app '%s' are up-to-date", installed_app_id)


async def _continue_flow(
    hass: HomeAssistantType,
    app_id: str,
    location_id: str,
    installed_app_id: str,
    refresh_token: str,
):
    """Continue a config flow if one is in progress for the specific installed app."""
    unique_id = format_unique_id(app_id, location_id)
    flow = next(
        (
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["handler"] == DOMAIN and flow["context"]["unique_id"] == unique_id
        ),
        None,
    )
    if flow is not None:
        await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                CONF_INSTALLED_APP_ID: installed_app_id,
                CONF_REFRESH_TOKEN: refresh_token,
            },
        )
        _LOGGER.debug(
            "Continued config flow '%s' for SmartApp '%s' under parent app '%s'",
            flow["flow_id"],
            installed_app_id,
            app_id,
        )


async def smartapp_install(hass: HomeAssistantType, req, resp, app):
    """Handle a SmartApp installation and continue the config flow."""
    await _continue_flow(
        hass, app.app_id, req.location_id, req.installed_app_id, req.refresh_token
    )
    _LOGGER.debug(
        "Installed SmartApp '%s' under parent app '%s'",
        req.installed_app_id,
        app.app_id,
    )


async def smartapp_update(hass: HomeAssistantType, req, resp, app):
    """Handle a SmartApp update and either update the entry or continue the flow."""
    entry = next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_INSTALLED_APP_ID) == req.installed_app_id
        ),
        None,
    )
    if entry:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_REFRESH_TOKEN: req.refresh_token}
        )
        _LOGGER.debug(
            "Updated config entry '%s' for SmartApp '%s' under parent app '%s'",
            entry.entry_id,
            req.installed_app_id,
            app.app_id,
        )

    await _continue_flow(
        hass, app.app_id, req.location_id, req.installed_app_id, req.refresh_token
    )
    _LOGGER.debug(
        "Updated SmartApp '%s' under parent app '%s'", req.installed_app_id, app.app_id
    )


async def smartapp_uninstall(hass: HomeAssistantType, req, resp, app):
    """
    Handle when a SmartApp is removed from a location by the user.

    Find and delete the config entry representing the integration.
    """
    entry = next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_INSTALLED_APP_ID) == req.installed_app_id
        ),
        None,
    )
    if entry:
        # Add as job not needed because the current coroutine was invoked
        # from the dispatcher and is not being awaited.
        await hass.config_entries.async_remove(entry.entry_id)

    _LOGGER.debug(
        "Uninstalled SmartApp '%s' under parent app '%s'",
        req.installed_app_id,
        app.app_id,
    )


async def smartapp_webhook(hass: HomeAssistantType, webhook_id: str, request):
    """
    Handle a smartapp lifecycle event callback from SmartThings.

    Requests from SmartThings are digitally signed and the SmartAppManager
    validates the signature for authenticity.
    """
    manager = hass.data[DOMAIN][DATA_MANAGER]
    data = await request.json()
    result = await manager.handle_request(data, request.headers)
    return web.json_response(result)
