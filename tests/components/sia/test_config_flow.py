"""Test the sia config flow."""
import logging
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
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
from homeassistant.const import CONF_PORT, CONF_PROTOCOL
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


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

BASIC_CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    data=BASE_OUT["data"],
    options=BASE_OUT["options"],
    title="SIA Alarm on port 7777",
    entry_id=BASIS_CONFIG_ENTRY_ID,
    version=1,
)
ADDITIONAL_CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    data=ADDITIONAL_OUT["data"],
    options=ADDITIONAL_OUT["options"],
    title="SIA Alarm on port 7777",
    entry_id=ADDITIONAL_CONFIG_ENTRY_ID,
    version=1,
)


@pytest.fixture(params=[False, True], ids=["user", "add_account"])
def additional(request) -> bool:
    """Return True or False for the additional or base test."""
    return request.param


@pytest.fixture
async def flow_at_user_step(hass):
    """Return a initialized flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )


@pytest.fixture
async def entry_with_basic_config(hass, flow_at_user_step):
    """Return a entry with a basic config."""
    with patch("pysiaalarm.aio.SIAClient.start", return_value=True):
        return await hass.config_entries.flow.async_configure(
            flow_at_user_step["flow_id"], BASIC_CONFIG
        )


@pytest.fixture
async def flow_at_add_account_step(hass, flow_at_user_step):
    """Return a initialized flow at the additional account step."""
    return await hass.config_entries.flow.async_configure(
        flow_at_user_step["flow_id"], BASIC_CONFIG_ADDITIONAL
    )


@pytest.fixture
async def entry_with_additional_account_config(hass, flow_at_add_account_step):
    """Return a entry with a two account config."""
    with patch("pysiaalarm.aio.SIAClient.start", return_value=True):
        return await hass.config_entries.flow.async_configure(
            flow_at_add_account_step["flow_id"], ADDITIONAL_ACCOUNT
        )


async def setup_sia(hass, config_entry: MockConfigEntry):
    """Add mock config to HASS."""
    assert await async_setup_component(hass, DOMAIN, {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_form_start(
    hass, flow_at_user_step, flow_at_add_account_step, additional
):
    """Start the form and check if you get the right id and schema."""
    if additional:
        assert flow_at_add_account_step["step_id"] == "add_account"
        assert flow_at_add_account_step["errors"] is None
        assert flow_at_add_account_step["data_schema"] == ACCOUNT_SCHEMA
        return
    assert flow_at_user_step["step_id"] == "user"
    assert flow_at_user_step["errors"] is None
    assert flow_at_user_step["data_schema"] == HUB_SCHEMA


async def test_create(hass, entry_with_basic_config):
    """Test we create a entry through the form."""
    assert entry_with_basic_config["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert (
        entry_with_basic_config["title"]
        == f"SIA Alarm on port {BASIC_CONFIG[CONF_PORT]}"
    )
    assert entry_with_basic_config["data"] == BASE_OUT["data"]
    assert entry_with_basic_config["options"] == BASE_OUT["options"]


async def test_create_additional_account(hass, entry_with_additional_account_config):
    """Test we create a config with two accounts."""
    assert (
        entry_with_additional_account_config["type"]
        == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    )
    assert (
        entry_with_additional_account_config["title"]
        == f"SIA Alarm on port {BASIC_CONFIG[CONF_PORT]}"
    )

    assert entry_with_additional_account_config["data"] == ADDITIONAL_OUT["data"]
    assert entry_with_additional_account_config["options"] == ADDITIONAL_OUT["options"]


async def test_abort_form(hass, entry_with_basic_config):
    """Test aborting a config that already exists."""
    assert entry_with_basic_config["data"][CONF_PORT] == BASIC_CONFIG[CONF_PORT]
    start_another_flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    get_abort = await hass.config_entries.flow.async_configure(
        start_another_flow["flow_id"], BASIC_CONFIG
    )
    assert get_abort["type"] == "abort"
    assert get_abort["reason"] == "already_configured"


@pytest.mark.parametrize(
    "field, value, error",
    [
        ("encryption_key", "AAAAAAAAAAAAAZZZ", "invalid_key_format"),
        ("encryption_key", "AAAAAAAAAAAAA", "invalid_key_length"),
        ("account", "ZZZ", "invalid_account_format"),
        ("account", "A", "invalid_account_length"),
        ("ping_interval", 1500, "invalid_ping"),
        ("zones", 0, "invalid_zones"),
    ],
)
async def test_validation_errors(
    hass,
    flow_at_user_step,
    additional,
    field,
    value,
    error,
):
    """Test we handle the different invalid inputs, both in the user and add_account flow."""
    config = BASIC_CONFIG.copy()
    flow_id = flow_at_user_step["flow_id"]
    if additional:
        flow_at_add_account_step = await hass.config_entries.flow.async_configure(
            flow_at_user_step["flow_id"], BASIC_CONFIG_ADDITIONAL
        )
        config = ADDITIONAL_ACCOUNT.copy()
        flow_id = flow_at_add_account_step["flow_id"]

    config[field] = value
    result_err = await hass.config_entries.flow.async_configure(flow_id, config)
    assert result_err["type"] == "form"
    assert result_err["errors"] == {"base": error}


async def test_unknown(hass, flow_at_user_step, additional):
    """Test unknown exceptions."""
    flow_id = flow_at_user_step["flow_id"]
    if additional:
        flow_at_add_account_step = await hass.config_entries.flow.async_configure(
            flow_at_user_step["flow_id"], BASIC_CONFIG_ADDITIONAL
        )
        flow_id = flow_at_add_account_step["flow_id"]
    with patch(
        "pysiaalarm.SIAAccount.validate_account",
        side_effect=Exception,
    ):
        config = ADDITIONAL_ACCOUNT if additional else BASIC_CONFIG
        result_err = await hass.config_entries.flow.async_configure(flow_id, config)
        assert result_err
        assert result_err["step_id"] == "add_account" if additional else "user"
        assert result_err["errors"] == {"base": "unknown"}
        assert result_err["data_schema"] == ACCOUNT_SCHEMA if additional else HUB_SCHEMA


async def test_options_basic(hass):
    """Test options flow for single account."""
    await setup_sia(hass, BASIC_CONFIG_ENTRY)
    result = await hass.config_entries.options.async_init(BASIC_CONFIG_ENTRY.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "options"
    assert result["last_step"]

    updated = await hass.config_entries.options.async_configure(
        result["flow_id"], BASIC_OPTIONS
    )
    assert updated["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert updated["data"] == {
        CONF_ACCOUNTS: {BASIC_CONFIG[CONF_ACCOUNT]: BASIC_OPTIONS}
    }


async def test_options_additional(hass):
    """Test options flow for single account."""
    await setup_sia(hass, ADDITIONAL_CONFIG_ENTRY)
    result = await hass.config_entries.options.async_init(
        ADDITIONAL_CONFIG_ENTRY.entry_id
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "options"
    assert not result["last_step"]

    updated = await hass.config_entries.options.async_configure(
        result["flow_id"], BASIC_OPTIONS
    )
    assert updated["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert updated["step_id"] == "options"
    assert updated["last_step"]
