"""SMLIGHT services."""

from __future__ import annotations

from pysmlight.exceptions import SmlightError
from pysmlight.models import BuzzerPayload
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .coordinator import SmConfigEntry

SERVICE_PLAY_RTTTL = "play_rtttl"

ATTR_TONE = "tone"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for SMLIGHT."""

    async def async_play_rtttl(call: ServiceCall) -> None:
        """Play RTTTL tone."""
        tone = call.data[ATTR_TONE]

        target_entry_ids = await async_extract_config_entry_ids(call)
        target_entries: list[SmConfigEntry] = [
            loaded_entry
            for loaded_entry in hass.config_entries.async_loaded_entries(DOMAIN)
            if loaded_entry.entry_id in target_entry_ids
        ]

        if not target_entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_device_found",
            )

        for target_entry in target_entries:
            coordinator = target_entry.runtime_data.data
            client = coordinator.client

            if not coordinator.data.info.has_peripherals:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="not_supported_buzzer",
                )

            try:
                await coordinator.async_execute_command(
                    client.actions.buzzer, BuzzerPayload(code=tone)
                )
            except SmlightError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="play_tone_failed",
                    translation_placeholders={
                        "device_name": target_entry.title,
                        "error": str(err),
                    },
                ) from err

    schema = vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Required(ATTR_TONE): cv.string,
        }
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_RTTTL,
        async_play_rtttl,
        schema=schema,
    )
