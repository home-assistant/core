"""Test the SmartTub controller."""

import pytest
import smarttub

from homeassistant.components.smarttub.const import DOMAIN
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


@pytest.fixture(name="controller")
async def make_controller(hass, smarttub_api):
    """Instantiate the controller for testing."""

    controller = SmartTubController(hass)
    assert len(controller.spa_ids) == 0

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
        options={},
    )
    ret = await controller.async_setup(config_entry)
    assert ret is True

    return controller


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
    await controller.async_register_entity(entity)
    await controller.async_update_entity(entity)
    available = controller.entity_is_available(entity)
    assert available


async def test_validate_credentials(controller, smarttub_api):
    """Test SmartTubController.validate_credentials."""
    valid = await controller.validate_credentials("test-email1", "test-password1")
    smarttub_api.login.assert_called()
    assert valid is True

    smarttub_api.login.side_effect = smarttub.LoginFailed
    valid = await controller.validate_credentials("test-email1", "test-password1")
    assert valid is False


def test_spa_metadata(controller):
    """Test spa metadata."""
    name = controller.get_spa_name("mockspa1")
    assert name == "mockbrand1 mockmodel1"


def test_spa_temperatures(controller):
    """Test temperature methods."""
    set_temp = controller.get_target_water_temperature("mockspa1")
    assert set_temp == "settemp1"

    water_temp = controller.get_current_water_temperature("mockspa1")
    assert water_temp == "watertemp1"

    heater_status = controller.get_heater_status("mockspa1")
    assert heater_status == "heaterstatus1"
