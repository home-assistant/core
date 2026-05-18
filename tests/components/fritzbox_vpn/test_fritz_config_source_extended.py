"""Extended tests for Fritz config import."""

import pytest
from custom_components.fritzbox_vpn.fritz_config_source import (
    _entry_has_credentials,
    _host_username_password_from_entry,
    get_existing_fritz_config,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


def test_entry_has_credentials_from_options() -> None:
    """Credentials in options are detected."""
    entry = MockConfigEntry(
        domain="fritz",
        data={},
        options={CONF_USERNAME: "u"},
    )
    assert _entry_has_credentials(entry)


def test_host_from_nested_data() -> None:
    """Nested data dict host extraction."""
    entry = MockConfigEntry(
        domain="fritzbox",
        data={"data": {CONF_HOST: "10.0.0.1", CONF_USERNAME: "u", CONF_PASSWORD: "p"}},
    )
    result = _host_username_password_from_entry(entry)
    assert result is not None
    assert result[CONF_HOST] == "10.0.0.1"


@pytest.mark.asyncio
async def test_get_existing_skips_repeater(hass: HomeAssistant) -> None:
    """Repeater titles are skipped when searching Fritz domains."""
    repeater = MockConfigEntry(
        domain="fritz",
        title="FRITZ!WLAN Repeater",
        data={CONF_HOST: "10.0.0.2", CONF_USERNAME: "u", CONF_PASSWORD: "p"},
    )
    router = MockConfigEntry(
        domain="fritz",
        title="FRITZ!Box 7590",
        data={CONF_HOST: "192.168.178.1", CONF_USERNAME: "u", CONF_PASSWORD: "p"},
    )
    repeater.add_to_hass(hass)
    router.add_to_hass(hass)

    result = await get_existing_fritz_config(hass)
    assert result is not None
    assert result[CONF_HOST] == "192.168.178.1"


def test_host_from_entry_without_host() -> None:
    """Entries without host return None."""
    entry = MockConfigEntry(domain="fritz", data={CONF_USERNAME: "u"})
    assert _host_username_password_from_entry(entry) is None


def test_entry_has_credentials_password_only() -> None:
    """Password-only entries count as having credentials."""
    entry = MockConfigEntry(domain="fritz", data={CONF_PASSWORD: "p"})
    assert _entry_has_credentials(entry)
