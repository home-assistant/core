"""Tests for the luci config flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.luci.config_flow import InvalidAuth
from homeassistant.components.luci.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

REAUTH_INPUT = {
    CONF_USERNAME: "root",
    CONF_PASSWORD: "new-password",
}

USER_INPUT = {
    CONF_HOST: "192.168.1.1",
    CONF_USERNAME: "root",
    CONF_PASSWORD: "password",
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
}


@pytest.mark.parametrize(
    ("side_effect", "errors", "existing_entry"),
    [
        (None, {}, False),
        (ConnectionError, {"base": "cannot_connect"}, False),
        (InvalidAuth, {"base": "invalid_auth"}, False),
        (None, {}, True),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception] | None,
    errors: dict[str, str],
    existing_entry: bool,
) -> None:
    """Test user flow outcomes including errors and recovery."""
    if existing_entry:
        mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    if errors:
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == errors
        with patch("homeassistant.components.luci.config_flow._try_connect"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=USER_INPUT
            )
        assert result["type"] is FlowResultType.CREATE_ENTRY
    elif existing_entry:
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
    else:
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "192.168.1.1"
        assert result["data"] == USER_INPUT


@pytest.mark.parametrize(
    ("side_effect", "result_type", "reason", "existing_entry"),
    [
        (None, FlowResultType.CREATE_ENTRY, None, False),
        (ConnectionError, FlowResultType.ABORT, "cannot_connect", False),
        (InvalidAuth, FlowResultType.ABORT, "invalid_auth", False),
        (None, FlowResultType.ABORT, "already_configured", True),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception] | None,
    result_type: FlowResultType,
    reason: str | None,
    existing_entry: bool,
) -> None:
    """Test import flow outcomes."""
    if existing_entry:
        mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
        )

    assert result["type"] is result_type
    if result_type is FlowResultType.CREATE_ENTRY:
        assert result["title"] == "192.168.1.1"
        assert result["data"] == USER_INPUT
    else:
        assert result["reason"] == reason


@pytest.mark.parametrize(
    ("side_effect", "errors"),
    [
        (None, {}),
        (ConnectionError, {"base": "cannot_connect"}),
        (InvalidAuth, {"base": "invalid_auth"}),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception] | None,
    errors: dict[str, str],
) -> None:
    """Test reauth flow outcomes including errors and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=REAUTH_INPUT
        )

    if errors:
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == errors
        with patch("homeassistant.components.luci.config_flow._try_connect"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=REAUTH_INPUT
            )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
