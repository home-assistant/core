"""Test the dio_chacon config flow."""

import logging
from unittest.mock import AsyncMock

from dio_chacon_wifi_api.exceptions import DIOChaconAPIError, DIOChaconInvalidAuthError
import pytest

from homeassistant.components.dio_chacon.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_COVER_DEVICE

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_dio_chacon_client: AsyncMock
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] is SOURCE_USER

    mock_dio_chacon_client.get_user_id.return_value = "dummy-user-id"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_USERNAME: "dummylogin",
            CONF_PASSWORD: "dummypass",
        },
    )

    _LOGGER.debug("Test result after init : %s", result)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dio Chacon dummylogin"
    assert result["result"].unique_id == "dummy-user-id"
    assert result["data"] == {
        CONF_USERNAME: "dummylogin",
        CONF_PASSWORD: "dummypass",
    }


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (Exception("Bad request Boy :) --"), {"base": "unknown"}),
        (DIOChaconInvalidAuthError, {"base": "invalid_auth"}),
        (DIOChaconAPIError, {"base": "cannot_connect"}),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_dio_chacon_client: AsyncMock,
    exception,
    expected,
) -> None:
    """Test we handle any error."""
    mock_dio_chacon_client.get_user_id.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_USERNAME: "nada",
            CONF_PASSWORD: "nadap",
        },
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == expected

    # Test of recover in normal state after correction of the 1st error
    mock_dio_chacon_client.get_user_id.side_effect = None
    mock_dio_chacon_client.get_user_id.return_value = "dummy-user-id"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "dummylogin",
            CONF_PASSWORD: "dummypass",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dio Chacon dummylogin"
    assert result["result"].unique_id == "dummy-user-id"
    assert result["data"] == {
        CONF_USERNAME: "dummylogin",
        CONF_PASSWORD: "dummypass",
    }


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test abort when setting up duplicate entry."""

    mock_dio_chacon_client.search_all_devices.return_value = MOCK_COVER_DEVICE
    mock_config_entry.add_to_hass(hass)

    _LOGGER.debug("Test duplicate entry by launching a config flow")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    mock_dio_chacon_client.get_user_id.return_value = "test_entry_unique_id"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "dummylogin",
            CONF_PASSWORD: "dummypass",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
