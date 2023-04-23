"""Support for Actions on Google Assistant Smart Home Control."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    CONF_ALIASES,
    CONF_CLIENT_EMAIL,
    CONF_ENTITY_CONFIG,
    CONF_EXPOSE,
    CONF_EXPOSE_BY_DEFAULT,
    CONF_EXPOSED_DOMAINS,
    CONF_PRIVATE_KEY,
    CONF_PROJECT_ID,
    CONF_REPORT_STATE,
    CONF_ROOM_HINT,
    CONF_SECURE_DEVICES_PIN,
    CONF_SERVICE_ACCOUNT,
    DATA_CONFIG,
    DEFAULT_EXPOSE_BY_DEFAULT,
    DEFAULT_EXPOSED_DOMAINS,
    DOMAIN,
    SERVICE_REQUEST_SYNC,
    SOURCE_CLOUD,
)
from .const import EVENT_QUERY_RECEIVED  # noqa: F401
from .http import GoogleAssistantView, GoogleConfig

from .const import EVENT_COMMAND_RECEIVED, EVENT_SYNC_RECEIVED  # noqa: F401, isort:skip

_LOGGER = logging.getLogger(__name__)

CONF_ALLOW_UNLOCK = "allow_unlock"

PLATFORMS = [Platform.BUTTON]

ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_EXPOSE, default=True): cv.boolean,
        vol.Optional(CONF_ALIASES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_ROOM_HINT): cv.string,
    }
)

GOOGLE_SERVICE_ACCOUNT = vol.Schema(
    {
        vol.Required(CONF_PRIVATE_KEY): cv.string,
        vol.Required(CONF_CLIENT_EMAIL): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)


def _check_report_state(data):
    if data[CONF_REPORT_STATE] and CONF_SERVICE_ACCOUNT not in data:
        raise vol.Invalid("If report state is enabled, a service account must exist")
    return data


GOOGLE_ASSISTANT_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_PROJECT_ID): cv.string,
            vol.Optional(
                CONF_EXPOSE_BY_DEFAULT, default=DEFAULT_EXPOSE_BY_DEFAULT
            ): cv.boolean,
            vol.Optional(
                CONF_EXPOSED_DOMAINS, default=DEFAULT_EXPOSED_DOMAINS
            ): cv.ensure_list,
            vol.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: ENTITY_SCHEMA},
            # str on purpose, makes sure it is configured correctly.
            vol.Optional(CONF_SECURE_DEVICES_PIN): str,
            vol.Optional(CONF_REPORT_STATE, default=False): cv.boolean,
            vol.Optional(CONF_SERVICE_ACCOUNT): GOOGLE_SERVICE_ACCOUNT,
            # deprecated configuration options
            vol.Remove(CONF_ALLOW_UNLOCK): cv.boolean,
            vol.Remove(CONF_API_KEY): cv.string,
        },
        extra=vol.PREVENT_EXTRA,
    ),
    _check_report_state,
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): GOOGLE_ASSISTANT_SCHEMA}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    """Activate Google Actions component."""
    if DOMAIN not in yaml_config:
        return True

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CONFIG] = yaml_config[DOMAIN]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_PROJECT_ID: yaml_config[DOMAIN][CONF_PROJECT_ID]},
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    config: ConfigType = {**hass.data[DOMAIN][DATA_CONFIG]}

    if entry.source == SOURCE_IMPORT:
        # if project was changed, remove entry a new will be setup
        if config[CONF_PROJECT_ID] != entry.data[CONF_PROJECT_ID]:
            hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
            return False

    config.update(entry.data)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, config[CONF_PROJECT_ID])},
        manufacturer="Google",
        model="Google Assistant",
        name=config[CONF_PROJECT_ID],
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    google_config = GoogleConfig(hass, config)
    await google_config.async_initialize()

    hass.data[DOMAIN][entry.entry_id] = google_config

    hass.http.register_view(GoogleAssistantView(google_config))

    if google_config.should_report_state:
        google_config.async_enable_report_state()

    async def request_sync_service_handler(call: ServiceCall) -> None:
        """Handle request sync service calls."""
        agent_user_id = call.data.get("agent_user_id") or call.context.user_id

        if agent_user_id is None:
            _LOGGER.warning(
                "No agent_user_id supplied for request_sync. Call as a user or pass in"
                " user id as agent_user_id"
            )
            return

        await google_config.async_sync_entities(agent_user_id)

    # Register service only if key is provided
    if CONF_SERVICE_ACCOUNT in config:
        hass.services.async_register(
            DOMAIN, SERVICE_REQUEST_SYNC, request_sync_service_handler
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
