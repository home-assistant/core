"""Test the Sveriges Radio config flow."""
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sveriges_radio.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    # with patch(
    #     # "homeassistant.components.sveriges_radio.config_flow.PlaceholderHub.authenticate",
    #     "homeassistant.components.sveriges_radio.config_flow.async_get_options_flow",
    #     return_value=True,
    # ):
    # result2 = await hass.config_entries.flow.async_configure(
    #     result["flow_id"],
    #     {
    #         "host": "1.1.1.1",
    #         "username": "test-username",
    #         "password": "test-password",
    #     },
    # )
    # await hass.async_block_till_done()
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "area": "Örebro",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Sveriges Radio Traffic"  # Should fix: Remove traffic
    assert result2["data"] == {
        "area": "Örebro",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_traffic_area(hass: HomeAssistant) -> None:
    """Test that an invalid area raises an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with pytest.raises(vol.error.MultipleInvalid):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "area": "",
            },
        )
        await hass.async_block_till_done()


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    entry = MockConfigEntry(domain=DOMAIN, data={"area": "Örebro"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


# async def test_form_invalid_auth(hass: HomeAssistant) -> None:
#     """Test we handle invalid auth."""
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": config_entries.SOURCE_USER}
#     )

#     with patch(
#         "homeassistant.components.sveriges_radio_audio.config_flow.PlaceholderHub.authenticate",
#         side_effect=InvalidAuth,
#     ):
#         result2 = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             {
#                 "host": "1.1.1.1",
#                 "username": "test-username",
#                 "password": "test-password",
#             },
#         )

#     assert result2["type"] == FlowResultType.FORM
#     assert result2["errors"] == {"base": "invalid_auth"}


# async def test_form_cannot_connect(hass: HomeAssistant) -> None:
#     """Test we handle cannot connect error."""
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": config_entries.SOURCE_USER}
#     )

#     with patch(
#         "homeassistant.components.sveriges_radio_audio.config_flow.PlaceholderHub.authenticate",
#         side_effect=CannotConnect,
#     ):
#         result2 = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             {
#                 "host": "1.1.1.1",
#                 "username": "test-username",
#                 "password": "test-password",
#             },
#         )

#     assert result2["type"] == FlowResultType.FORM
#     assert result2["errors"] == {"base": "cannot_connect"}
