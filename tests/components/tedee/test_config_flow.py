"""Test the Tedee config flow."""
from unittest.mock import MagicMock

from pytedee_async import TedeeAuthException, TedeeLocalAuthException

from homeassistant import config_entries
from homeassistant.components.tedee.const import (
    CONF_HOME_ASSISTANT_ACCESS_TOKEN,
    CONF_LOCAL_ACCESS_TOKEN,
    CONF_UNLOCK_PULLS_LATCH,
    CONF_USE_CLOUD,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

FLOW_UNIQUE_ID = "112233445566778899"
ACCESS_TOKEN = "api_token"
LOCAL_ACCESS_TOKEN = "api_token"


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_flow_abort(hass: HomeAssistant, mock_tedee: MagicMock) -> None:
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.62",
            CONF_LOCAL_ACCESS_TOKEN: "token",
            CONF_USE_CLOUD: False,
        },
    )

    assert len(mock_tedee.get_locks.mock_calls) == 1

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: "192.168.1.62",
        CONF_LOCAL_ACCESS_TOKEN: "token",
        CONF_USE_CLOUD: False,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_flow(hass: HomeAssistant, mock_tedee: MagicMock) -> None:
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.62",
            CONF_LOCAL_ACCESS_TOKEN: "token",
            CONF_USE_CLOUD: True,
        },
    )

    assert len(mock_tedee.get_locks.mock_calls) == 1

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "configure_cloud"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {CONF_ACCESS_TOKEN: "token"}
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        CONF_HOST: "192.168.1.62",
        CONF_LOCAL_ACCESS_TOKEN: "token",
        CONF_USE_CLOUD: True,
        CONF_ACCESS_TOKEN: "token",
    }


async def config_flow_errors(hass: HomeAssistant, mock_tedee: MagicMock) -> None:
    """Test the config flow errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_LOCAL_ACCESS_TOKEN: "token"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "invalid_host"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.42"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_LOCAL_ACCESS_TOKEN: "invalid_api_key"}

    mock_tedee.side_effect = TedeeLocalAuthException("Invalid token")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.42",
            CONF_LOCAL_ACCESS_TOKEN: "wrong_token",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_LOCAL_ACCESS_TOKEN: "invalid_api_key"}
    assert len(mock_tedee.get_locks.mock_calls) == 1

    mock_tedee.get_locks.side_effect = Exception()
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.x",
            CONF_LOCAL_ACCESS_TOKEN: "token",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_HOST: "invalid_host"}
    assert len(mock_tedee.get_locks.mock_calls) == 2

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_CLOUD: True}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "configure_cloud"

    mock_tedee.get_locks.side_effect = TedeeAuthException("Invalid token")

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_ACCESS_TOKEN: "invalid_token",
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {CONF_ACCESS_TOKEN: "invalid_api_key"}
    assert len(mock_tedee.get_locks.mock_calls) == 3

    mock_tedee.get_locks.side_effect = Exception()

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_ACCESS_TOKEN: "token",
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}
    assert len(mock_tedee.get_locks.mock_calls) == 4


async def test_show_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the reauth form shows."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tedee: MagicMock
) -> None:
    """Test that the reauth flow works."""

    mock_config_entry.add_to_hass(hass)

    # Trigger reauth
    reauth_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        reauth_result["flow_id"],
        {
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
    )
    assert result["type"] == FlowResultType.ABORT
    await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_errors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tedee: MagicMock
) -> None:
    """Test that the reauth flow errors."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
    )

    mock_tedee.get_locks.side_effect = TedeeLocalAuthException("Invalid token")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ACCESS_TOKEN: "wrong_token",
            CONF_LOCAL_ACCESS_TOKEN: "wrong_token",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {
        CONF_ACCESS_TOKEN: "invalid_api_key",
        CONF_LOCAL_ACCESS_TOKEN: "invalid_api_key",
    }
    assert len(mock_tedee.get_locks.mock_calls) == 1

    mock_tedee.get_locks.side_effect = Exception()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ACCESS_TOKEN: "token",
            CONF_LOCAL_ACCESS_TOKEN: "token",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    assert len(mock_tedee.get_locks.mock_calls) == 2


async def test_options_flow(hass: HomeAssistant, mock_tedee: MagicMock) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},  # assume no data for tests, as most is optional
        unique_id=FLOW_UNIQUE_ID,
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_LOCAL_ACCESS_TOKEN: "token"},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_HOST: "invalid_host"}

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.42"},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_LOCAL_ACCESS_TOKEN: "invalid_api_key"}

    mock_tedee.get_locks.side_effect = TedeeLocalAuthException("Invalid token")

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.42",
            CONF_LOCAL_ACCESS_TOKEN: "wrong_token",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_LOCAL_ACCESS_TOKEN: "invalid_api_key"}
    assert len(mock_tedee.get_locks.mock_calls) == 1

    mock_tedee.get_locks.side_effect = Exception()

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.x",
            CONF_LOCAL_ACCESS_TOKEN: "wrong_token",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_HOST: "invalid_host"}
    assert len(mock_tedee.get_locks.mock_calls) == 2

    mock_tedee.get_locks.side_effect = TedeeAuthException("invalid auth")
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACCESS_TOKEN: "wrong_token"},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_ACCESS_TOKEN: "invalid_api_key"}
    assert len(mock_tedee.get_locks.mock_calls) == 3

    mock_tedee.get_locks.side_effect = Exception()
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACCESS_TOKEN: "token"},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    assert len(mock_tedee.get_locks.mock_calls) == 4

    mock_tedee.get_locks.side_effect = None

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.42",
            CONF_LOCAL_ACCESS_TOKEN: "token1",
            CONF_ACCESS_TOKEN: "token2",
            CONF_HOME_ASSISTANT_ACCESS_TOKEN: "token3",
            CONF_UNLOCK_PULLS_LATCH: False,
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: "192.168.1.42",
        CONF_LOCAL_ACCESS_TOKEN: "token1",
        CONF_ACCESS_TOKEN: "token2",
        CONF_HOME_ASSISTANT_ACCESS_TOKEN: "token3",
        CONF_UNLOCK_PULLS_LATCH: False,
    }
    assert len(mock_tedee.get_locks.mock_calls) == 6
