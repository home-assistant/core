"""Services for Google Mail integration."""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from googleapiclient.http import HttpRequest
import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import ATTR_ME, DOMAIN

if TYPE_CHECKING:
    from . import GoogleMailConfigEntry


class GoogleMailService(StrEnum):
    """Store keys for Google Mail services."""

    SET_VACATION = "set_vacation"


class GoogleMailServiceArgument(StrEnum):
    """Store keys for Google Mail service arguments."""

    ENABLED = "enabled"
    TITLE = "title"
    MESSAGE = "message"
    PLAIN_TEXT = "plain_text"
    RESTRICT_CONTACTS = "restrict_contacts"
    RESTRICT_DOMAIN = "restrict_domain"
    START = "start"
    END = "end"


SERVICE_VACATION_SCHEMA = probatio.All(
    cv.make_entity_service_schema(
        {
            probatio.Required(
                GoogleMailServiceArgument.ENABLED, default=True
            ): cv.boolean,
            probatio.Optional(GoogleMailServiceArgument.TITLE): cv.string,
            probatio.Required(GoogleMailServiceArgument.MESSAGE): cv.string,
            probatio.Optional(
                GoogleMailServiceArgument.PLAIN_TEXT, default=True
            ): cv.boolean,
            probatio.Optional(GoogleMailServiceArgument.RESTRICT_CONTACTS): cv.boolean,
            probatio.Optional(GoogleMailServiceArgument.RESTRICT_DOMAIN): cv.boolean,
            probatio.Optional(GoogleMailServiceArgument.START): cv.date,
            probatio.Optional(GoogleMailServiceArgument.END): cv.date,
        },
    )
)


async def _extract_gmail_config_entries(
    call: ServiceCall,
) -> list[GoogleMailConfigEntry]:
    return [
        entry
        for entry_id in await async_extract_config_entry_ids(call)
        if (entry := call.hass.config_entries.async_get_entry(entry_id))
        and entry.domain == DOMAIN
    ]


async def _gmail_service(call: ServiceCall) -> None:
    """Call Google Mail service."""
    for entry in await _extract_gmail_config_entries(call):
        try:
            auth = entry.runtime_data
        except AttributeError as ex:
            raise ValueError(f"Config entry not loaded: {entry.entry_id}") from ex
        service = await auth.get_resource()

        _settings = {
            "enableAutoReply": call.data[GoogleMailServiceArgument.ENABLED],
            "responseSubject": call.data.get(GoogleMailServiceArgument.TITLE),
        }
        if contacts := call.data.get(GoogleMailServiceArgument.RESTRICT_CONTACTS):
            _settings["restrictToContacts"] = contacts
        if domain := call.data.get(GoogleMailServiceArgument.RESTRICT_DOMAIN):
            _settings["restrictToDomain"] = domain
        if _date := call.data.get(GoogleMailServiceArgument.START):
            _dt = datetime.combine(_date, datetime.min.time())
            _settings["startTime"] = _dt.timestamp() * 1000
        if _date := call.data.get(GoogleMailServiceArgument.END):
            _dt = datetime.combine(_date, datetime.min.time())
            _settings["endTime"] = (_dt + timedelta(days=1)).timestamp() * 1000
        if call.data[GoogleMailServiceArgument.PLAIN_TEXT]:
            _settings["responseBodyPlainText"] = call.data[
                GoogleMailServiceArgument.MESSAGE
            ]
        else:
            _settings["responseBodyHtml"] = call.data[GoogleMailServiceArgument.MESSAGE]
        settings: HttpRequest = (
            service.users().settings().updateVacation(userId=ATTR_ME, body=_settings)
        )
        await call.hass.async_add_executor_job(settings.execute)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Google Mail integration."""

    hass.services.async_register(
        domain=DOMAIN,
        service=GoogleMailService.SET_VACATION,
        schema=SERVICE_VACATION_SCHEMA,
        service_func=_gmail_service,
    )
