"""Tests for the GogoGate2 component."""
from homeassistant.components.gogogate2.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_FORM

from .common import ComponentFactory


async def test_options_change(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test test1."""
    await component_factory.configure_component()
    await component_factory.run_config_flow(
        config_data={
            CONF_NAME: "cover0",
            CONF_IP_ADDRESS: "127.0.1.0",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        }
    )

    assert hass.states.get("cover.cover0")

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert config_entries
    assert len(config_entries) == 1

    config_entry = config_entries[0]
    assert config_entry.data[CONF_NAME] == "cover0"
    assert config_entry.data[CONF_IP_ADDRESS] == "127.0.1.0"
    assert config_entry.data[CONF_USERNAME] == "user0"
    assert config_entry.data[CONF_PASSWORD] == "password0"

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "cover1",
            CONF_IP_ADDRESS: "127.0.1.1",
            CONF_USERNAME: "user1",
            CONF_PASSWORD: "password1",
        },
    )
    assert result
    assert result["type"] == "create_entry"
    assert result["data"] == {
        CONF_NAME: "cover1",
        CONF_IP_ADDRESS: "127.0.1.1",
        CONF_USERNAME: "user1",
        CONF_PASSWORD: "password1",
    }

    await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert config_entries
    assert len(config_entries) == 1
    assert config_entries[0].title == "cover1"

    assert not hass.states.get("cover.cover0")
    assert hass.states.get("cover.cover1")
