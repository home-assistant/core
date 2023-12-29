"""Test Govee Local API config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.govee_local_api.const import (
    CONF_BIND_ADDRESS,
    CONF_DISCOVERY_INTERVAL,
    CONF_LISENING_PORT,
    CONF_MULTICAST_ADDRESS,
    CONF_TARGET_PORT,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import DEFAULT_CONFIG, DEFAULT_UNIQUE_ID

from tests.common import MockConfigEntry


async def test_step_user(hass: HomeAssistant) -> None:
    """Test user step."""

    with patch(
        "homeassistant.components.network.async_get_source_ip",
        return_value="192.168.1.1",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM
    assert CONF_BIND_ADDRESS in result["data_schema"].schema
    assert CONF_DISCOVERY_INTERVAL in result["data_schema"].schema
    assert CONF_MULTICAST_ADDRESS not in result["data_schema"].schema
    assert CONF_TARGET_PORT not in result["data_schema"].schema
    assert CONF_LISENING_PORT not in result["data_schema"].schema

    with patch(
        "homeassistant.components.govee_local_api.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bind_address": "192.168.1.1"},
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "govee@192.168.1.1"
    assert result2["data"] == {"config": DEFAULT_CONFIG}
    assert result2["result"].unique_id == DEFAULT_UNIQUE_ID


async def test_step_user_advanced(hass: HomeAssistant) -> None:
    """Test user step with advanced config."""

    with patch(
        "homeassistant.components.network.async_get_source_ip",
        return_value="192.168.1.1",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_USER,
                "show_advanced_options": True,
            },
        )

    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM
    assert CONF_BIND_ADDRESS in result["data_schema"].schema
    assert CONF_DISCOVERY_INTERVAL in result["data_schema"].schema

    with patch(
        "homeassistant.components.govee_local_api.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_BIND_ADDRESS: "192.168.1.2",
                CONF_TARGET_PORT: 1234,
                CONF_LISENING_PORT: 4321,
            },
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "govee@192.168.1.2"
    assert result2["data"] == {
        "config": {
            CONF_BIND_ADDRESS: "192.168.1.2",
            CONF_MULTICAST_ADDRESS: "239.255.255.250",
            CONF_TARGET_PORT: 1234,
            CONF_LISENING_PORT: 4321,
            CONF_DISCOVERY_INTERVAL: 60,
        }
    }
    assert (
        result2["result"].unique_id
        == "GoveeLocalApi:192.168.1.2:4321:239.255.255.250:1234"
    )


async def test_async_step_already_configured(hass: HomeAssistant) -> None:
    """Test flow if there is already a config entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEFAULT_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.network.async_get_source_ip",
        return_value="192.168.1.1",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(
        "homeassistant.components.govee_local_api.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bind_address": "192.168.1.1"},
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_option_flow(hass: HomeAssistant) -> None:
    """Test option flow."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEFAULT_UNIQUE_ID,
        data={"config": DEFAULT_CONFIG},
    )
    entry.add_to_hass(hass)

    assert not entry.options

    with patch(
        "homeassistant.components.govee_local_api.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(
            entry.entry_id,
            data=None,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DISCOVERY_INTERVAL: 42},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_DISCOVERY_INTERVAL: 42}
