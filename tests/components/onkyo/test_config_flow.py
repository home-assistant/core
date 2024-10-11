"""Test Onkyo config flow."""

# from typing import Any
# from unittest import mock
from unittest.mock import patch

from homeassistant.components.onkyo.config_flow import OnkyoConfigFlow

# import eiscp
# import pytest
# from homeassistant import config_entries
from homeassistant.components.onkyo.const import (
    #     CONF_RECEIVER_MAX_VOLUME,
    DOMAIN,
    #     OPTION_MAX_VOLUME,
    #     OPTION_SOURCES,
)
from homeassistant.config_entries import SOURCE_USER

# from homeassistant.const import (
#     CONF_DEVICE,
#     CONF_HOST,
#     CONF_MAC,
#     CONF_MODEL,
#     CONF_NAME,
#     CONF_PORT,
# )
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# from . import create_empty_config_entry, create_receiver_info, setup_integration
from . import create_receiver_info

from tests.common import Mock

# from tests.common import MockConfigEntry


async def test_user_initial_menu(hass: HomeAssistant) -> None:
    """Test initial menu."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert init_result["type"] is FlowResultType.MENU
    # Check if the values are there, but ignore order
    assert not set(init_result["menu_options"]) ^ {"manual", "eiscp_discovery"}


async def test_manual_valid_host(hass: HomeAssistant) -> None:
    """Test valid host entered."""

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "manual"},
    )

    mock_info = Mock()
    mock_info.identifier = "mock_id"
    mock_info.host = "mock_host"
    mock_info.model_name = "mock_model"

    with patch(
        "homeassistant.components.onkyo.config_flow.async_interview",
        return_value=mock_info,
    ):
        configure_result = await hass.config_entries.flow.async_configure(
            form_result["flow_id"],
            user_input={CONF_HOST: "sample-host-name"},
        )

        assert configure_result["step_id"] == "configure_receiver"
        assert (
            configure_result["description_placeholders"]["name"]
            == "mock_model (mock_host)"
        )


async def test_manual_invalid_host(hass: HomeAssistant) -> None:
    """Test invalid host entered."""

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "manual"},
    )

    with patch(
        "homeassistant.components.onkyo.config_flow.async_interview", return_value=None
    ):
        configure_result = await hass.config_entries.flow.async_configure(
            form_result["flow_id"],
            user_input={CONF_HOST: "sample-host-name"},
        )

    assert configure_result["step_id"] == "manual"
    assert configure_result["errors"]["base"] == "cannot_connect"


async def test_manual_valid_host_unexpected_error(hass: HomeAssistant) -> None:
    """Test valid host entered."""

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "manual"},
    )

    with patch(
        "homeassistant.components.onkyo.config_flow.async_interview",
        side_effect=Exception(),
    ):
        configure_result = await hass.config_entries.flow.async_configure(
            form_result["flow_id"],
            user_input={CONF_HOST: "sample-host-name"},
        )

    assert configure_result["step_id"] == "manual"
    assert configure_result["errors"]["base"] == "unknown"


async def test_discovery_and_no_devices_discovered(hass: HomeAssistant) -> None:
    """Test initial menu."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.onkyo.config_flow.async_discover", return_value=[]
    ):
        form_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {"next_step_id": "eiscp_discovery"},
        )

        assert form_result["type"] is FlowResultType.ABORT
        assert form_result["reason"] == "no_devices_found"


async def test_discovery_with_exception(hass: HomeAssistant) -> None:
    """Test discovery which throws an unexpected exception."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    with patch(
        "homeassistant.components.onkyo.config_flow.async_discover",
        side_effect=Exception(),
    ):
        form_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {"next_step_id": "eiscp_discovery"},
        )

        assert form_result["type"] is FlowResultType.ABORT
        assert form_result["reason"] == "unknown"


async def test_discovery_with_new_and_existing_found(hass: HomeAssistant) -> None:
    """Test discovery with a new and an existing entry."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    infos = [create_receiver_info(1), create_receiver_info(2)]

    with (
        patch(
            "homeassistant.components.onkyo.config_flow.async_discover",
            return_value=infos,
        ),
        # Fake it like the first entry was already added
        patch.object(OnkyoConfigFlow, "_async_current_ids", return_value=["id1"]),
    ):
        form_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {"next_step_id": "eiscp_discovery"},
        )

        assert form_result["type"] is FlowResultType.FORM

        assert form_result["data_schema"] is not None
        schema = form_result["data_schema"].schema
        container = schema["device"].container
        assert container == {"id2": "type 2 (host 2)"}


