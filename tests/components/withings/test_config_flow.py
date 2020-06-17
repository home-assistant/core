"""Tests for config flow."""

from homeassistant.components.withings import const
from homeassistant.components.withings.config_flow import WithingsFlowHandler
from homeassistant.core import HomeAssistant

from tests.components.withings.common import ComponentFactory, new_profile_config


async def test_config_non_unique_profile(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test setup a non-unique profile."""
    person0 = new_profile_config("person0", 0)

    await component_factory.configure_component(profile_configs=(person0,))
    await component_factory.setup_profile(person0.user_id)

    flow_handler = WithingsFlowHandler()
    flow_handler.hass = hass
    flow_handler.context = {}
    result = await flow_handler.async_oauth_create_entry({"profile": person0.profile})
    assert result
    assert result["errors"]["base"] == "profile_exists"


async def test_config_reauth_profile(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test reauth an existing profile re-creates the config entry."""
    person0 = new_profile_config("person0", 0)

    await component_factory.configure_component(profile_configs=(person0,))
    await component_factory.setup_profile(person0.user_id)

    flow_handler = WithingsFlowHandler()
    flow_handler.hass = hass
    flow_handler.context = {"profile": person0.profile}
    result = await flow_handler.async_oauth_create_entry(
        {"token": {"userid": 0}, "profile": person0.profile}
    )
    assert result
    assert result["type"] == "create_entry"
    assert flow_handler.unique_id == "0"
    assert not hass.config_entries.async_entries(const.DOMAIN)
