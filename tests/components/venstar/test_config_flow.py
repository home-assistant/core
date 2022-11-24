"""Test the Venstar config flow."""
import logging
from unittest.mock import patch

from spencerassistant import config_entries
from spencerassistant.components.venstar.const import DOMAIN
from spencerassistant.config_entries import SOURCE_USER
from spencerassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SSL,
    CONF_USERNAME,
)
from spencerassistant.core import spencerAssistant
from spencerassistant.data_entry_flow import FlowResultType

from . import VenstarColorTouchMock

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

TEST_DATA = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_PIN: "test-pin",
    CONF_SSL: False,
}
TEST_ID = "VenstarUniqueID"


async def test_form(hass: spencerAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "spencerassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
        new=VenstarColorTouchMock.update_info,
    ), patch(
        "spencerassistant.components.venstar.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: spencerAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "spencerassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_unknown_error(hass: spencerAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "spencerassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_already_configured(hass: spencerAssistant) -> None:
    """Test when provided credentials are already configured."""
    MockConfigEntry(domain=DOMAIN, data=TEST_DATA, unique_id=TEST_ID).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER

    with patch(
        "spencerassistant.components.venstar.VenstarColorTouch.update_info",
        new=VenstarColorTouchMock.update_info,
    ), patch(
        "spencerassistant.components.venstar.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
