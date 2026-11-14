"""Test pi_hole config flow."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value

from homeassistant.components import pi_hole
from homeassistant.components.pi_hole.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_LOCATION,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    CONFIG_DATA_DEFAULTS,
    CONFIG_ENTRY_WITH_API_KEY,
    CONFIG_FLOW_USER,
    FTL_ERROR,
    ZERO_DATA,
    _create_mocked_hole,
    _patch_config_flow_hole,
    _patch_init_hole,
    _patch_setup_hole,
)


@contextmanager
def _patch_valid_hole() -> Generator[None]:
    """Patch a reachable Pi-hole that accepts the API key."""
    mocked_hole = _create_mocked_hole(has_data=False, api_version=6)
    with (
        _patch_init_hole(mocked_hole),
        _patch_config_flow_hole(mocked_hole),
        _patch_setup_hole(),
    ):
        yield


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
        assert result["title"] == DEFAULT_NAME
        assert result["data"] == CONFIG_ENTRY_WITH_API_KEY
        mock_setup.assert_called_once()

        # duplicated server
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
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
        assert result["title"] == DEFAULT_NAME
        assert result["data"] == {**CONFIG_ENTRY_WITH_API_KEY}
        mock_setup.assert_called_once()

        # duplicated server
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_user_invalid(hass: HomeAssistant) -> None:
    """Test user initialized flow with completely invalid server."""
    mocked_hole = _create_mocked_hole(raise_exception=True)
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"api_key": "invalid_auth"}

    with _patch_valid_hole():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_user_invalid_v6(hass: HomeAssistant) -> None:
    """Test user flow with invalid server (V6 API, wrong password)."""
    mocked_hole = _create_mocked_hole(
        has_data=True, api_version=6, incorrect_app_password=True
    )
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"api_key": "invalid_auth"}

    with _patch_valid_hole():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


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
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

    with _patch_valid_hole():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_error_response(hass: HomeAssistant) -> None:
    """Test user initialized flow but dataotherbase errors occur."""
    mocked_hole = _create_mocked_hole(api_version=5, ftl_error=True, has_data=False)
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
        assert mocked_hole.instances[-1].data == FTL_ERROR
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

    with _patch_valid_hole():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfiguring the Pi-hole connection."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_WITH_API_KEY)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    with _patch_valid_hole():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "5.6.7.8",
                CONF_PORT: 8080,
                CONF_LOCATION: "admin",
                CONF_API_KEY: "newkey",
                CONF_SSL: True,
                CONF_VERIFY_SSL: False,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_HOST: "5.6.7.8:8080",
        CONF_LOCATION: "admin",
        CONF_API_KEY: "newkey",
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
    }


@pytest.mark.parametrize(
    ("hole_kwargs", "expected_errors"),
    [
        pytest.param(
            {"api_version": 6, "wrong_host": True},
            {"base": "cannot_connect"},
            id="cannot_connect",
        ),
        pytest.param(
            {"api_version": 6, "has_data": True, "incorrect_app_password": True},
            {CONF_API_KEY: "invalid_auth"},
            id="invalid_auth_v6",
        ),
        pytest.param(
            {"api_version": 5, "ftl_error": True, "has_data": False},
            {"base": "cannot_connect"},
            id="ftl_error_v5",
        ),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    hole_kwargs: dict[str, Any],
    expected_errors: dict[str, str],
) -> None:
    """Test reconfigure errors are shown and the flow can recover."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_WITH_API_KEY)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mocked_hole = _create_mocked_hole(**hole_kwargs)
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == expected_errors

    with _patch_valid_hole():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_FLOW_USER,
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == CONFIG_ENTRY_WITH_API_KEY


async def test_reconfigure_flow_already_configured(hass: HomeAssistant) -> None:
    """Test reconfiguring to the host and location of another entry aborts."""
    MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_WITH_API_KEY).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_ENTRY_WITH_API_KEY, CONF_HOST: "5.6.7.8:80"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_FLOW_USER,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "5.6.7.8:80"


@pytest.mark.parametrize(
    ("use_ssl", "port"),
    [
        pytest.param(False, 80, id="http"),
        pytest.param(True, 443, id="https"),
    ],
)
async def test_reconfigure_flow_host_without_port(
    hass: HomeAssistant, use_ssl: bool, port: int
) -> None:
    """Test the reconfigure form for an entry whose host has no port."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_ENTRY_WITH_API_KEY, CONF_HOST: "pi.hole", CONF_SSL: use_ssl},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, CONF_HOST) == "pi.hole"
    assert get_schema_suggested_value(schema, CONF_PORT) == port
