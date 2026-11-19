"""SMLIGHT services."""

from enum import StrEnum

import probatio
from pysmlight.exceptions import SmlightError
from pysmlight.models import BuzzerPayload

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .coordinator import SmConfigEntry


class SmlightService(StrEnum):
    """Store keys for SMLIGHT services."""

    PLAY_RTTTL = "play_rtttl"


class SmlightServiceArgument(StrEnum):
    """Store keys for SMLIGHT service arguments."""

    DURATION = "duration"
    OCTAVE = "octave"
    BPM = "bpm"
    NOTES = "notes"


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
        notes = call.data[SmlightServiceArgument.NOTES]
        octave: int = call.data[SmlightServiceArgument.OCTAVE]
        bpm: int | None = call.data.get(SmlightServiceArgument.BPM)
        duration: int | None = call.data.get(SmlightServiceArgument.DURATION)

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

    schema = probatio.Schema(
        {
            probatio.Required(CommonServiceArgument.DEVICE_ID): probatio.All(
                probatio.EnsureList(), [cv.string]
            ),
            probatio.Optional(SmlightServiceArgument.DURATION): probatio.All(
                probatio.Coerce(int), probatio.In([1, 2, 4, 8, 16, 32])
            ),
            probatio.Required(SmlightServiceArgument.OCTAVE): probatio.All(
                probatio.Coerce(int), probatio.Range(min=4, max=7)
            ),
            probatio.Optional(SmlightServiceArgument.BPM): probatio.All(
                probatio.Coerce(int), probatio.In(RTTTL_VALID_BPMS)
            ),
            probatio.Required(SmlightServiceArgument.NOTES): cv.string,
        }
    )

    hass.services.async_register(
        DOMAIN,
        SmlightService.PLAY_RTTTL,
        async_play_rtttl,
        schema=schema,
    )
