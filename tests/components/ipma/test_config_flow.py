"""Tests for IPMA config flow."""

from unittest.mock import Mock, patch

from homeassistant.components.ipma import DOMAIN, config_flow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from .test_weather import MockLocation

from tests.common import MockConfigEntry, mock_registry


async def test_show_config_form():
    """Test show configuration form."""
    hass = Mock()
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    result = await flow._show_config_form()

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_show_config_form_default_values():
    """Test show configuration form."""
    hass = Mock()
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    result = await flow._show_config_form(name="test", latitude="0", longitude="0")

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_flow_with_home_location(hass):
    """Test config flow .

    Tests the flow when a default location is configured
    then it should return a form with default values
    """
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    hass.config.location_name = "Home"
    hass.config.latitude = 1
    hass.config.longitude = 1

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_flow_show_form():
    """Test show form scenarios first time.

    Test when the form should show when no configurations exists
    """
    hass = Mock()
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.ipma.config_flow.IpmaFlowHandler._show_config_form"
    ) as config_form:
        await flow.async_step_user()
        assert len(config_form.mock_calls) == 1


async def test_flow_entry_created_from_user_input():
    """Test that create data from user input.

    Test when the form should show when no configurations exists
    """
    hass = Mock()
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    test_data = {"name": "home", CONF_LONGITUDE: "0", CONF_LATITUDE: "0"}

    # Test that entry created when user_input name not exists
    with patch(
        "homeassistant.components.ipma.config_flow.IpmaFlowHandler._show_config_form"
    ) as config_form, patch.object(
        flow.hass.config_entries,
        "async_entries",
        return_value=[],
    ) as config_entries:

        result = await flow.async_step_user(user_input=test_data)

        assert result["type"] == "create_entry"
        assert result["data"] == test_data
        assert len(config_entries.mock_calls) == 1
        assert not config_form.mock_calls


async def test_flow_entry_config_entry_already_exists():
    """Test that create data from user input and config_entry already exists.

    Test when the form should show when user puts existing name
    in the config gui. Then the form should show with error
    """
    hass = Mock()
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    test_data = {"name": "home", CONF_LONGITUDE: "0", CONF_LATITUDE: "0"}

    # Test that entry created when user_input name not exists
    with patch(
        "homeassistant.components.ipma.config_flow.IpmaFlowHandler._show_config_form"
    ) as config_form, patch.object(
        flow.hass.config_entries, "async_entries", return_value={"home": test_data}
    ) as config_entries:

        await flow.async_step_user(user_input=test_data)

        assert len(config_form.mock_calls) == 1
        assert len(config_entries.mock_calls) == 1
        assert len(flow._errors) == 1


async def test_config_entry_migration(hass):
    """Tests config entry without mode in unique_id can be migrated."""
    ipma_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        data={CONF_LATITUDE: 0, CONF_LONGITUDE: 0, CONF_MODE: "daily"},
    )
    ipma_entry.add_to_hass(hass)

    ipma_entry2 = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        data={CONF_LATITUDE: 0, CONF_LONGITUDE: 0, CONF_MODE: "hourly"},
    )
    ipma_entry2.add_to_hass(hass)

    mock_registry(
        hass,
        {
            "weather.hometown": entity_registry.RegistryEntry(
                entity_id="weather.hometown",
                unique_id="0, 0",
                platform="ipma",
                config_entry_id=ipma_entry.entry_id,
            ),
            "weather.hometown_2": entity_registry.RegistryEntry(
                entity_id="weather.hometown_2",
                unique_id="0, 0, hourly",
                platform="ipma",
                config_entry_id=ipma_entry.entry_id,
            ),
        },
    )

    with patch(
        "homeassistant.components.ipma.weather.async_get_location",
        return_value=MockLocation(),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        ent_reg = await entity_registry.async_get_registry(hass)

        weather_home = ent_reg.async_get("weather.hometown")
        assert weather_home.unique_id == "0, 0, daily"

        weather_home2 = ent_reg.async_get("weather.hometown_2")
        assert weather_home2.unique_id == "0, 0, hourly"
