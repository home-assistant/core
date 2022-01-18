"""Define tests for AirVisual diagnostics."""
from unittest.mock import patch

import pytest

from homeassistant.components.airvisual.const import (
    CONF_CITY,
    CONF_COUNTRY,
    CONF_GEOGRAPHIES,
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    INTEGRATION_TYPE_GEOGRAPHY_NAME,
    INTEGRATION_TYPE_NODE_PRO,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, hass_client):
    """Test that entry diagnostics are generated correctly."""
    geography_conf = {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="51.528308, -0.3817765", data=geography_conf
    )
    entry.add_to_hass(hass)

    with patch("pyairvisual.air_quality.AirQuality.city"), patch(
        "pyairvisual.air_quality.AirQuality.nearest_city"
    ), patch.object(hass.config_entries, "async_forward_entry_setup"):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: geography_conf})
        await hass.async_block_till_done()

    # print(await get_diagnostics_for_config_entry(hass, hass_client, entry))
