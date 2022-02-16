"""Common methods for SleepIQ."""
import re
from unittest.mock import patch

from aioresponses import aioresponses
import pytest

from homeassistant.components.sleepiq import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_aioresponse():
    """Mock responses for SleepIQ."""
    BASE_URL = "https://prod-api.sleepiq.sleepnumber.com/rest/"
    with aioresponses() as m:
        m.put(BASE_URL + "login", body=load_fixture("sleepiq/login.json"))
        m.get(BASE_URL + "bed?_k=0987", body=load_fixture("sleepiq/bed.json"))
        m.get(BASE_URL + "sleeper?_k=0987", body=load_fixture("sleepiq/sleeper.json"))
        m.get(
            BASE_URL + "bed/familyStatus?_k=0987",
            body=load_fixture("sleepiq/familystatus.json"),
        )
        m.get(re.compile(BASE_URL + ".*/foundation/.*"), status=404, repeat=True)
        m.get(re.compile(BASE_URL + ".*/pauseMode"), payload={"pauseMode": "off"})
        m.put(re.compile(BASE_URL + ".*/pauseMode"), repeat=True)

        yield m


async def setup_platform(hass: HomeAssistant, platform) -> MockConfigEntry:
    """Set up the SleepIQ platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
        },
    )
    mock_entry.add_to_hass(hass)

    if platform:
        with patch("homeassistant.components.sleepiq.PLATFORMS", [platform]):
            assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    return mock_entry
