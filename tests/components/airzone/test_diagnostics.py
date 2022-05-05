"""The diagnostics tests for the Airzone platform."""

from aioairzone.const import (
    AZD_ID,
    AZD_MASTER,
    AZD_SYSTEM,
    AZD_SYSTEMS,
    AZD_ZONES,
    AZD_ZONES_NUM,
)
from aiohttp import ClientSession

from homeassistant.components.airzone.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .util import CONFIG, async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_config_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSession
) -> None:
    """Test config entry diagnostics."""
    await async_init_integration(hass)
    assert hass.data[DOMAIN]

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert diag["info"][CONF_HOST] == CONFIG[CONF_HOST]
    assert diag["info"][CONF_PORT] == CONFIG[CONF_PORT]

    assert diag["data"][AZD_SYSTEMS]["1"][AZD_ID] == 1
    assert diag["data"][AZD_SYSTEMS]["1"][AZD_ZONES_NUM] == 5

    assert diag["data"][AZD_ZONES]["1:1"][AZD_ID] == 1
    assert diag["data"][AZD_ZONES]["1:1"][AZD_MASTER] == 1
    assert diag["data"][AZD_ZONES]["1:1"][AZD_SYSTEM] == 1

    assert diag["data"][AZD_ZONES]["1:2"][AZD_ID] == 2
    assert diag["data"][AZD_ZONES]["1:2"][AZD_MASTER] == 0
    assert diag["data"][AZD_ZONES]["1:2"][AZD_SYSTEM] == 1

    assert diag["data"][AZD_ZONES]["1:3"][AZD_ID] == 3
    assert diag["data"][AZD_ZONES]["1:3"][AZD_MASTER] == 0
    assert diag["data"][AZD_ZONES]["1:3"][AZD_SYSTEM] == 1

    assert diag["data"][AZD_ZONES]["1:4"][AZD_ID] == 4
    assert diag["data"][AZD_ZONES]["1:4"][AZD_MASTER] == 0
    assert diag["data"][AZD_ZONES]["1:4"][AZD_SYSTEM] == 1

    assert diag["data"][AZD_ZONES]["1:5"][AZD_ID] == 5
    assert diag["data"][AZD_ZONES]["1:5"][AZD_MASTER] == 0
    assert diag["data"][AZD_ZONES]["1:5"][AZD_SYSTEM] == 1
