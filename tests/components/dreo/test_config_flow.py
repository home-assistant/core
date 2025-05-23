"""Test the Dreo config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries, setup
from homeassistant.components.dreo.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def ignore_missing_translations() -> list[str]:
    """Ignore specific missing translations."""
    return [
        "component.dreo.config.step.user.data_description.username",
        "component.dreo.config.step.user.data_description.password",
    ]


@pytest.fixture(autouse=True)
def mock_config_entries_setup():
    """Disable setting up entries for config flow tests."""
    with patch("homeassistant.config_entries.ConfigEntries.async_setup"):
        yield


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "homeassistant", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result.get("errors") == {}

    with patch(
        "homeassistant.components.dreo.config_flow.DreoFlowHandler._validate_login",
        return_value=(True, None),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    data = result2["data"]
    assert data[CONF_USERNAME] == "test-username"

    assert CONF_PASSWORD in data


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dreo.config_flow.DreoFlowHandler._validate_login",
        return_value=(False, "invalid_auth"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dreo.config_flow.DreoFlowHandler._validate_login",
        return_value=(False, "cannot_connect"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
