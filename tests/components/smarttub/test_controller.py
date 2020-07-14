"""Test the SmartTub controller."""

import pytest
import smarttub

from homeassistant.components.smarttub.const import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
)
from homeassistant.components.smarttub.controller import SmartTubController
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.async_mock import create_autospec, patch
from tests.common import MockConfigEntry, MockEntity


@pytest.fixture(name="spa")
def mock_spa():
    """Mock a SmartTub.Spa."""

    mock_spa = create_autospec(smarttub.Spa, instance=True)
    mock_spa.id = "mockspa1"
    mock_spa.brand = "mockbrand1"
    mock_spa.model = "mockmodel1"
    mock_spa.get_status.return_value = {
        "setTemperature": "settemp1",
        "water": {"temperature": "watertemp1"},
        "heater": "heaterstatus1",
    }
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
        yield api_mock


@pytest.fixture(name="config_entry")
def config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
        options={},
    )


@pytest.fixture(name="controller")
async def make_controller(hass, smarttub_api, config_entry):
    """Instantiate the controller for testing."""

    controller = SmartTubController(hass)
    assert len(controller.spa_ids) == 0

    ret = await controller.async_setup_entry(config_entry)
    assert ret is True

    return controller


async def test_unload(controller, config_entry):
    """Test async_unload_entry."""
    ret = await controller.async_unload_entry(config_entry)
    assert ret is True


async def test_invalid_credentials(hass, controller, smarttub_api, config_entry):
    """Check that we start a new config flow if the configured credentials are invalid.

    This should mean that the user changed their SmartTub password.
    """

    smarttub_api.login.side_effect = smarttub.LoginFailed
    controller = SmartTubController(hass)
    with patch(
        "homeassistant.components.smarttub.controller.create_config_flow", autospec=True
    ) as create_config_flow:
        ret = await controller.async_setup_entry(config_entry)
        assert ret is False
        create_config_flow.assert_called()


async def test_update(controller, spa):
    """Test data updates from API."""
    data = await controller.async_update_data()
    assert data[spa.id] == {"status": spa.get_status.return_value}

    spa.get_status.side_effect = smarttub.APIError
    with pytest.raises(UpdateFailed):
        data = await controller.async_update_data()


async def test_entity(hass, controller):
    """Test SmartTubController entity interface."""

    entity = MockEntity(entity_id="entity.id1", unique_id="mockentity1")
    entity.hass = hass
    entity.spa_id = "mockspa1"
    await controller.async_register_entity(entity)
    await controller._coordinator.async_refresh()
    assert controller.entity_is_available(entity)

    entity = MockEntity(entity_id="entity.id1", unique_id="mockentity1")
    entity.hass = hass
    entity.spa_id = "notmockspa1"
    await controller.async_register_entity(entity)
    assert not controller.entity_is_available(entity)


async def test_get_account_id(controller, smarttub_api):
    """Test SmartTubController.validate_credentials."""
    smarttub_api.get_account.return_value.id = "account-id1"
    account_id = await controller.get_account_id("test-email1", "test-password1")
    smarttub_api.login.assert_called()
    assert account_id == "account-id1"

    smarttub_api.login.side_effect = smarttub.LoginFailed
    account_id = await controller.get_account_id("test-email1", "test-password1")
    assert account_id is None


def test_spa_metadata(controller):
    """Test spa metadata."""
    name = controller.get_spa_name("mockspa1")
    assert name == "mockbrand1 mockmodel1"


async def test_spa_temperatures(controller, spa):
    """Test temperature methods."""
    set_temp = controller.get_target_water_temperature("mockspa1")
    assert set_temp == "settemp1"

    water_temp = controller.get_current_water_temperature("mockspa1")
    assert water_temp == "watertemp1"

    heater_status = controller.get_heater_status("mockspa1")
    assert heater_status == "heaterstatus1"

    await controller.set_target_water_temperature("mockspa1", 38.3)
    spa.set_temperature.assert_called_with(38.3)

    assert controller.get_maximum_target_water_temperature("spaid1") == DEFAULT_MAX_TEMP
    assert controller.get_minimum_target_water_temperature("spaid1") == DEFAULT_MIN_TEMP
