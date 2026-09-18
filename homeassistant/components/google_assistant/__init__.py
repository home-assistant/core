"""Support for Actions on Google Assistant Smart Home Control."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

import probatio

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
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
    EVENT_QUERY_RECEIVED,
    SOURCE_CLOUD,
)
from .http import GoogleAssistantView, GoogleConfig
from .services import async_setup_services

from .const import EVENT_COMMAND_RECEIVED, EVENT_SYNC_RECEIVED  # noqa: F401, isort:skip

CONF_ALLOW_UNLOCK = "allow_unlock"

PLATFORMS = [Platform.BUTTON]

ENTITY_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_NAME): cv.string,
        probatio.Optional(CONF_EXPOSE, default=True): cv.boolean,
        probatio.Optional(CONF_ALIASES): probatio.All(cv.ensure_list, [cv.string]),
        probatio.Optional(CONF_ROOM_HINT): cv.string,
    }
)

GOOGLE_SERVICE_ACCOUNT = probatio.Schema(
    {
        probatio.Required(CONF_PRIVATE_KEY): cv.string,
        probatio.Required(CONF_CLIENT_EMAIL): cv.string,
    },
    extra=probatio.ALLOW_EXTRA,
)


def _check_report_state(data):
    if data[CONF_REPORT_STATE] and CONF_SERVICE_ACCOUNT not in data:
        raise probatio.Invalid(
            "If report state is enabled, a service account must exist"
        )
    return data


GOOGLE_ASSISTANT_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Required(CONF_PROJECT_ID): cv.string,
            probatio.Optional(
                CONF_EXPOSE_BY_DEFAULT, default=DEFAULT_EXPOSE_BY_DEFAULT
            ): cv.boolean,
            probatio.Optional(
                CONF_EXPOSED_DOMAINS, default=DEFAULT_EXPOSED_DOMAINS
            ): cv.ensure_list,
            probatio.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: ENTITY_SCHEMA},
            # str on purpose, makes sure it is configured correctly.
            probatio.Optional(CONF_SECURE_DEVICES_PIN): str,
            probatio.Optional(CONF_REPORT_STATE, default=False): cv.boolean,
            probatio.Optional(CONF_SERVICE_ACCOUNT): GOOGLE_SERVICE_ACCOUNT,
            # deprecated configuration options
            probatio.Remove(CONF_ALLOW_UNLOCK): cv.boolean,
            probatio.Remove(CONF_API_KEY): cv.string,
        },
        extra=probatio.PREVENT_EXTRA,
    ),
    _check_report_state,
)

CONFIG_SCHEMA = probatio.Schema(
    {probatio.Optional(DOMAIN): GOOGLE_ASSISTANT_SCHEMA}, extra=probatio.ALLOW_EXTRA
)

type GoogleConfigEntry = ConfigEntry[GoogleConfig]


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    """Activate Google Actions component."""
    if DOMAIN not in yaml_config:
        return True

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CONFIG] = yaml_config[DOMAIN]

    if CONF_SERVICE_ACCOUNT in yaml_config[DOMAIN]:
        async_setup_services(hass)

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_PROJECT_ID: yaml_config[DOMAIN][CONF_PROJECT_ID]},
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: GoogleConfigEntry) -> bool:
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

    entry.runtime_data = google_config

    hass.http.register_view(GoogleAssistantView(google_config))

    if google_config.should_report_state:
        google_config.async_enable_report_state()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
