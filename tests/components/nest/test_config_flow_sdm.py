"""Test the Google Nest Device Access config flow.

The Nest SDM API integration supports two approaches for configuration:
  - Using config flow only, the new preferred approach
  - Using configuration.yaml, the old way similar to how the legacy works
    with nest integration works.

This file exercises tests in both approaches.  The tests for configuration.yaml
approach have a suffix of "_from_yaml".
"""

import pytest
from voluptuous.error import MultipleInvalid

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.nest.const import (
    CONF_PROJECT_ID,
    CONF_SUBSCRIBER_ID,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

from .common import MockConfigEntry

from tests.async_mock import patch

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
PROJECT_ID = "project-id-4321"
SUBSCRIBER_ID = "subscriber-id-9876"

# Used in either ConfigEntry data or configuration.yaml
DEVICE_ACCESS_CONFIG = {
    CONF_PROJECT_ID: PROJECT_ID,
    CONF_CLIENT_ID: CLIENT_ID,
    CONF_CLIENT_SECRET: CLIENT_SECRET,
}
SUBSCRIBER_CONFIG = {
    CONF_SUBSCRIBER_ID: SUBSCRIBER_ID,
}

# A configuration.yaml without a "nest:" clause
EMPTY_CONFIG = {
    "http": {"base_url": "https://example.com"},
}


# A configuration.yaml with a "nest:" clause, the old way to configure the
# integration.
CONFIG_FROM_YAML = {
    DOMAIN: {
        **DEVICE_ACCESS_CONFIG,
        **SUBSCRIBER_CONFIG,
    },
    "http": {"base_url": "https://example.com"},
}

OAUTH_RESPONSE = {
    "refresh_token": "mock-refresh-token",
    "access_token": "mock-access-token",
    "type": "Bearer",
    "expires_in": 60,
}

EXPECTED_CONFIG_ENTRY_DATA = {
    "auth_implementation": "nest",
    "token": OAUTH_RESPONSE,
    **DEVICE_ACCESS_CONFIG,
    **SUBSCRIBER_CONFIG,
    "sdm": {},
}


def get_config_entry(hass):
    """Return a single config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    return entries[0]


class FlowFixture:
    """Facilitate testing of a ConfigFlow."""

    def __init__(self, hass, aiohttp_client, aioclient_mock):
        """Initialize OAuthFixture."""
        self.hass = hass
        self.aiohttp_client = aiohttp_client
        self.aioclient_mock = aioclient_mock

        # Preserve every step of the flow
        self.result = None

        # Set to true when setup is complete
        self.setup_called = False

    async def async_init(
        self, source: str = config_entries.SOURCE_USER, data: dict = None
    ):
        """Initialize the Config Flow."""
        self.result = await self.hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        return self.result

    async def async_next(self, user_input: dict):
        """Advance to the next step in the config flow."""
        with patch(
            "homeassistant.components.nest.async_setup_entry", return_value=True
        ) as mock_setup:
            self.result = await self.hass.config_entries.flow.async_configure(
                self.result["flow_id"], user_input=user_input
            )
            self.setup_called = len(mock_setup.mock_calls) > 0
        return self.result

    async def async_oauth_flow(self):
        """Verify auth redirect and prepare fake OAuth responses."""
        state = config_entry_oauth2_flow._encode_jwt(
            self.hass,
            {
                "flow_id": self.result["flow_id"],
                "redirect_uri": "https://example.com/auth/external/callback",
            },
        )

        oauth_authorize = OAUTH2_AUTHORIZE.format(project_id=PROJECT_ID)
        assert self.result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
        assert self.result["step_id"] == "auth"
        assert self.result["url"] == (
            f"{oauth_authorize}?response_type=code&client_id={CLIENT_ID}"
            "&redirect_uri=https://example.com/auth/external/callback"
            f"&state={state}&scope=https://www.googleapis.com/auth/sdm.service"
            "+https://www.googleapis.com/auth/pubsub"
            "&access_type=offline&prompt=consent"
        )

        client = await self.aiohttp_client(self.hass.http.app)
        resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
        assert resp.status == 200
        assert resp.headers["content-type"] == "text/html; charset=utf-8"

        self.aioclient_mock.post(OAUTH2_TOKEN, json=OAUTH_RESPONSE)


@pytest.fixture
async def flow_fixture(hass, aiohttp_client, aioclient_mock, current_request_with_host):
    """Create the flow test fixture."""
    return FlowFixture(hass, aiohttp_client, aioclient_mock)


async def test_full_flow(hass, flow_fixture):
    """Check full flow."""
    assert await setup.async_setup_component(hass, DOMAIN, EMPTY_CONFIG)

    result = await flow_fixture.async_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device_access"
    # No default values
    with pytest.raises(MultipleInvalid):
        assert result["data_schema"]({}) == ""

    result = await flow_fixture.async_next(user_input=DEVICE_ACCESS_CONFIG)
    await flow_fixture.async_oauth_flow()
    result = await flow_fixture.async_next(user_input={})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pubsub"
    # No default values
    with pytest.raises(MultipleInvalid):
        assert result["data_schema"]({}) == ""

    result = await flow_fixture.async_next(user_input=SUBSCRIBER_CONFIG)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert flow_fixture.setup_called

    # Verify existing tokens are replaced
    entry = get_config_entry(hass)
    entry.data["token"].pop("expires_at")
    assert entry.unique_id == DOMAIN
    assert dict(entry.data) == EXPECTED_CONFIG_ENTRY_DATA


async def test_full_flow_from_yaml(hass, flow_fixture):
    """Check full flow from a configuration.yaml."""
    assert await setup.async_setup_component(hass, DOMAIN, CONFIG_FROM_YAML)

    result = await flow_fixture.async_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device_access"
    # Default values populated from yaml config
    assert result["data_schema"]({}) == DEVICE_ACCESS_CONFIG

    result = await flow_fixture.async_next(user_input=DEVICE_ACCESS_CONFIG)
    await flow_fixture.async_oauth_flow()
    result = await flow_fixture.async_next(user_input={})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pubsub"
    # Verify default values are populated from yaml config
    assert result["data_schema"]({}) == SUBSCRIBER_CONFIG

    result = await flow_fixture.async_next(user_input=SUBSCRIBER_CONFIG)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert flow_fixture.setup_called

    entry = get_config_entry(hass)
    entry.data["token"].pop("expires_at")
    assert entry.unique_id == DOMAIN
    assert dict(entry.data) == EXPECTED_CONFIG_ENTRY_DATA


async def test_reauth(hass, flow_fixture):
    """Test Nest reauthentication."""
    old_data = EXPECTED_CONFIG_ENTRY_DATA.copy()
    old_data["token"] = {"access_token": "some-revoked-token"}
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data=old_data,
        unique_id=DOMAIN,
    )
    old_entry.add_to_hass(hass)

    assert await setup.async_setup_component(hass, DOMAIN, EMPTY_CONFIG)

    entry = get_config_entry(hass)
    assert entry.data["token"] == {
        "access_token": "some-revoked-token",
    }

    # Initiate the reauth flow
    result = await flow_fixture.async_init(
        config_entries.SOURCE_REAUTH,
        data=old_entry.data,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    # Start normal config flow
    result = await flow_fixture.async_next(user_input={})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device_access"
    # Default values populated from existing config entry
    assert result["data_schema"]({}) == DEVICE_ACCESS_CONFIG

    result = await flow_fixture.async_next(user_input=DEVICE_ACCESS_CONFIG)
    await flow_fixture.async_oauth_flow()
    result = await flow_fixture.async_next(user_input={})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pubsub"
    # Verify default values are populated from existing config entry
    assert result["data_schema"]({}) == SUBSCRIBER_CONFIG
    result = await flow_fixture.async_next(user_input=SUBSCRIBER_CONFIG)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert flow_fixture.setup_called

    # Verify existing tokens are replaced
    entry = get_config_entry(hass)
    entry.data["token"].pop("expires_at")
    assert entry.unique_id == DOMAIN
    assert dict(entry.data) == EXPECTED_CONFIG_ENTRY_DATA


async def test_reauth_from_yaml(hass, flow_fixture):
    """Test Nest reauthentication from configuration.yaml."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                # Verify this is replaced at end of the test
                "access_token": "some-revoked-token",
            },
            "sdm": {},
        },
        unique_id=DOMAIN,
    )
    old_entry.add_to_hass(hass)

    assert await setup.async_setup_component(hass, DOMAIN, CONFIG_FROM_YAML)

    entry = get_config_entry(hass)
    assert entry.data["token"] == {
        "access_token": "some-revoked-token",
    }

    # Initiate the reauth flow
    result = await flow_fixture.async_init(
        config_entries.SOURCE_REAUTH,
        data=old_entry.data,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    # Start normal config flow
    result = await flow_fixture.async_next(user_input={})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device_access"
    # Default values populated from existing config entry
    assert result["data_schema"]({}) == DEVICE_ACCESS_CONFIG

    result = await flow_fixture.async_next(user_input=DEVICE_ACCESS_CONFIG)
    await flow_fixture.async_oauth_flow()
    result = await flow_fixture.async_next(user_input={})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pubsub"
    # Verify default values are populated from existing config entry
    assert result["data_schema"]({}) == SUBSCRIBER_CONFIG
    result = await flow_fixture.async_next(user_input=SUBSCRIBER_CONFIG)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert flow_fixture.setup_called

    # Verify existing tokens are replaced
    entry = get_config_entry(hass)
    entry.data["token"].pop("expires_at")
    assert entry.unique_id == DOMAIN
    assert dict(entry.data) == EXPECTED_CONFIG_ENTRY_DATA


async def test_reauth_missing_input(hass, flow_fixture):
    """Test Nest reauthentication with invalid parameters passed."""
    assert await setup.async_setup_component(hass, DOMAIN, EMPTY_CONFIG)

    result = await flow_fixture.async_init(
        config_entries.SOURCE_REAUTH,
        data=None,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "missing_configuration"


async def test_single_config_entry_from_yaml(hass, flow_fixture):
    """Test that only a single config entry is allowed."""
    old_entry = MockConfigEntry(
        domain=DOMAIN, data={"auth_implementation": DOMAIN, "sdm": {}}
    )
    old_entry.add_to_hass(hass)

    assert await setup.async_setup_component(hass, DOMAIN, CONFIG_FROM_YAML)

    result = await flow_fixture.async_init()
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_unexpected_existing_config_entries_from_yaml(hass, flow_fixture):
    """Test Nest reauthentication with multiple existing config entries."""
    # Note that this case will not happen in the future since only a single
    # instance is now allowed, but this may have been allowed in the past.
    # On reauth, only one entry is kept and the others are deleted.

    old_entry = MockConfigEntry(
        domain=DOMAIN, data={"auth_implementation": DOMAIN, "sdm": {}}
    )
    old_entry.add_to_hass(hass)

    old_entry = MockConfigEntry(
        domain=DOMAIN, data={"auth_implementation": DOMAIN, "sdm": {}}
    )
    old_entry.add_to_hass(hass)

    assert await setup.async_setup_component(hass, DOMAIN, CONFIG_FROM_YAML)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2

    # Invoke the reauth flow
    result = await flow_fixture.async_init(
        config_entries.SOURCE_REAUTH,
        data=old_entry.data,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    result = await flow_fixture.async_next(user_input={})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device_access"
    # Verify default values are populated from existing config entry
    assert result["data_schema"]({}) == DEVICE_ACCESS_CONFIG
    result = await flow_fixture.async_next(user_input={})
    await flow_fixture.async_oauth_flow()
    result = await flow_fixture.async_next(user_input={})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pubsub"
    # Verify default values are populated from existing config entry
    assert result["data_schema"]({}) == SUBSCRIBER_CONFIG
    result = await flow_fixture.async_next(user_input=SUBSCRIBER_CONFIG)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert flow_fixture.setup_called

    # Only a single entry now exists, and the other was cleaned up
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.unique_id == DOMAIN
    entry.data["token"].pop("expires_at")
    assert dict(entry.data) == EXPECTED_CONFIG_ENTRY_DATA
