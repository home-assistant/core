"""Tests of the initialization of the venstar integration."""

from unittest.mock import patch

from homeassistant.components.venstar import async_setup_entry, async_unload_entry
from homeassistant.components.venstar.const import DOMAIN as VENSTAR_DOMAIN
from homeassistant.const import CONF_HOST, CONF_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_HOST = "venstartest.localdomain"


async def test_setup_entry(hass: HomeAssistant):
    """Validate that setup entry also configure the client."""

    id = "VenTest"
    config_entry = MockConfigEntry(
        domain=VENSTAR_DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_SSL: False,
        },
        entry_id=id,
    )

    def setup_mock(_, __):
        return True

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        side_effect=setup_mock,
    ):
        await async_setup_entry(hass, config_entry)

    assert hass.data[VENSTAR_DOMAIN][id] is not None


async def test_unload_entry(hass: HomeAssistant):
    """Validate that unload entry also clear the client."""

    id = "VenTest"
    config_entry = MockConfigEntry(
        domain=VENSTAR_DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_SSL: False,
        },
        entry_id=id,
    )

    # Put random content at the location where the client should have been placed by setup
    hass.data.setdefault(VENSTAR_DOMAIN, {})[id] = config_entry

    await async_unload_entry(hass, config_entry)

    assert hass.data[VENSTAR_DOMAIN].get(id) is None
