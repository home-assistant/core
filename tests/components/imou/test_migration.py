"""Tests for Imou config entry migration."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.imou.const import (
    API_URLS,
    CONF_API_URL,
    CONF_APP_ID,
    CONF_APP_SECRET,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import CONFIG_ENTRY_DATA


@pytest.mark.parametrize(
    ("saved_region", "kept_host"),
    [
        ("eu", "openapi-or.easy4ip.com"),
        ("na", "openapi-fk.easy4ip.com"),
    ],
)
@pytest.mark.usefixtures("mock_imou_ha_device_manager")
async def test_migrate_swapped_region_keeps_previous_host(
    hass: HomeAssistant,
    saved_region: str,
    kept_host: str,
) -> None:
    """A saved Europe or North America entry keeps the server it already used."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_ENTRY_DATA, CONF_API_URL: saved_region},
        unique_id=CONFIG_ENTRY_DATA[CONF_APP_ID],
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.imou.ImouOpenApiClient",
        autospec=True,
    ) as client_cls:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.data[CONF_API_URL] == {"eu": "na", "na": "eu"}[saved_region]
    client_cls.assert_called_once_with(
        CONFIG_ENTRY_DATA[CONF_APP_ID],
        CONFIG_ENTRY_DATA[CONF_APP_SECRET],
        kept_host,
    )


@pytest.mark.parametrize("region", ["sg", "cn"])
@pytest.mark.usefixtures("mock_imou_ha_device_manager")
async def test_migrate_unchanged_region_only_bumps_version(
    hass: HomeAssistant,
    region: str,
) -> None:
    """Singapore and China were already stored against the right server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_ENTRY_DATA, CONF_API_URL: region},
        unique_id=CONFIG_ENTRY_DATA[CONF_APP_ID],
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.imou.ImouOpenApiClient",
        autospec=True,
    ) as client_cls:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.data[CONF_API_URL] == region
    client_cls.assert_called_once_with(
        CONFIG_ENTRY_DATA[CONF_APP_ID],
        CONFIG_ENTRY_DATA[CONF_APP_SECRET],
        API_URLS[region],
    )


@pytest.mark.usefixtures("mock_imou_ha_device_manager")
async def test_current_region_entry_is_not_swapped(hass: HomeAssistant) -> None:
    """An entry created after the correction keeps the region the user chose."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_ENTRY_DATA, CONF_API_URL: "eu"},
        unique_id=CONFIG_ENTRY_DATA[CONF_APP_ID],
        minor_version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.imou.ImouOpenApiClient",
        autospec=True,
    ) as client_cls:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.data[CONF_API_URL] == "eu"
    client_cls.assert_called_once_with(
        CONFIG_ENTRY_DATA[CONF_APP_ID],
        CONFIG_ENTRY_DATA[CONF_APP_SECRET],
        API_URLS["eu"],
    )
