"""Configure py.test."""

import json
from unittest.mock import patch

from laundrify_aio import LaundrifyAPI, LaundrifyDevice
import pytest

from homeassistant.components.laundrify import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from .const import VALID_ACCESS_TOKEN, VALID_ACCOUNT_ID

from tests.common import MockConfigEntry, load_fixture
from tests.typing import ClientSessionGenerator


@pytest.fixture(name="laundrify_config_entry")
async def laundrify_setup_config_entry(
    hass: HomeAssistant, access_token: str = VALID_ACCESS_TOKEN
) -> MockConfigEntry:
    """Create laundrify entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=VALID_ACCOUNT_ID,
        data={CONF_ACCESS_TOKEN: access_token},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture(name="laundrify_api_mock", autouse=True)
def laundrify_api_fixture(hass_client: ClientSessionGenerator):
    """Mock valid laundrify API responses."""
    with (
        patch(
            "laundrify_aio.LaundrifyAPI.get_account_id",
            return_value=VALID_ACCOUNT_ID,
        ),
        patch(
            "laundrify_aio.LaundrifyAPI.validate_token",
            return_value=True,
        ),
        patch(
            "laundrify_aio.LaundrifyAPI.exchange_auth_code",
            return_value=VALID_ACCESS_TOKEN,
        ),
        patch(
            "laundrify_aio.LaundrifyAPI.get_machines",
            return_value=[
                LaundrifyDevice(machine, LaundrifyAPI)
                for machine in json.loads(load_fixture("laundrify/machines.json"))
            ],
        ),
    ):
        yield LaundrifyAPI(VALID_ACCESS_TOKEN, hass_client)
