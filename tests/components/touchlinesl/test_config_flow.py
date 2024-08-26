"""Test the Roth Touchline SL config flow."""

from typing import NamedTuple
from unittest.mock import AsyncMock, patch

from pytouchlinesl.client import RothAPIError

from homeassistant import config_entries
from homeassistant.components.touchlinesl.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


class FakeModule(NamedTuple):
    """Fake Module used for unit testing only."""

    name: str
    id: str


FAKE_MODULES = [FakeModule(name="Foobar", id="deadbeef")]


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == "user"
    assert result1["errors"] == {}

    with patch("pytouchlinesl.TouchlineSL.modules", return_value=FAKE_MODULES):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == "user"
    assert result1["errors"] == {}

    with patch(
        "pytouchlinesl.TouchlineSL.modules", side_effect=RothAPIError(status=401)
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    with patch("pytouchlinesl.TouchlineSL.modules", return_value=FAKE_MODULES):
        result3 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "test-username"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == "user"
    assert result1["errors"] == {}

    with patch(
        "pytouchlinesl.TouchlineSL.modules", side_effect=RothAPIError(status=502)
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch("pytouchlinesl.TouchlineSL.modules", return_value=FAKE_MODULES):
        result3 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "test-username"
    assert len(mock_setup_entry.mock_calls) == 1