async def test_discovery_with_one_selected(hass: HomeAssistant) -> None:
    """Test discovery after a selection."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    infos = [create_receiver_info(42), create_receiver_info(0)]

    with (
        patch(
            "homeassistant.components.onkyo.config_flow.async_discover",
            return_value=infos,
        ),
    ):
        infos = [create_receiver_info(1), create_receiver_info(2)]
        form_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {"next_step_id": "eiscp_discovery"},
        )

        select_result = await hass.config_entries.flow.async_configure(
            form_result["flow_id"],
            user_input={"device": "id42"},
        )

        assert select_result["step_id"] == "configure_receiver"
        assert select_result["description_placeholders"]["name"] == "type 42 (host 42)"


# @pytest.mark.parametrize(
#     ("user_input", "error"),
#     [
#         (
#             {OPTION_SOURCES: ["list"]},
#             "invalid_sources",
#         ),
#     ],
# )
# async def test_options_flow_failures(
#     hass: HomeAssistant,
#     config_entry: MockConfigEntry,
#     user_input: dict[str, Any],
#     error: str,
# ) -> None:
#     """Test load and unload entry."""
#     await setup_integration(hass, config_entry)

#     result = await hass.config_entries.options.async_init(config_entry.entry_id)
#     await hass.async_block_till_done()

#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "init"

#     result = await hass.config_entries.options.async_configure(
#         result["flow_id"],
#         user_input={**user_input},
#     )
#     await hass.async_block_till_done()

#     assert result["type"] is FlowResultType.FORM
#     assert result["step_id"] == "init"
#     assert result["errors"]["base"] == error


# async def test_options_flow(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
#     """Test options flow."""
#     await setup_integration(hass, config_entry)

#     result = await hass.config_entries.options.async_init(config_entry.entry_id)
#     await hass.async_block_till_done()

#     result = await hass.config_entries.options.async_configure(
#         result["flow_id"],
#         user_input={
#             "receiver_max_volume": 200,
#             "maximum_volume": 42,
#             "sources": {},
#         },
#     )
#     await hass.async_block_till_done()

#     assert result["type"] is FlowResultType.CREATE_ENTRY
#     assert result["data"] == {
#         "receiver_max_volume": 200,
#         "maximum_volume": 42,
#         "sources": {},
#     }


# @pytest.mark.parametrize(
#     ("user_input", "error"),
#     [
#         (
#             {CONF_HOST: None},
#             "no_host_defined",
#         ),
#         (
#             {CONF_HOST: "127.0.0.1"},
#             "cannot_connect",
#         ),
#     ],
# )
# @mock.patch("eiscp.eISCP", autospec=eiscp.eISCP)
# async def test_import_fail(
#     mock_receiver: MagicMock,
#     hass: HomeAssistant,
#     user_input: dict[str, Any],
#     error: str,
# ) -> None:
#     """Test import flow."""

#     client = mock_receiver.return_value
#     client.info = None

#     with patch("homeassistant.components.onkyo.config_flow"):
#         result = await hass.config_entries.flow.async_init(
#             DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=user_input
#         )
#         await hass.async_block_till_done()

#     assert result["type"] is FlowResultType.ABORT
#     assert result["reason"] == error


# @mock.patch("eiscp.eISCP", autospec=eiscp.eISCP)
# async def test_import_success(
#     mock_receiver: MagicMock,
#     mock_setup_entry: AsyncMock,
#     hass: HomeAssistant,
# ) -> None:
#     """Test import flow."""

#     client = mock_receiver.return_value
#     client.info = {"identifier": "001122334455", "model_name": "Test model"}

#     with patch("homeassistant.components.onkyo.config_flow"):
#         result = await hass.config_entries.flow.async_init(
#             DOMAIN,
#             context={"source": config_entries.SOURCE_IMPORT},
#             data={
#                 CONF_HOST: "127.0.0.1",
#                 CONF_NAME: "Receiver test name",
#                 OPTION_MAX_VOLUME: 42,
#                 CONF_RECEIVER_MAX_VOLUME: 69,
#                 OPTION_SOURCES: {
#                     "Key_one": "Value-A",
#                     "Key_two": "Value-B",
#                 },
#             },
#         )
#         await hass.async_block_till_done()

#     assert len(mock_setup_entry.mock_calls) == 1
#     assert result["type"] is FlowResultType.CREATE_ENTRY
#     assert result["title"] == "Test model 001122334455"
#     assert result["result"].unique_id == "001122334455"
#     assert result["data"] == {"model": "Test model", "mac": "001122334455"}
#     assert result["options"] == {
#         "maximum_volume": 42,
#         "receiver_max_volume": 69,
#         "sources": {"Key_one": "Value-A", "Key_two": "Value-B"},
#     }
