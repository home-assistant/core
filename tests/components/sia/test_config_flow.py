"""Test the sia config flow."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.sia.config_flow import ACCOUNT_SCHEMA, HUB_SCHEMA
from homeassistant.components.sia.const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ADDITIONAL_ACCOUNTS,
    CONF_ENCRYPTION_KEY,
    CONF_IGNORE_TIMESTAMPS,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DOMAIN,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PORT, CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

BASIS_CONFIG_ENTRY_ID = 1
BASIC_CONFIG = {
    CONF_PORT: 7777,
    CONF_PROTOCOL: "TCP",
    CONF_ACCOUNT: "ABCDEF",
    CONF_ENCRYPTION_KEY: "AAAAAAAAAAAAAAAA",
    CONF_PING_INTERVAL: 10,
    CONF_ZONES: 1,
    CONF_ADDITIONAL_ACCOUNTS: False,
}

BASIC_OPTIONS = {CONF_IGNORE_TIMESTAMPS: False, CONF_ZONES: 2}

BASE_OUT = {
    "data": {
        CONF_PORT: 7777,
        CONF_PROTOCOL: "TCP",
        CONF_ACCOUNTS: [
            {
                CONF_ACCOUNT: "ABCDEF",
                CONF_ENCRYPTION_KEY: "AAAAAAAAAAAAAAAA",
                CONF_PING_INTERVAL: 10,
            },
        ],
    },
    "options": {
        CONF_ACCOUNTS: {"ABCDEF": {CONF_IGNORE_TIMESTAMPS: False, CONF_ZONES: 1}}
    },
}

ADDITIONAL_CONFIG_ENTRY_ID = 2
BASIC_CONFIG_ADDITIONAL = {
    CONF_PORT: 7777,
    CONF_PROTOCOL: "TCP",
    CONF_ACCOUNT: "ABCDEF",
    CONF_ENCRYPTION_KEY: "AAAAAAAAAAAAAAAA",
    CONF_PING_INTERVAL: 10,
    CONF_ZONES: 1,
    CONF_ADDITIONAL_ACCOUNTS: True,
}

ADDITIONAL_ACCOUNT = {
    CONF_ACCOUNT: "ACC2",
    CONF_ENCRYPTION_KEY: "AAAAAAAAAAAAAAAA",
    CONF_PING_INTERVAL: 2,
    CONF_ZONES: 2,
    CONF_ADDITIONAL_ACCOUNTS: False,
}
ADDITIONAL_OUT = {
    "data": {
        CONF_PORT: 7777,
        CONF_PROTOCOL: "TCP",
        CONF_ACCOUNTS: [
            {
                CONF_ACCOUNT: "ABCDEF",
                CONF_ENCRYPTION_KEY: "AAAAAAAAAAAAAAAA",
                CONF_PING_INTERVAL: 10,
            },
            {
                CONF_ACCOUNT: "ACC2",
                CONF_ENCRYPTION_KEY: "AAAAAAAAAAAAAAAA",
                CONF_PING_INTERVAL: 2,
            },
        ],
    },
    "options": {
        CONF_ACCOUNTS: {
            "ABCDEF": {CONF_IGNORE_TIMESTAMPS: False, CONF_ZONES: 1},
            "ACC2": {CONF_IGNORE_TIMESTAMPS: False, CONF_ZONES: 2},
        }
    },
}

ADDITIONAL_OPTIONS = {
    CONF_ACCOUNTS: {
        "ABCDEF": {CONF_IGNORE_TIMESTAMPS: False, CONF_ZONES: 2},
        "ACC2": {CONF_IGNORE_TIMESTAMPS: False, CONF_ZONES: 2},
    }
}


@pytest.fixture
async def flow_at_user_step(hass: HomeAssistant) -> ConfigFlowResult:
    """Return a initialized flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )


@pytest.fixture
async def entry_with_basic_config(
    hass: HomeAssistant, flow_at_user_step: ConfigFlowResult
) -> ConfigFlowResult:
    """Return a entry with a basic config."""
    with patch("homeassistant.components.sia.async_setup_entry", return_value=True):
        return await hass.config_entries.flow.async_configure(
            flow_at_user_step["flow_id"], BASIC_CONFIG
        )


