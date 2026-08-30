"""The pushover component."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pushover_complete import BadAPIRequestError, PushoverAPI
from requests.exceptions import RequestException
from urllib3.exceptions import HTTPError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ENTRY_ID,
    ATTR_TAG,
    CONF_USER_KEY,
    DATA_HASS_CONFIG,
    DOMAIN,
    SERVICE_CANCEL,
)

if TYPE_CHECKING:
    from .notify import PushoverNotificationService

PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_CANCEL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Optional(ATTR_TAG): cv.string,
    }
)


@dataclass
class PushoverRuntimeData:
    """Runtime data for a pushover config entry."""

    api: PushoverAPI
    notify_service: PushoverNotificationService | None = None


type PushoverConfigEntry = ConfigEntry[PushoverRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the pushover component."""

    hass.data[DATA_HASS_CONFIG] = config

    async def _async_cancel_service_handler(call: ServiceCall) -> None:
        """Cancel emergency notifications for the targeted config entry."""
        entry_id: str = call.data[ATTR_ENTRY_ID]
        entry: PushoverConfigEntry | None = hass.config_entries.async_get_entry(
            entry_id
        )
        if entry is None:
            raise ServiceValidationError(
                f"Pushover config entry {entry_id} does not exist"
            )

        notify_service = entry.runtime_data.notify_service
        if notify_service is None:
            raise ServiceValidationError(
                f"Pushover config entry {entry_id} has no notify service set up"
            )

        tag: str = call.data.get(ATTR_TAG, "")
        await hass.async_add_executor_job(notify_service.cancel_by_tag, tag)

    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL,
        _async_cancel_service_handler,
        schema=SERVICE_CANCEL_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: PushoverConfigEntry) -> bool:
    """Set up pushover from a config entry."""

    # remove unique_id for beta users
    if entry.unique_id is not None:
        hass.config_entries.async_update_entry(entry, unique_id=None)

    pushover_api = PushoverAPI(entry.data[CONF_API_KEY])
    try:
        await hass.async_add_executor_job(
            pushover_api.validate, entry.data[CONF_USER_KEY]
        )

    except (BadAPIRequestError, ValueError, RequestException, HTTPError) as err:
        if "application token is invalid" in str(err):
            raise ConfigEntryAuthFailed(err) from err
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = PushoverRuntimeData(api=pushover_api)

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                CONF_NAME: entry.data[CONF_NAME],
                CONF_USER_KEY: entry.data[CONF_USER_KEY],
                "entry_id": entry.entry_id,
            },
            hass.data[DATA_HASS_CONFIG],
        )
    )

    return True
