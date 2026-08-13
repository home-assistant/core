"""Repair issue helpers for the SpaceXAI integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, ISSUE_MODEL_NOT_ENTITLED, ISSUE_SUBSCRIPTION_NOT_ENTITLED


@callback
def async_create_model_not_entitled_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    subentry_id: str,
    model: str,
) -> None:
    """Create a repair for a withdrawn conversation model."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_MODEL_NOT_ENTITLED}_{subentry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_MODEL_NOT_ENTITLED,
        translation_placeholders={"model": model},
        data={
            "entry_id": entry.entry_id,
            "subentry_id": subentry_id,
        },
    )


@callback
def async_create_subscription_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create an account-scoped subscription entitlement repair."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_SUBSCRIPTION_NOT_ENTITLED}_{entry.entry_id}",
        is_fixable=False,
        learn_more_url="https://console.x.ai/",
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_SUBSCRIPTION_NOT_ENTITLED,
    )


@callback
def async_delete_model_not_entitled_issue(
    hass: HomeAssistant,
    subentry_id: str,
) -> None:
    """Delete the model-not-entitled repair for a subentry if present."""
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_MODEL_NOT_ENTITLED}_{subentry_id}")


@callback
def async_delete_subscription_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the subscription-not-entitled repair for an entry if present."""
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_SUBSCRIPTION_NOT_ENTITLED}_{entry_id}")
