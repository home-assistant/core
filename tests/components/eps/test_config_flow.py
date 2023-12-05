"""Test the EPS Alarm config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.eps.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_DATA = {
    CONF_USERNAME: "Bob",
    CONF_PASSWORD: "my password",
    CONF_TOKEN: "DSJDKSHDJKZHE",
}

TEST_SITE = "123"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.eps.config_flow.EPS.get_status",
        return_value=1,
    ), patch(
        "homeassistant.components.eps.config_flow.EPS.get_site",
        return_value=TEST_SITE,
    ), patch(
        "homeassistant.components.eps.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_DATA[CONF_USERNAME]
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.eps.config_flow.EPS.get_site",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.eps.config_flow.EPS.get_site",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_exists(hass: HomeAssistant) -> None:
    """Test that a flow with an existing host aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SITE,
        data=TEST_DATA,
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.eps.config_flow.EPS.get_site",
        return_value=TEST_SITE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