@pytest.fixture
async def flow_at_add_account_step(
    hass: HomeAssistant, flow_at_user_step: ConfigFlowResult
) -> ConfigFlowResult:
    """Return a initialized flow at the additional account step."""
    return await hass.config_entries.flow.async_configure(
        flow_at_user_step["flow_id"], BASIC_CONFIG_ADDITIONAL
    )


@pytest.fixture
async def entry_with_additional_account_config(
    hass: HomeAssistant, flow_at_add_account_step: ConfigFlowResult
) -> ConfigFlowResult:
    """Return a entry with a two account config."""
    with patch("homeassistant.components.sia.async_setup_entry", return_value=True):
        return await hass.config_entries.flow.async_configure(
            flow_at_add_account_step["flow_id"], ADDITIONAL_ACCOUNT
        )


async def setup_sia(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Add mock config to HASS."""
    assert await async_setup_component(hass, DOMAIN, {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_form_start_user(flow_at_user_step: ConfigFlowResult) -> None:
    """Start the form and check if you get the right id and schema for the user step."""
    assert flow_at_user_step["step_id"] == "user"
    assert flow_at_user_step["errors"] is None
    assert flow_at_user_step["data_schema"] == HUB_SCHEMA


async def test_form_start_account(flow_at_add_account_step: ConfigFlowResult) -> None:
    """Start the form and check if you get the right id and schema for the additional account step."""
    assert flow_at_add_account_step["step_id"] == "add_account"
    assert flow_at_add_account_step["errors"] is None
    assert flow_at_add_account_step["data_schema"] == ACCOUNT_SCHEMA


async def test_create(entry_with_basic_config: ConfigFlowResult) -> None:
    """Test we create a entry through the form."""
    assert entry_with_basic_config["type"] is FlowResultType.CREATE_ENTRY
    assert (
        entry_with_basic_config["title"]
        == f"SIA Alarm on port {BASIC_CONFIG[CONF_PORT]}"
    )
    assert entry_with_basic_config["data"] == BASE_OUT["data"]
    assert entry_with_basic_config["options"] == BASE_OUT["options"]


async def test_create_additional_account(
    entry_with_additional_account_config: ConfigFlowResult,
) -> None:
    """Test we create a config with two accounts."""
    assert entry_with_additional_account_config["type"] is FlowResultType.CREATE_ENTRY
    assert (
        entry_with_additional_account_config["title"]
        == f"SIA Alarm on port {BASIC_CONFIG[CONF_PORT]}"
    )

    assert entry_with_additional_account_config["data"] == ADDITIONAL_OUT["data"]
    assert entry_with_additional_account_config["options"] == ADDITIONAL_OUT["options"]


async def test_abort_form(hass: HomeAssistant) -> None:
    """Test aborting a config that already exists."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=BASE_OUT["data"],
        options=BASE_OUT["options"],
        title="SIA Alarm on port 7777",
        entry_id=BASIS_CONFIG_ENTRY_ID,
        version=1,
    )
    await setup_sia(hass, config_entry)
    start_another_flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    get_abort = await hass.config_entries.flow.async_configure(
        start_another_flow["flow_id"], BASIC_CONFIG
    )
    assert get_abort["type"] is FlowResultType.ABORT
    assert get_abort["reason"] == "already_configured"


