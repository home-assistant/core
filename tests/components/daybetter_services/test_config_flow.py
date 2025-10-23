"""Test the DayBetter Services config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.daybetter_services.const import (
    CONF_TOKEN,
    CONF_USER_CODE,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.integrate",
            return_value={"code": 1, "data": {"hassCodeToken": "test_token_12345"}},
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_pids",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.close",
        ),
        patch(
            "homeassistant.components.daybetter_services.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USER_CODE: "123456"},
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "DayBetter Services"
        assert result2["data"] == {
            CONF_USER_CODE: "123456",
            CONF_TOKEN: "test_token_12345",
        }
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_code(hass: HomeAssistant) -> None:
    """Test we handle invalid code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.integrate",
            return_value={"code": 0, "msg": "Invalid code"},
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.close",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USER_CODE: "invalid"},
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "invalid_code"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.integrate",
            return_value={"code": 1, "data": {"hassCodeToken": "test_token"}},
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
            side_effect=Exception("Connection error"),
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.close",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USER_CODE: "123456"},
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_single_instance(hass: HomeAssistant) -> None:
    """Test that only one instance can be configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: "test_token"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
