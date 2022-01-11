"""Tests for the sleepiq component."""

from unittest.mock import Mock

from homeassistant.components.sleepiq.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


async def init_integration(
    hass: HomeAssistant, mock: Mock, single: bool = False
) -> MockConfigEntry:
    """Set up the SleepIQ integration in Home Assistant."""
    mock_responses(mock, single)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_SCAN_INTERVAL: 60,
        },
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


def mock_responses(mock, single=False) -> None:
    """Mock responses for SleepIQ."""
    base_url = "https://prod-api.sleepiq.sleepnumber.com/rest/"
    if single:
        suffix = "-single"
    else:
        suffix = ""
    mock.put(base_url + "login", text=load_fixture("login.json", "sleepiq"))
    mock.get(
        base_url + "bed?_k=0987",
        text=load_fixture(f"bed{suffix}.json", "sleepiq"),
    )
    mock.get(
        base_url + "sleeper?_k=0987",
        text=load_fixture("sleeper.json", "sleepiq"),
    )
    mock.get(
        base_url + "bed/familyStatus?_k=0987",
        text=load_fixture(f"familystatus{suffix}.json", "sleepiq"),
    )
