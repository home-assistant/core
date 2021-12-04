"""Test the Balboa Spa Client config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.balboa.const import CONF_SYNC_TIME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import BalboaMock

from tests.common import MockConfigEntry

TEST_DATA = {
    CONF_HOST: "1.1.1.1",
}
TEST_ID = "FakeBalboa"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi.connect",
        new=BalboaMock.connect,
    ), patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi.disconnect",
        new=BalboaMock.disconnect,
    ), patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi.listen",
        new=BalboaMock.listen,
    ), patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi.send_mod_ident_req",
        new=BalboaMock.send_mod_ident_req,
    ), patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi.send_panel_req",
        new=BalboaMock.send_panel_req,
    ), patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi.spa_configured",
        new=BalboaMock.spa_configured,
    ), patch(
        "homeassistant.components.balboa.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi.connect",
        new=BalboaMock.broken_connect,
    ), patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi.disconnect",
        new=BalboaMock.disconnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi.connect",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test when provided credentials are already configured."""
    MockConfigEntry(domain=DOMAIN, data=TEST_DATA, unique_id=TEST_ID).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER

    with patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi.connect",
        new=BalboaMock.connect,
    ), patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi.disconnect",
        new=BalboaMock.disconnect,
    ), patch(
        "homeassistant.components.balboa.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"


async def test_options_flow(hass):
    """Test specifying non default settings using options flow."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_DATA, unique_id=TEST_ID)
    config_entry.add_to_hass(hass)

    # Rather than mocking out 15 or so functions, we just need to mock
    # the entire library, otherwise it will get stuck in a listener and
    # the various loops in pybalboa.
    with patch(
        "homeassistant.components.balboa.config_flow.BalboaSpaWifi",
        new=BalboaMock,
    ), patch(
        "homeassistant.components.balboa.BalboaSpaWifi",
        new=BalboaMock,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SYNC_TIME: True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {CONF_SYNC_TIME: True}
