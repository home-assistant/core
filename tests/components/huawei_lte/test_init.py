"""Tests for the Huawei LTE integration setup."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import magic_client

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        pytest.param(
            {CONF_URL: "http://huawei-lte"},
            "Could not resolve serial number to use as unique ID for router at"
            " http://huawei-lte. Try setting up credentials for the router for one"
            " startup, unauthenticated mode can be enabled after that in integration"
            " settings",
            id="unauthenticated",
        ),
        pytest.param(
            {
                CONF_URL: "http://huawei-lte",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
            },
            "Could not resolve serial number to use as unique ID for router at"
            " http://huawei-lte",
            id="authenticated",
        ),
    ],
)
async def test_setup_serial_number_not_found(
    hass: HomeAssistant, data: dict[str, Any], reason: str
) -> None:
    """Test setup fails when the serial number can't be resolved."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    client = magic_client()
    client.device.information.return_value = {}
    with (
        patch("homeassistant.components.huawei_lte.Connection", MagicMock()),
        patch("homeassistant.components.huawei_lte.Client", return_value=client),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == reason
