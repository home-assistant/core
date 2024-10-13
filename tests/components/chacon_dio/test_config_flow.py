"""Test the chacon_dio config flow."""

from unittest.mock import AsyncMock

from dio_chacon_wifi_api.exceptions import DIOChaconAPIError, DIOChaconInvalidAuthError
import pytest

from homeassistant.components.chacon_dio.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_dio_chacon_client: AsyncMock
) -> None:
    """Test the full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_USERNAME: "dummylogin",
            CONF_PASSWORD: "dummypass",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Chacon DiO dummylogin"
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
    exception: Exception,
    expected: dict[str, str],
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == expected

    # Test of recover in normal state after correction of the 1st error
    mock_dio_chacon_client.get_user_id.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "dummylogin",
            CONF_PASSWORD: "dummypass",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Chacon DiO dummylogin"
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

    mock_config_entry.add_to_hass(hass)

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
