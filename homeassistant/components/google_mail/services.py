"""Services for Google Mail integration."""
from __future__ import annotations

from datetime import datetime, timedelta

from googleapiclient.http import HttpRequest
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .api import AsyncConfigEntryAuth
from .const import (
    ATTR_ENABLED,
    ATTR_END,
    ATTR_ME,
    ATTR_MESSAGE,
    ATTR_PLAIN_TEXT,
    ATTR_RESTRICT_CONTACTS,
    ATTR_RESTRICT_DOMAIN,
    ATTR_START,
    ATTR_TITLE,
    DOMAIN,
)

SERVICE_SET_VACATION = "set_vacation"

SERVICE_VACATION_SCHEMA = vol.All(
    cv.make_entity_service_schema(
        {
            vol.Required(ATTR_ENABLED, default=True): cv.boolean,
            vol.Optional(ATTR_TITLE): cv.string,
            vol.Required(ATTR_MESSAGE): cv.string,
            vol.Optional(ATTR_PLAIN_TEXT, default=True): cv.boolean,
            vol.Optional(ATTR_RESTRICT_CONTACTS): cv.boolean,
            vol.Optional(ATTR_RESTRICT_DOMAIN): cv.boolean,
            vol.Optional(ATTR_START): cv.date,
            vol.Optional(ATTR_END): cv.date,
        },
    )
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Google Mail integration."""

    async def extract_gmail_config_entries(call: ServiceCall) -> list[ConfigEntry]:
        return [
            entry
            for entry_id in await async_extract_config_entry_ids(hass, call)
            if (entry := hass.config_entries.async_get_entry(entry_id))
            and entry.domain == DOMAIN
        ]

    async def gmail_service(call: ServiceCall) -> None:
        """Call Google Mail service."""
        auth: AsyncConfigEntryAuth
        for entry in await extract_gmail_config_entries(call):
            if not (auth := hass.data[DOMAIN].get(entry.entry_id)):
                raise ValueError(f"Config entry not loaded: {entry.entry_id}")
            service = await auth.get_resource()

            _settings = {
                "enableAutoReply": call.data[ATTR_ENABLED],
                "responseSubject": call.data.get(ATTR_TITLE),
            }
            if contacts := call.data.get(ATTR_RESTRICT_CONTACTS):
                _settings["restrictToContacts"] = contacts
            if domain := call.data.get(ATTR_RESTRICT_DOMAIN):
                _settings["restrictToDomain"] = domain
            if _date := call.data.get(ATTR_START):
                _dt = datetime.combine(_date, datetime.min.time())
                _settings["startTime"] = _dt.timestamp() * 1000
            if _date := call.data.get(ATTR_END):
                _dt = datetime.combine(_date, datetime.min.time())
                _settings["endTime"] = (_dt + timedelta(days=1)).timestamp() * 1000
            if call.data[ATTR_PLAIN_TEXT]:
                _settings["responseBodyPlainText"] = call.data[ATTR_MESSAGE]
            else:
                _settings["responseBodyHtml"] = call.data[ATTR_MESSAGE]
            settings: HttpRequest = (
                service.users()
                .settings()
                .updateVacation(userId=ATTR_ME, body=_settings)
            )
            await hass.async_add_executor_job(settings.execute)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_VACATION,
        schema=SERVICE_VACATION_SCHEMA,
        service_func=gmail_service,
    )
