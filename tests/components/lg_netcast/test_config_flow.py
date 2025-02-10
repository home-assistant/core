"""Define tests for the LG Netcast config flow."""

from datetime import timedelta
from unittest.mock import DEFAULT, patch

from homeassistant import data_entry_flow
from homeassistant.components.lg_netcast.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    CONF_ID,
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant

from . import (
    FAKE_PIN,
    FRIENDLY_NAME,
    IP_ADDRESS,
    MODEL_NAME,
    UNIQUE_ID,
    _patch_lg_netcast,
)


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_invalid_host(hass: HomeAssistant) -> None:
    """Test that errors are shown when the host is invalid."""
    with _patch_lg_netcast():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "invalid/host"}
        )

        assert result["errors"] == {CONF_HOST: "invalid_host"}


async def test_manual_host(hass: HomeAssistant) -> None:
    """Test manual host configuration."""
    with _patch_lg_netcast():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: IP_ADDRESS}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "authorize"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        assert result2["step_id"] == "authorize"
        assert result2["errors"] is not None
        assert result2["errors"][CONF_ACCESS_TOKEN] == "invalid_access_token"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: FAKE_PIN}
        )

        assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result3["title"] == FRIENDLY_NAME
        assert result3["data"] == {
            CONF_HOST: IP_ADDRESS,
            CONF_ACCESS_TOKEN: FAKE_PIN,
            CONF_NAME: FRIENDLY_NAME,
            CONF_MODEL: MODEL_NAME,
            CONF_ID: UNIQUE_ID,
        }


async def test_manual_host_no_connection_during_authorize(hass: HomeAssistant) -> None:
    """Test manual host configuration."""
    with _patch_lg_netcast(fail_connection=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: IP_ADDRESS}
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


async def test_manual_host_invalid_details_during_authorize(
    hass: HomeAssistant,
) -> None:
    """Test manual host configuration."""
    with _patch_lg_netcast(invalid_details=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: IP_ADDRESS}
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


async def test_manual_host_unsuccessful_details_response(hass: HomeAssistant) -> None:
    """Test manual host configuration."""
    with _patch_lg_netcast(always_404=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: IP_ADDRESS}
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


async def test_manual_host_no_unique_id_response(hass: HomeAssistant) -> None:
    """Test manual host configuration."""
    with _patch_lg_netcast(no_unique_id=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: IP_ADDRESS}
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "invalid_host"


async def test_invalid_session_id(hass: HomeAssistant) -> None:
    """Test Invalid Session ID."""
    with _patch_lg_netcast(session_error=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: IP_ADDRESS}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "authorize"
        assert not result["errors"]

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: FAKE_PIN}
        )

        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        assert result2["step_id"] == "authorize"
        assert result2["errors"] is not None
        assert result2["errors"]["base"] == "cannot_connect"


async def test_display_access_token_aborted(hass: HomeAssistant) -> None:
    """Test Access token display is cancelled."""

    def _async_track_time_interval(
        hass: HomeAssistant,
        action,
        interval: timedelta,
        *,
        name=None,
        cancel_on_shutdown=None,
    ):
        hass.async_create_task(action())
        return DEFAULT

    with (
        _patch_lg_netcast(session_error=True),
        patch(
            "homeassistant.components.lg_netcast.config_flow.async_track_time_interval"
        ) as mock_interval,
    ):
        mock_interval.side_effect = _async_track_time_interval
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: IP_ADDRESS}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "authorize"
        assert not result["errors"]

        assert mock_interval.called

        hass.config_entries.flow.async_abort(result["flow_id"])
        assert mock_interval.return_value.called
