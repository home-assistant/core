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


@pytest.fixture(name="laundrify_exchange_code")
def laundrify_exchange_code_fixture():
    """Mock laundrify exchange_auth_code function."""
    with patch(
        "laundrify_aio.LaundrifyAPI.exchange_auth_code",
        return_value=VALID_ACCESS_TOKEN,
    ) as exchange_code_mock:
        yield exchange_code_mock


@pytest.fixture(name="laundrify_validate_token")
def laundrify_validate_token_fixture():
    """Mock laundrify validate_token function."""
    with patch(
        "laundrify_aio.LaundrifyAPI.validate_token",
        return_value=True,
    ) as validate_token_mock:
        yield validate_token_mock


@pytest.fixture(name="laundrify_api_mock", autouse=True)
def laundrify_api_fixture(laundrify_exchange_code, laundrify_validate_token):
    """Mock valid laundrify API responses."""
    with (
        patch(
            "laundrify_aio.LaundrifyAPI.get_account_id",
            return_value=VALID_ACCOUNT_ID,
        ),
        patch(
            "laundrify_aio.LaundrifyAPI.get_machines",
            return_value=[
                LaundrifyDevice(machine, LaundrifyAPI)
                for machine in json.loads(load_fixture("laundrify/machines.json"))
            ],
        ) as get_machines_mock,
    ):
        yield get_machines_mock
