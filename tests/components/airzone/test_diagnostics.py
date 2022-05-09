"""The diagnostics tests for the Airzone platform."""

from unittest.mock import patch

from aioairzone.const import (
    API_DATA,
    API_MAC,
    API_SYSTEM_ID,
    API_SYSTEMS,
    API_WIFI_RSSI,
    AZD_ID,
    AZD_MASTER,
    AZD_SYSTEM,
    AZD_SYSTEMS,
    AZD_ZONES,
    AZD_ZONES_NUM,
    RAW_HVAC,
    RAW_WEBSERVER,
)
from aiohttp import ClientSession

from homeassistant.components.airzone.const import DOMAIN
from homeassistant.components.diagnostics.const import REDACTED
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .util import CONFIG, HVAC_MOCK, HVAC_WEBSERVER_MOCK, async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_config_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSession
) -> None:
    """Test config entry diagnostics."""
    await async_init_integration(hass)
    assert hass.data[DOMAIN]

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.raw_data",
        return_value={
            RAW_HVAC: HVAC_MOCK,
            RAW_WEBSERVER: HVAC_WEBSERVER_MOCK,
        },
    ):
        diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert (
        diag["api_data"][RAW_HVAC][API_SYSTEMS][0][API_DATA][0].items()
        >= {
            API_SYSTEM_ID: HVAC_MOCK[API_SYSTEMS][0][API_DATA][0][API_SYSTEM_ID],
        }.items()
    )

    assert (
        diag["api_data"][RAW_WEBSERVER].items()
        >= {
            API_MAC: REDACTED,
            API_WIFI_RSSI: HVAC_WEBSERVER_MOCK[API_WIFI_RSSI],
        }.items()
    )

    assert (
        diag["config_entry"].items()
        >= {
            "data": {
                CONF_HOST: CONFIG[CONF_HOST],
                CONF_PORT: CONFIG[CONF_PORT],
            },
            "domain": DOMAIN,
            "unique_id": REDACTED,
        }.items()
    )

    assert (
        diag["coord_data"][AZD_SYSTEMS]["1"].items()
        >= {
            AZD_ID: 1,
            AZD_ZONES_NUM: 5,
        }.items()
    )

    assert (
        diag["coord_data"][AZD_ZONES]["1:1"].items()
        >= {
            AZD_ID: 1,
            AZD_MASTER: True,
            AZD_SYSTEM: 1,
        }.items()
    )
