"""Test the Universal Devices ISY/IoX integration init."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.isy994.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_UUID = "ce:fb:72:31:b7:b9"


async def test_migrate_minor_version_drops_tls(
    hass: HomeAssistant,
) -> None:
    """Test minor migration drops legacy "tls" and seeds verify_ssl."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={
            CONF_HOST: "http://1.1.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            "tls": 1.1,
        },
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert "tls" not in entry.data
    assert entry.data[CONF_VERIFY_SSL] is False


@pytest.mark.parametrize("verify_ssl", [True, False])
async def test_setup_forwards_verify_ssl_to_pyisy(
    hass: HomeAssistant,
    mock_isy: MagicMock,
    verify_ssl: bool,
) -> None:
    """Test the verify_ssl entry option is forwarded to the pyisy ISY constructor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        data={
            CONF_HOST: "https://1.1.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_VERIFY_SSL: verify_ssl,
        },
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.isy994.ISY", return_value=mock_isy
    ) as isy_constructor:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isy_constructor.call_args.kwargs["verify_ssl"] is verify_ssl
