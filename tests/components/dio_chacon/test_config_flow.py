"""Test the dio_chacon config flow."""

import logging
from unittest.mock import AsyncMock, patch

from dio_chacon_wifi_api.exceptions import DIOChaconAPIError

from homeassistant import config_entries
from homeassistant.components.dio_chacon.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

_LOGGER = logging.getLogger(__name__)


async def test_show_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""

    with patch(
        "dio_chacon_wifi_api.DIOChaconAPIClient.get_user_id",
        return_value="dummy-user-id",
    ) as mock_dio_chacon_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERNAME: "dummylogin",
                CONF_PASSWORD: "dummypass",
                CONF_UNIQUE_ID: "dummy-user-id",
            },
        )

        _LOGGER.debug("Test result after init : %s", result)

    assert len(mock_dio_chacon_client.mock_calls) == 1

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dio Chacon dummylogin"
    assert result["data"] == {
        CONF_USERNAME: "dummylogin",
        CONF_PASSWORD: "dummypass",
        CONF_UNIQUE_ID: "dummy-user-id",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "dio_chacon_wifi_api.DIOChaconAPIClient.get_user_id",
        side_effect=DIOChaconAPIError,
    ) as mock_dio_chacon_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERNAME: "nada",
                CONF_PASSWORD: "nadap",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert len(mock_dio_chacon_client.mock_calls) == 1


async def test_other_error(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we handle any error."""
    with patch(
        "dio_chacon_wifi_api.DIOChaconAPIClient.get_user_id",
        side_effect=Exception("Bad request Boy :) --"),
    ) as mock_dio_chacon_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERNAME: "nada",
                CONF_PASSWORD: "nadap",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    assert len(mock_dio_chacon_client.mock_calls) == 1
