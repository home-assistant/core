"""Tests for the GogoGate2 component."""
from unittest.mock import MagicMock

from gogogate2_api import GogoGate2Api

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_CREATE_ENTRY

from .common import INFO_RESPONSE, ComponentFactory


async def test_auth_fail(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test authorization failures."""
    api_mock: GogoGate2Api = MagicMock(spec=GogoGate2Api)

    await component_factory.configure_component()
    component_factory.api_class_mock.return_value = api_mock

    api_mock.info.side_effect = Exception("Error")
    result = await hass.config_entries.flow.async_init(
        "gogogate2", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        },
    )
    assert result
    assert result["type"] == RESULT_TYPE_ABORT

    api_mock.reset_mock()
    api_mock.info.side_effect = [INFO_RESPONSE, Exception("Error")]
    result = await hass.config_entries.flow.async_init(
        "gogogate2", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        },
    )
    assert result
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()

    assert not hass.states.async_entity_ids(COVER_DOMAIN)