@pytest.fixture(autouse=True)
def mock_sia() -> Generator[None]:
    """Mock SIAClient."""
    with patch("homeassistant.components.sia.hub.SIAClient", autospec=True):
        yield


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("encryption_key", "AAAAAAAAAAAAAZZZ", "invalid_key_format"),
        ("encryption_key", "AAAAAAAAAAAAA", "invalid_key_length"),
        ("account", "ZZZ", "invalid_account_format"),
        ("account", "A", "invalid_account_length"),
        ("ping_interval", 1500, "invalid_ping"),
        ("zones", 0, "invalid_zones"),
    ],
)
async def test_validation_errors_user(
    hass: HomeAssistant,
    flow_at_user_step,
    field,
    value,
    error,
) -> None:
    """Test we handle the different invalid inputs, in the user flow."""
    config = BASIC_CONFIG.copy()
    flow_id = flow_at_user_step["flow_id"]
    config[field] = value
    result_err = await hass.config_entries.flow.async_configure(flow_id, config)
    assert result_err["type"] is FlowResultType.FORM
    assert result_err["errors"] == {"base": error}


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("encryption_key", "AAAAAAAAAAAAAZZZ", "invalid_key_format"),
        ("encryption_key", "AAAAAAAAAAAAA", "invalid_key_length"),
        ("account", "ZZZ", "invalid_account_format"),
        ("account", "A", "invalid_account_length"),
        ("ping_interval", 1500, "invalid_ping"),
        ("zones", 0, "invalid_zones"),
    ],
)
async def test_validation_errors_account(
    hass: HomeAssistant,
    flow_at_user_step,
    field,
    value,
    error,
) -> None:
    """Test we handle the different invalid inputs, in the add_account flow."""
    flow_at_add_account_step = await hass.config_entries.flow.async_configure(
        flow_at_user_step["flow_id"], BASIC_CONFIG_ADDITIONAL
    )
    config = ADDITIONAL_ACCOUNT.copy()
    flow_id = flow_at_add_account_step["flow_id"]
    config[field] = value
    result_err = await hass.config_entries.flow.async_configure(flow_id, config)
    assert result_err["type"] is FlowResultType.FORM
    assert result_err["errors"] == {"base": error}


async def test_unknown_user(hass: HomeAssistant, flow_at_user_step) -> None:
    """Test unknown exceptions."""
    flow_id = flow_at_user_step["flow_id"]
    with patch(
        "pysiaalarm.SIAAccount.validate_account",
        side_effect=Exception,
    ):
        config = BASIC_CONFIG
        result_err = await hass.config_entries.flow.async_configure(flow_id, config)
        assert result_err
        assert result_err["step_id"] == "user"
        assert result_err["errors"] == {"base": "unknown"}
        assert result_err["data_schema"] == HUB_SCHEMA


async def test_unknown_account(hass: HomeAssistant, flow_at_user_step) -> None:
    """Test unknown exceptions."""
    flow_at_add_account_step = await hass.config_entries.flow.async_configure(
        flow_at_user_step["flow_id"], BASIC_CONFIG_ADDITIONAL
    )
    flow_id = flow_at_add_account_step["flow_id"]
    with patch(
        "pysiaalarm.SIAAccount.validate_account",
        side_effect=Exception,
    ):
        config = ADDITIONAL_ACCOUNT
        result_err = await hass.config_entries.flow.async_configure(flow_id, config)
        assert result_err
        assert result_err["step_id"] == "add_account"
        assert result_err["errors"] == {"base": "unknown"}
        assert result_err["data_schema"] == ACCOUNT_SCHEMA


async def test_options_basic(hass: HomeAssistant) -> None:
    """Test options flow for single account."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=BASE_OUT["data"],
        options=BASE_OUT["options"],
        title="SIA Alarm on port 7777",
        entry_id=BASIS_CONFIG_ENTRY_ID,
        version=1,
    )
    await setup_sia(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"
    assert result["last_step"]

    updated = await hass.config_entries.options.async_configure(
        result["flow_id"], BASIC_OPTIONS
    )
    await hass.async_block_till_done()
    assert updated["type"] is FlowResultType.CREATE_ENTRY
    assert updated["data"] == {
        CONF_ACCOUNTS: {BASIC_CONFIG[CONF_ACCOUNT]: BASIC_OPTIONS}
    }


async def test_options_additional(hass: HomeAssistant) -> None:
    """Test options flow for single account."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=ADDITIONAL_OUT["data"],
        options=ADDITIONAL_OUT["options"],
        title="SIA Alarm on port 7777",
        entry_id=ADDITIONAL_CONFIG_ENTRY_ID,
        version=1,
    )
    await setup_sia(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"
    assert not result["last_step"]

    updated = await hass.config_entries.options.async_configure(
        result["flow_id"], BASIC_OPTIONS
    )
    assert updated["type"] is FlowResultType.FORM
    assert updated["step_id"] == "options"
    assert updated["last_step"]
