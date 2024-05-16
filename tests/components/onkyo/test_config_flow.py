"""Test Onkyo config flow."""

from unittest import mock
from unittest.mock import MagicMock, patch

import eiscp

from homeassistant.components.onkyo.const import (
    DOMAIN,
    EISCP_IDENTIFIER,
    EISCP_MODEL_NAME,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_no_manual_entry_and_no_devices_discovered(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""

    # eISCP discovery shows no devices discovered
    with patch.object(eiscp.eISCP, "discover", return_value=[]):
        init_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        # Empty form triggers manual discovery
        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={},
        )

        assert configure_result["type"] is FlowResultType.ABORT
        assert configure_result["reason"] == "no_devices_found"


async def test_manual_entry_invalid_ip(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    configure_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        user_input={CONF_HOST: "xxx"},
    )

    assert configure_result["type"] is FlowResultType.FORM
    assert configure_result["step_id"] == "user"
    assert configure_result["errors"]["base"] == "no_ip"


@mock.patch("eiscp.eISCP", autospec=eiscp.eISCP)
async def test_manual_entry_valid_ip_fails_connection(
    mock_receiver: MagicMock, hass: HomeAssistant
) -> None:
    """Test the full user configuration flow."""

    client = mock_receiver.return_value
    client.host = "fake_host"
    client.port = 1337
    client.info = None

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    configure_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        user_input={CONF_HOST: "127.0.0.1"},
    )

    client.disconnect.assert_called()
    assert configure_result["type"] is FlowResultType.FORM
    assert configure_result["step_id"] == "user"
    assert configure_result["errors"]["base"] == "cannot_connect"


@mock.patch("eiscp.eISCP", autospec=eiscp.eISCP)
async def test_manual_entry_valid_ip(
    mock_receiver: MagicMock, hass: HomeAssistant
) -> None:
    """Test the full user configuration flow."""

    client = mock_receiver.return_value
    client.host = "fake_host"
    client.port = 1337
    client.info = {EISCP_IDENTIFIER: "001122334455", EISCP_MODEL_NAME: "fake_model"}

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    configure_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        user_input={CONF_HOST: "127.0.0.1"},
    )

    client.disconnect.assert_called()
    assert configure_result["type"] is FlowResultType.CREATE_ENTRY
    assert configure_result["title"] == "fake_model 001122334455"
    assert configure_result["data"][CONF_HOST] == "fake_host"
    assert configure_result["data"][CONF_PORT] == 1337
    assert configure_result["data"][CONF_NAME] == "fake_model 001122334455"
    assert configure_result["data"][CONF_MODEL] == "fake_model"
    assert configure_result["data"][CONF_MAC] == "001122334455"


async def test_select_manually_discovered_device(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""

    info = {EISCP_IDENTIFIER: "004815162342 ", EISCP_MODEL_NAME: "fake_model"}
    receiver = MagicMock()
    receiver.host = "fake_host"
    receiver.port = 12345

    # Mock the dict
    receiver.info.__getitem__.side_effect = info.__getitem__

    # eISCP discovery shows 1 devices discovered
    with patch.object(eiscp.eISCP, "discover", return_value=[receiver]):
        init_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        # Empty form triggers manual discovery
        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={},
        )

        assert configure_result["type"] is FlowResultType.FORM

        # Empty form triggers manual discovery
        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            user_input={CONF_DEVICE: "004815162342 "},
        )

    assert configure_result["type"] is FlowResultType.CREATE_ENTRY
    assert configure_result["title"] == "fake_model 004815162342 "
    assert configure_result["data"][CONF_HOST] == "fake_host"
    assert configure_result["data"][CONF_PORT] == 12345
    assert configure_result["data"][CONF_NAME] == "fake_model 004815162342 "
    assert configure_result["data"][CONF_MODEL] == "fake_model"
    assert configure_result["data"][CONF_MAC] == "004815162342 "
