import json
import typing as t
from unittest.mock import patch

import pytest

from homeassistant.components.digital_ocean import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from tests.common import load_fixture

TOKEN = "my-fake-access-token"
DOMAIN_NAME = 'example.com'


@pytest.fixture()
def digital_ocean_config() -> dict[str, t.Any]:
    return {
        DOMAIN: {
            "access_token": TOKEN
        }
    }


@pytest.fixture()
async def configured_hass(hass: HomeAssistant, digital_ocean_config):
    """Define a config entry fixture."""
    result = await async_setup_component(hass, DOMAIN, digital_ocean_config)
    await hass.async_block_till_done()

    assert result is True, "Failed configuring Digital Ocean"

    yield hass


@pytest.fixture(scope='module')
def account_fixture():
    return json.loads(
        load_fixture('account.json', integration='digital_ocean')
    )


@pytest.fixture(scope='module')
def domain_records_fixture():
    return json.loads(
        load_fixture('domain_records.json', integration='digital_ocean')
    )


@pytest.fixture(autouse=True)
async def digital_ocean_account(account_fixture):
    with patch('digitalocean.Manager.Manager.get_account') as acc_patch:
        from digitalocean import Account
        acc = Account(token=TOKEN)

        for attr in account_fixture.keys():
            setattr(acc, attr, account_fixture[attr])

        acc_patch.return_value = acc
        yield acc_patch


@pytest.fixture(autouse=True)
async def example_com_records(domain_records_fixture):
    with patch('digitalocean.Domain.Domain.get_records') as records_patch:
        from digitalocean import Record

        records = []
        for record_data in domain_records_fixture:
            record = Record(domain_name=DOMAIN_NAME, **record_data)
            record.token = TOKEN
            records.append(record)

        records_patch.return_value = records
        yield records_patch

