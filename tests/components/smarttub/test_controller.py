"""Test the SmartTub controller."""

import pytest
import smarttub

from homeassistant.components.smarttub.const import DOMAIN
from homeassistant.components.smarttub.controller import SmartTubController
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.async_mock import create_autospec, patch
from tests.common import MockConfigEntry


@pytest.fixture(name="spa")
def mock_spa():
    """Mock a SmartTub.Spa."""
    mock_spa = create_autospec(smarttub.Spa, instance=True)
    mock_spa.id = "mockspa1"
    mock_spa.brand = "mockbrand1"
    mock_spa.model = "mockmodel1"
    return mock_spa


@pytest.fixture(name="account")
def mock_account(spa):
    """Mock a SmartTub.Account."""
    mock_account = create_autospec(smarttub.Account, instance=True)
    mock_account.id = "mockaccount1"
    mock_account.get_spas.return_value = [spa]
    return mock_account


@pytest.fixture(name="smarttub_api")
def mock_api(account):
    """Mock the SmartTub API."""
    with patch(
        "homeassistant.components.smarttub.controller.SmartTub", autospec=True,
    ) as api_class_mock:
        api_mock = api_class_mock.return_value
        api_mock.get_account.return_value = account
        yield api_class_mock


async def test_controller_setup(hass, smarttub_api, account, spa):
    """Test SmartTubController setup."""
    controller = SmartTubController(hass)
    assert len(controller.spa_ids) == 0

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
        options={},
    )
    smarttub_api.get_account.return_value.get_spas.return_value = [spa]
    ret = await controller.async_setup(config_entry)
    assert ret is True
