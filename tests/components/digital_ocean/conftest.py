"""Fixture definitions for digital_ocean."""

import json
import typing as t
from unittest.mock import MagicMock, patch

import digitalocean
import pytest

from homeassistant.components.digital_ocean import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import load_fixture

TOKEN = "my-fake-access-token"
DOMAIN_NAME = "example.com"


@pytest.fixture
def domain_name():
    """Return the domain name used in other fixtures. Default to example.com."""
    return DOMAIN_NAME


@pytest.fixture
def digital_ocean_config() -> dict[str, t.Any]:
    """Fixture for producing a valid config dict for this integration."""
    return {DOMAIN: {"access_token": TOKEN}}


@pytest.fixture
async def configured_hass(hass: HomeAssistant, digital_ocean_config):
    """Fixture to produce a hass object where this integration is configured."""
    result = await async_setup_component(hass, DOMAIN, digital_ocean_config)
    await hass.async_block_till_done()

    assert result is True, "Failed configuring Digital Ocean"

    return hass


@pytest.fixture(scope="module")
def account_fixture():
    """Fixture to load a JSON file for mocking the external API."""
    return json.loads(load_fixture("account.json", integration="digital_ocean"))


@pytest.fixture(scope="module")
def example_com_records_fixture():
    """Fixture to load a JSON file for mocking the external API."""
    return json.loads(load_fixture("domain_records.json", integration="digital_ocean"))


@pytest.fixture(autouse=True)
async def digital_ocean_account(account_fixture):
    """Fixture to patch the Digital Ocean API call for get account details."""
    with patch("digitalocean.Manager.Manager.get_account") as acc_patch:
        from digitalocean import Account

        acc = Account(token=TOKEN)

        for attr in account_fixture:
            setattr(acc, attr, account_fixture[attr])

        acc_patch.return_value = acc
        yield acc_patch


@pytest.fixture(autouse=True)
async def patched_domain(example_com_records_fixture, domain_name):
    """Fixture to patch the Digital Ocean API call to get domain records."""
    # Build Record objects from the fixtures
    records = []
    if domain_name == DOMAIN_NAME:
        for record_data in example_com_records_fixture:
            record = digitalocean.Record(domain_name=domain_name, **record_data)
            record.token = TOKEN
            records.append(record)

    with patch("digitalocean.Domain", autospec=True) as domain_factory:
        domain_factory.return_value.attach_mock(
            MagicMock(return_value=records), "get_records"
        )
        yield domain_factory
