"""The Fish Audio integration."""

from __future__ import annotations

import logging

from fish_audio_sdk import Session
from fish_audio_sdk.schemas import APICreditEntity

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

from .const import CONF_API_KEY, CRITICAL_CREDIT_BALANCE, DOMAIN, WARNING_CREDIT_BALANCE

PLATFORMS: list[Platform] = [Platform.STT, Platform.TTS]

_LOGGER = logging.getLogger(__name__)

FishAudioConfigEntry = ConfigEntry[Session]


async def async_setup_entry(hass: HomeAssistant, entry: FishAudioConfigEntry) -> bool:
    """Set up Fish Audio from a config entry."""

    session = await hass.async_add_executor_job(Session, entry.data[CONF_API_KEY])
    try:
        credit_info = await hass.async_add_executor_job(session.get_api_credit)
        async_check_credit_balance(hass, credit_info)

    except Exception as exc:
        raise ConfigEntryNotReady("Failed to validate API key") from exc

    entry.runtime_data = session

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FishAudioConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def async_check_credit_balance(
    hass: HomeAssistant, credit_info: APICreditEntity
) -> None:
    """Check the credit balance and create an issue if it is below the critical threshold."""
    if credit_info.credit < CRITICAL_CREDIT_BALANCE:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "low_credit_balance",
            is_fixable=False,
            severity=ir.IssueSeverity.CRITICAL,
            translation_key="low_credit_balance",
            translation_placeholders={"balance": str(credit_info.credit)},
            learn_more_url="https://fish.audio/app/billing/",
        )
    elif credit_info.credit < WARNING_CREDIT_BALANCE:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "low_credit_balance",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="low_credit_balance",
            translation_placeholders={"balance": str(credit_info.credit)},
            learn_more_url="https://fish.audio/app/billing/",
        )
