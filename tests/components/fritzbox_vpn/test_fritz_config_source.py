"""Tests for Fritz config import from other integrations."""


import pytest
from custom_components.fritzbox_vpn.fritz_config_source import (
    _entry_has_credentials,
    _host_username_password_from_entry,
    get_existing_fritz_config,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


def test_entry_has_credentials() -> None:
    """Detect username/password on config entries."""
    entry = MockConfigEntry(
        domain="fritz",
        data={CONF_USERNAME: "u", CONF_PASSWORD: "p"},
    )
    assert _entry_has_credentials(entry)


def test_host_username_password_from_entry() -> None:
    """Extract connection fields from Fritz entry data."""
    entry = MockConfigEntry(
        domain="fritz",
        data={CONF_HOST: "192.168.178.1", CONF_USERNAME: "u", CONF_PASSWORD: "p"},
    )
    result = _host_username_password_from_entry(entry)
    assert result is not None
    assert result[CONF_HOST] == "192.168.178.1"


@pytest.mark.asyncio
async def test_get_existing_fritz_config(hass: HomeAssistant) -> None:
    """Return credentials from existing fritz domain entry."""
    fritz_entry = MockConfigEntry(
        domain="fritz",
        data={CONF_HOST: "192.168.178.1", CONF_USERNAME: "u", CONF_PASSWORD: "p"},
    )
    fritz_entry.add_to_hass(hass)

    result = await get_existing_fritz_config(hass)
    assert result is not None
    assert result[CONF_HOST] == "192.168.178.1"


@pytest.mark.asyncio
async def test_get_existing_fritz_config_none(hass: HomeAssistant) -> None:
    """Return None when no Fritz integration is configured."""
    assert await get_existing_fritz_config(hass) is None
