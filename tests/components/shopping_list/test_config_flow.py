"""Test config flow."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.shopping_list.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_import(hass: HomeAssistant) -> None:
    """Test entry will be imported."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None


async def test_user(hass: HomeAssistant) -> None:
    """Test we can start a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_confirm(hass: HomeAssistant) -> None:
    """Test we can finish a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {}
    assert result["result"].unique_id is None


async def test_onboarding_flow(hass: HomeAssistant) -> None:
    """Test the onboarding configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "onboarding"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Shopping list"
    assert result["data"] == {}
    assert result["result"].unique_id is None


@pytest.mark.parametrize("unique_id", [None, DOMAIN])
@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_IMPORT, "onboarding"])
async def test_single_instance_allowed(
    hass: HomeAssistant, source: str, unique_id: str | None
) -> None:
    """Test a second config entry is not allowed."""
    MockConfigEntry(domain=DOMAIN, unique_id=unique_id).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
