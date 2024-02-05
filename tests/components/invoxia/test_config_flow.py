"""Test the Invoxia (unofficial) config flow."""
from unittest.mock import patch
import uuid

import gps_tracker
import pytest

from homeassistant.components.invoxia.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_CONF, TEST_CONF_REAUTH

from tests.common import MockConfigEntry


async def test_setup_entry_auth_failed(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test authentication failure during entry setup."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_CONF, unique_id=uuid.uuid4().hex
    )
    mock_config_entry.add_to_hass(hass)
    entry_id = mock_config_entry.entry_id

    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_trackers",
        side_effect=gps_tracker.client.exceptions.UnauthorizedQuery,
    ):
        await hass.config_entries.async_setup(entry_id)
        await hass.async_block_till_done()

    assert "could not authenticate" in caplog.text
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_not_ready(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test not ready status during entry setup."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_CONF, unique_id=uuid.uuid4().hex
    )
    mock_config_entry.add_to_hass(hass)
    entry_id = mock_config_entry.entry_id
    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_trackers",
        side_effect=gps_tracker.client.exceptions.GpsTrackerException,
    ):
        await hass.config_entries.async_setup(entry_id)
        await hass.async_block_till_done()
    assert "not ready yet" in caplog.text
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_trackers",
        return_value=[],
    ) as mock_client, patch(
        "homeassistant.components.invoxia.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-user@domain.ha"
    assert result2["data"] == TEST_CONF
    assert len(mock_client) == 0
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_trackers",
        side_effect=gps_tracker.client.exceptions.UnauthorizedQuery,
    ) as mock_client:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
    assert len(mock_client.mock_calls) == 1

    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_trackers",
        side_effect=gps_tracker.client.exceptions.ForbiddenQuery,
    ) as mock_client:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF,
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}
    assert len(mock_client.mock_calls) == 1

    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_trackers",
        side_effect=Exception,
    ) as mock_client:
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF,
        )

    assert result4["type"] == FlowResultType.FORM
    assert result4["errors"] == {"base": "unknown"}
    assert len(mock_client.mock_calls) == 1


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test the reauthentication configuration flow."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_CONF, unique_id=uuid.uuid4().hex
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"
    assert "flow_id" in result

    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_trackers",
        return_value=[],
    ) as mock_client, patch(
        "homeassistant.components.invoxia.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF_REAUTH,
        )
        await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"
    assert mock_config_entry.data == TEST_CONF_REAUTH

    assert len(mock_client.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_reauth_with_exceptions(hass: HomeAssistant) -> None:
    """Test the reauthentication configuration flow with exception raised."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_CONF, unique_id=uuid.uuid4().hex
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"
    assert "flow_id" in result

    # Authentication error
    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_trackers",
        side_effect=gps_tracker.client.exceptions.UnauthorizedQuery,
    ) as mock_client:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF_REAUTH,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2.get("step_id") == "reauth_confirm"
    assert result2["errors"] == {"base": "invalid_auth"}
    assert len(mock_client.mock_calls) == 1

    # Connection Error
    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_trackers",
        side_effect=gps_tracker.client.exceptions.ForbiddenQuery,
    ) as mock_client:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF_REAUTH,
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3.get("step_id") == "reauth_confirm"
    assert result3["errors"] == {"base": "cannot_connect"}
    assert len(mock_client.mock_calls) == 1

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    # Unknown Error
    with patch(
        "gps_tracker.client.asynchronous.AsyncClient.get_trackers",
        side_effect=Exception,
    ) as mock_client:
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONF_REAUTH,
        )

    assert result4["type"] == FlowResultType.FORM
    assert result4.get("step_id") == "reauth_confirm"
    assert result4["errors"] == {"base": "unknown"}
    assert len(mock_client.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
