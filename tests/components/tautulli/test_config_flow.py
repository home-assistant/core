"""Test Tautulli config flow."""

from unittest.mock import AsyncMock, patch

from pytautulli import exceptions

from homeassistant.components.tautulli.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_SOURCE, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import CONF_DATA, NAME, patch_config_flow_tautulli, setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initiated flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch_config_flow_tautulli(AsyncMock()):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == NAME
    assert result2["data"] == CONF_DATA


async def test_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    with patch_config_flow_tautulli(AsyncMock()) as tautullimock:
        tautullimock.side_effect = exceptions.PyTautulliConnectionException
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=CONF_DATA
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"

    with patch_config_flow_tautulli(AsyncMock()):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == NAME
    assert result2["data"] == CONF_DATA


async def test_flow_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test user initialized flow with invalid authentication."""
    with patch_config_flow_tautulli(AsyncMock()) as tautullimock:
        tautullimock.side_effect = exceptions.PyTautulliAuthenticationException
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_auth"

    with patch_config_flow_tautulli(AsyncMock()):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == NAME
    assert result2["data"] == CONF_DATA


async def test_flow_user_unknown_error(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    with patch_config_flow_tautulli(AsyncMock()) as tautullimock:
        tautullimock.side_effect = exceptions.PyTautulliException
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "unknown"

    with patch_config_flow_tautulli(AsyncMock()):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == NAME
    assert result2["data"] == CONF_DATA


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user step already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    with patch_config_flow_tautulli(AsyncMock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONF_DATA,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_user_multiple_entries_allowed(hass: HomeAssistant) -> None:
    """Test user step can configure multiple entries."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    user_input = {
        CONF_URL: "http://1.2.3.5:8181/test",
        CONF_API_KEY: "efgh",
        CONF_VERIFY_SSL: True,
    }
    with patch_config_flow_tautulli(AsyncMock()):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == NAME
    assert result2["data"] == user_input


async def test_flow_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth flow."""
    with patch("homeassistant.components.tautulli.PLATFORMS", []):
        entry = await setup_integration(hass, aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            CONF_SOURCE: SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=CONF_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    new_conf = {CONF_API_KEY: "efgh"}
    CONF_DATA[CONF_API_KEY] = "efgh"
    with (
        patch_config_flow_tautulli(AsyncMock()),
        patch("homeassistant.components.tautulli.async_setup_entry") as mock_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=new_conf,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == CONF_DATA
    assert len(mock_entry.mock_calls) == 1


async def test_flow_reauth_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth flow with invalid authentication."""
    with patch("homeassistant.components.tautulli.PLATFORMS", []):
        entry = await setup_integration(hass, aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )
    with patch_config_flow_tautulli(AsyncMock()) as tautullimock:
        tautullimock.side_effect = exceptions.PyTautulliAuthenticationException
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "efgh"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "invalid_auth"

    with patch_config_flow_tautulli(AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "efgh"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
