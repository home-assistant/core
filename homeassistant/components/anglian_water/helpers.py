"""Helpers for the Anglian Water integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import CONF_ACCOUNT_NUMBER, DOMAIN

LEARN_MORE_URL = "https://myaccount.anglianwater.co.uk/"


def consent_required_issue_id(account_number: str) -> str:
    """Return the repair issue id for a consent-required condition."""
    return f"consent_required_{account_number}"


def async_create_consent_required_issue(
    hass: HomeAssistant, account_number: str
) -> None:
    """Create a repair issue directing the user to accept updated terms."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        consent_required_issue_id(account_number),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="consent_required",
        translation_placeholders={
            CONF_ACCOUNT_NUMBER: account_number,
        },
        learn_more_url=LEARN_MORE_URL,
    )


def async_delete_consent_required_issue(
    hass: HomeAssistant, account_number: str
) -> None:
    """Delete the consent-required repair issue if it exists."""
    ir.async_delete_issue(
        hass,
        DOMAIN,
        consent_required_issue_id(account_number),
    )
