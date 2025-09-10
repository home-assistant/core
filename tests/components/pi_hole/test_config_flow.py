"""Test pi_hole config flow."""

from homeassistant.components import pi_hole
from homeassistant.components.pi_hole.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    CONFIG_DATA_DEFAULTS,
    CONFIG_ENTRY_WITH_API_KEY,
    CONFIG_FLOW_USER,
    FTL_ERROR,
    NAME,
    ZERO_DATA,
    _create_mocked_hole,
    _patch_config_flow_hole,
    _patch_init_hole,
    _patch_setup_hole,
)

from tests.common import MockConfigEntry


async def test_flow_user_with_api_key_v6(hass: HomeAssistant) -> None:
    """Test user initialized flow with api key needed."""
    mocked_hole = _create_mocked_hole(has_data=False, api_version=6)
    with (
        _patch_init_hole(mocked_hole),
        _patch_config_flow_hole(mocked_hole),
        _patch_setup_hole() as mock_setup,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**CONFIG_FLOW_USER, CONF_API_KEY: "invalid_password"},
        )
        # we have had no response from the server yet, so we expect an error
        assert result["errors"] == {CONF_API_KEY: "invalid_auth"}

        # now we have a valid passiword
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )

        # form should be complete with a valid config entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == CONFIG_ENTRY_WITH_API_KEY
        mock_setup.assert_called_once()

        # duplicated server
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_FLOW_USER,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_user_with_api_key_v5(hass: HomeAssistant) -> None:
    """Test user initialized flow with api key needed."""
    mocked_hole = _create_mocked_hole(api_version=5)
    with (
        _patch_init_hole(mocked_hole),
        _patch_config_flow_hole(mocked_hole),
        _patch_setup_hole() as mock_setup,
    ):
        # start the flow as a user initiated flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        # configure the flow with an invalid api key
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**CONFIG_FLOW_USER, CONF_API_KEY: "wrong_token"},
        )

        # confirm an invalid authentication error
        assert result["errors"] == {CONF_API_KEY: "invalid_auth"}

        # configure the flow with a valid api key
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )

        # in API V5 we get data to confirm authentication
        assert mocked_hole.instances[-1].data == ZERO_DATA

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == NAME
        assert result["data"] == {**CONFIG_ENTRY_WITH_API_KEY}
        mock_setup.assert_called_once()

        # duplicated server
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_FLOW_USER,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_user_invalid(hass: HomeAssistant) -> None:
    """Test user initialized flow with completely invalid server."""
    mocked_hole = _create_mocked_hole(raise_exception=True)
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG_FLOW_USER
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"api_key": "invalid_auth"}


async def test_flow_user_invalid_v6(hass: HomeAssistant) -> None:
    """Test user initialized flow with invalid server - typically a V6 API and a incorrect app password."""
    mocked_hole = _create_mocked_hole(
        has_data=True, api_version=6, incorrect_app_password=True
    )
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG_FLOW_USER
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"api_key": "invalid_auth"}


async def test_flow_reauth(hass: HomeAssistant) -> None:
    """Test reauth flow."""
    mocked_hole = _create_mocked_hole(has_data=False, api_version=5)
    entry = MockConfigEntry(
        domain=pi_hole.DOMAIN,
        data={**CONFIG_DATA_DEFAULTS, CONF_API_KEY: "oldkey"},
    )
    entry.add_to_hass(hass)
    with _patch_init_hole(mocked_hole), _patch_config_flow_hole(mocked_hole):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        flows = hass.config_entries.flow.async_progress()

        assert len(flows) == 1
        assert flows[0]["step_id"] == "reauth_confirm"
        assert flows[0]["context"]["entry_id"] == entry.entry_id
        mocked_hole.instances[-1].api_token = "newkey"
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"],
            user_input={CONF_API_KEY: "newkey"},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data[CONF_API_KEY] == "newkey"


async def test_flow_user_invalid_host(hass: HomeAssistant) -> None:
    """Test user initialized flow with invalid server host address."""
    mocked_hole = _create_mocked_hole(api_version=6, wrong_host=True)
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG_FLOW_USER
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_error_response(hass: HomeAssistant) -> None:
    """Test user initialized flow but dataotherbase errors occur."""
    mocked_hole = _create_mocked_hole(api_version=5, ftl_error=True, has_data=False)
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG_FLOW_USER
        )
        assert mocked_hole.instances[-1].data == FTL_ERROR
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}
