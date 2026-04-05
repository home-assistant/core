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

ATTR_BPM = "bpm"
ATTR_DURATION = "duration"
ATTR_OCTAVE = "octave"
ATTR_NOTES = "notes"

RTTTL_VALID_BPMS: list[int] = [
    25,
    28,
    31,
    35,
    40,
    45,
    50,
    56,
    63,
    70,
    80,
    90,
    100,
    112,
    125,
    140,
    160,
    180,
    200,
    225,
    250,
    285,
    320,
    355,
    400,
    450,
    500,
    565,
    635,
    715,
    800,
    900,
]


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for SMLIGHT."""

    async def async_play_rtttl(call: ServiceCall) -> None:
        """Play RTTTL tone."""
        notes = call.data[ATTR_NOTES]
        octave: int = call.data[ATTR_OCTAVE]
        bpm: int | None = call.data.get(ATTR_BPM)
        duration: int | None = call.data.get(ATTR_DURATION)

        header: list[str] = []

        if duration is not None:
            header.append(f"d={duration}")
        header.append(f"o={octave}")
        if bpm is not None:
            header.append(f"b={bpm}")
        tone = f"S:{','.join(header)}:{notes}"

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
            vol.Optional(ATTR_DURATION): vol.All(
                vol.Coerce(int), vol.In([1, 2, 4, 8, 16, 32])
            ),
            vol.Required(ATTR_OCTAVE): vol.All(
                vol.Coerce(int), vol.Range(min=4, max=7)
            ),
            vol.Optional(ATTR_BPM): vol.All(vol.Coerce(int), vol.In(RTTTL_VALID_BPMS)),
            vol.Required(ATTR_NOTES): cv.string,
        }
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_RTTTL,
        async_play_rtttl,
        schema=schema,
    )
