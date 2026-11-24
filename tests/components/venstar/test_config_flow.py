"""Test the Venstar config flow."""

from collections.abc import Callable
import logging
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.venstar.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import VenstarColorTouchMock

_LOGGER = logging.getLogger(__name__)

TEST_DATA = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_PIN: "test-pin",
    CONF_SSL: False,
}
TEST_ID = "VenstarUniqueID"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
            new=VenstarColorTouchMock.update_info,
        ),
        patch(
            "homeassistant.components.venstar.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
            new=VenstarColorTouchMock.update_info,
        ),
        patch(
            "homeassistant.components.venstar.async_setup_entry",
            return_value=None,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    with (
        patch(
            "homeassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
            new=VenstarColorTouchMock.update_info,
        ),
        patch(
            "homeassistant.components.venstar.async_setup_entry",
            return_value=None,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test when provided credentials are already configured."""
    MockConfigEntry(domain=DOMAIN, data=TEST_DATA, unique_id=TEST_ID).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.venstar.VenstarColorTouch.update_info",
            new=VenstarColorTouchMock.update_info,
        ),
        patch(
            "homeassistant.components.venstar.async_setup_entry",
            return_value=None,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_import(hass: HomeAssistant) -> None:
    """Test importing a YAML configuration creates an entry."""
    with (
        patch(
            "homeassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
            new=VenstarColorTouchMock.update_info,
        ),
        patch(
            "homeassistant.components.venstar.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TEST_DATA
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == TEST_DATA


@pytest.mark.parametrize(
    ("update_info", "reason"),
    [
        pytest.param(
            VenstarColorTouchMock.failed_update_info,
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(VenstarColorTouchMock.broken_update_info, "unknown", id="unknown"),
    ],
)
async def test_import_error(
    hass: HomeAssistant, update_info: Callable[..., bool], reason: str
) -> None:
    """Test import errors abort the flow instead of showing a form."""
    with patch(
        "homeassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
        new=update_info,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TEST_DATA
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test importing an already configured host aborts."""
    MockConfigEntry(domain=DOMAIN, data=TEST_DATA, unique_id=TEST_ID).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TEST_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
