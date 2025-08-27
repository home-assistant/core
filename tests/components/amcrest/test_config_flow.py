"""Test the Amcrest config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.amcrest.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry():
    """Mock async setup entry."""
    with patch(
        "homeassistant.components.amcrest.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


async def test_form(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.return_value = None  # Connection successful

        with patch(
            "homeassistant.components.amcrest.config_flow._get_unique_id"
        ) as mock_unique:
            mock_unique.return_value = "ABCD1234567890"

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_NAME: "Living Room",
                    CONF_HOST: "192.168.1.100",
                    CONF_PORT: 80,
                    CONF_USERNAME: "admin",
                    CONF_PASSWORD: "password123",
                },
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Living Room"
    assert result2["data"] == {
        CONF_NAME: "Living Room",
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 80,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password123",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.side_effect = InvalidAuth()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Living Room",
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 80,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.side_effect = CannotConnect()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Living Room",
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 80,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password123",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.side_effect = Exception("Unexpected error")

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Living Room",
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 80,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password123",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reconfigure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"  # Should delegate to user step

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.return_value = None  # Connection successful

        with patch(
            "homeassistant.components.amcrest.config_flow._get_unique_id"
        ) as mock_unique:
            mock_unique.return_value = "ABCD1234567890"  # Same as config entry

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "192.168.1.101",
                    CONF_PORT: 8080,
                    CONF_USERNAME: "admin",
                    CONF_PASSWORD: "new_password",
                },
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.101"
    assert mock_config_entry.data[CONF_PORT] == 8080
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


async def test_unique_id_already_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if the camera is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.return_value = None  # Connection successful

        with patch(
            "homeassistant.components.amcrest.config_flow._get_unique_id"
        ) as mock_unique:
            mock_unique.return_value = "ABCD1234567890"  # Same as mock_config_entry

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_NAME: "Living Room 2",
                    CONF_HOST: "192.168.1.101",
                    CONF_PORT: 80,
                    CONF_USERNAME: "admin",
                    CONF_PASSWORD: "password123",
                },
            )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
