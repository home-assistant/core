"""Tests for the laundrify integration."""

from spencerassistant.components.laundrify import DOMAIN
from spencerassistant.const import CONF_ACCESS_TOKEN
from spencerassistant.core import spencerAssistant

from .const import VALID_ACCESS_TOKEN, VALID_ACCOUNT_ID

from tests.common import MockConfigEntry


def create_entry(
    hass: spencerAssistant, access_token: str = VALID_ACCESS_TOKEN
) -> MockConfigEntry:
    """Create laundrify entry in spencer Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=VALID_ACCOUNT_ID,
        data={CONF_ACCESS_TOKEN: access_token},
    )
    entry.add_to_hass(hass)
    return entry
