"""Test config entries API."""

from collections import OrderedDict
from http import HTTPStatus
from unittest.mock import ANY, AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries as core_ce, data_entry_flow
from homeassistant.components.config import config_entries
from homeassistant.config_entries import HANDLERS, ConfigFlow
from homeassistant.core import callback
from homeassistant.generated import config_flows
from homeassistant.helpers import config_entry_flow, config_validation as cv
from homeassistant.loader import IntegrationNotFound
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_entity_platform,
    mock_integration,
)


@pytest.fixture
def clear_handlers():
    """Clear config entry handlers."""
    with patch.dict(HANDLERS, clear=True):
        yield


@pytest.fixture(autouse=True)
def mock_test_component(hass):
    """Ensure a component called 'test' exists."""
    mock_integration(hass, MockModule("test"))


@pytest.fixture
async def client(hass, hass_client):
    """Fixture that can interact with the config manager API."""
    await async_setup_component(hass, "http", {})
    await config_entries.async_setup(hass)
    return await hass_client()


async def test_get_entries(hass, client, clear_handlers):
    """Test get entries."""
    mock_integration(hass, MockModule("comp1"))
    mock_integration(
        hass, MockModule("comp2", partial_manifest={"integration_type": "helper"})
    )
    mock_integration(hass, MockModule("comp3"))

    @HANDLERS.register("comp1")
    class Comp1ConfigFlow:
        """Config flow with options flow."""

        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            """Get options flow."""
            pass

        @classmethod
        @callback
        def async_supports_options_flow(cls, config_entry):
            """Return options flow support for this handler."""
            return True

    config_entry_flow.register_discovery_flow("comp2", "Comp 2", lambda: None)

    entry = MockConfigEntry(
        domain="comp1",
        title="Test 1",
        source="bla",
    )
    entry.supports_unload = True
    entry.add_to_hass(hass)
    MockConfigEntry(
        domain="comp2",
        title="Test 2",
        source="bla2",
        state=core_ce.ConfigEntryState.SETUP_ERROR,
        reason="Unsupported API",
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="comp3",
        title="Test 3",
        source="bla3",
        disabled_by=core_ce.ConfigEntryDisabler.USER,
    ).add_to_hass(hass)

    resp = await client.get("/api/config/config_entries/entry")
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    for entry in data:
        entry.pop("entry_id")
    assert data == [
        {
            "domain": "comp1",
            "title": "Test 1",
            "source": "bla",
            "state": core_ce.ConfigEntryState.NOT_LOADED.value,
            "supports_options": True,
            "supports_remove_device": False,
            "supports_unload": True,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "disabled_by": None,
            "reason": None,
        },
        {
            "domain": "comp2",
            "title": "Test 2",
            "source": "bla2",
            "state": core_ce.ConfigEntryState.SETUP_ERROR.value,
            "supports_options": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "disabled_by": None,
            "reason": "Unsupported API",
        },
        {
            "domain": "comp3",
            "title": "Test 3",
            "source": "bla3",
            "state": core_ce.ConfigEntryState.NOT_LOADED.value,
            "supports_options": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "disabled_by": core_ce.ConfigEntryDisabler.USER,
            "reason": None,
        },
    ]

    resp = await client.get("/api/config/config_entries/entry?domain=comp3")
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert len(data) == 1
    assert data[0]["domain"] == "comp3"

    resp = await client.get("/api/config/config_entries/entry?domain=comp3&type=helper")
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert len(data) == 0

    resp = await client.get(
        "/api/config/config_entries/entry?domain=comp3&type=integration"
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert len(data) == 1

    resp = await client.get("/api/config/config_entries/entry?type=integration")
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert len(data) == 2
    assert data[0]["domain"] == "comp1"
    assert data[1]["domain"] == "comp3"


async def test_remove_entry(hass, client):
    """Test removing an entry via the API."""
    entry = MockConfigEntry(domain="demo", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    resp = await client.delete(f"/api/config/config_entries/entry/{entry.entry_id}")
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data == {"require_restart": True}
    assert len(hass.config_entries.async_entries()) == 0


async def test_reload_entry(hass, client):
    """Test reloading an entry via the API."""
    entry = MockConfigEntry(domain="demo", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    resp = await client.post(
        f"/api/config/config_entries/entry/{entry.entry_id}/reload"
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data == {"require_restart": True}
    assert len(hass.config_entries.async_entries()) == 1


async def test_reload_invalid_entry(hass, client):
    """Test reloading an invalid entry via the API."""
    resp = await client.post("/api/config/config_entries/entry/invalid/reload")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_remove_entry_unauth(hass, client, hass_admin_user):
    """Test removing an entry via the API."""
    hass_admin_user.groups = []
    entry = MockConfigEntry(domain="demo", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    resp = await client.delete(f"/api/config/config_entries/entry/{entry.entry_id}")
    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert len(hass.config_entries.async_entries()) == 1


async def test_reload_entry_unauth(hass, client, hass_admin_user):
    """Test reloading an entry via the API."""
    hass_admin_user.groups = []
    entry = MockConfigEntry(domain="demo", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    resp = await client.post(
        f"/api/config/config_entries/entry/{entry.entry_id}/reload"
    )
    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert len(hass.config_entries.async_entries()) == 1


async def test_reload_entry_in_failed_state(hass, client, hass_admin_user):
    """Test reloading an entry via the API that has already failed to unload."""
    entry = MockConfigEntry(domain="demo", state=core_ce.ConfigEntryState.FAILED_UNLOAD)
    entry.add_to_hass(hass)
    resp = await client.post(
        f"/api/config/config_entries/entry/{entry.entry_id}/reload"
    )
    assert resp.status == HTTPStatus.FORBIDDEN
    assert len(hass.config_entries.async_entries()) == 1


async def test_reload_entry_in_setup_retry(hass, client, hass_admin_user):
    """Test reloading an entry via the API that is in setup retry."""
    mock_setup_entry = AsyncMock(return_value=True)
    mock_unload_entry = AsyncMock(return_value=True)
    mock_migrate_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_entity_platform(hass, "config_flow.comp", None)
    entry = MockConfigEntry(domain="comp", state=core_ce.ConfigEntryState.SETUP_RETRY)
    entry.supports_unload = True
    entry.add_to_hass(hass)

    with patch.dict(HANDLERS, {"comp": ConfigFlow, "test": ConfigFlow}):
        resp = await client.post(
            f"/api/config/config_entries/entry/{entry.entry_id}/reload"
        )
        await hass.async_block_till_done()
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data == {"require_restart": False}
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    "type_filter,result",
    (
        (None, {"hello", "another", "world"}),
        ("integration", {"hello", "another"}),
        ("helper", {"world"}),
    ),
)
async def test_available_flows(hass, client, type_filter, result):
    """Test querying the available flows."""
    with patch.object(
        config_flows,
        "FLOWS",
        {"integration": ["hello", "another"], "helper": ["world"]},
    ):
        resp = await client.get(
            "/api/config/config_entries/flow_handlers",
            params={"type": type_filter} if type_filter else {},
        )
        assert resp.status == HTTPStatus.OK
        data = await resp.json()
        assert set(data) == result


############################
#  FLOW MANAGER API TESTS  #
############################


async def test_initialize_flow(hass, client):
    """Test we can initialize a flow."""
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required("username")] = str
            schema[vol.Required("password")] = str

            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                description_placeholders={
                    "url": "https://example.com",
                    "show_advanced_options": self.show_advanced_options,
                },
                errors={"username": "Should be unique."},
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow",
            json={"handler": "test", "show_advanced_options": True},
        )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    data.pop("flow_id")

    assert data == {
        "type": "form",
        "handler": "test",
        "step_id": "user",
        "data_schema": [
            {"name": "username", "required": True, "type": "string"},
            {"name": "password", "required": True, "type": "string"},
        ],
        "description_placeholders": {
            "url": "https://example.com",
            "show_advanced_options": True,
        },
        "errors": {"username": "Should be unique."},
        "last_step": None,
    }


async def test_initialize_flow_unmet_dependency(hass, client):
    """Test unmet dependencies are listed."""
    mock_entity_platform(hass, "config_flow.test", None)

    config_schema = vol.Schema({"comp_conf": {"hello": str}}, required=True)
    mock_integration(
        hass, MockModule(domain="dependency_1", config_schema=config_schema)
    )
    # The test2 config flow should  fail because dependency_1 can't be automatically setup
    mock_integration(
        hass,
        MockModule(domain="test2", partial_manifest={"dependencies": ["dependency_1"]}),
    )

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            pass

    with patch.dict(HANDLERS, {"test2": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow",
            json={"handler": "test2", "show_advanced_options": True},
        )

    assert resp.status == HTTPStatus.BAD_REQUEST
    data = await resp.text()
    assert data == "Failed dependencies dependency_1"


async def test_initialize_flow_unauth(hass, client, hass_admin_user):
    """Test we can initialize a flow."""
    hass_admin_user.groups = []

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required("username")] = str
            schema[vol.Required("password")] = str

            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                description_placeholders={"url": "https://example.com"},
                errors={"username": "Should be unique."},
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_abort(hass, client):
    """Test a flow that aborts."""
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            return self.async_abort(reason="bla")

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    data.pop("flow_id")
    assert data == {
        "description_placeholders": None,
        "handler": "test",
        "reason": "bla",
        "type": "abort",
    }


async def test_create_account(hass, client, enable_custom_integrations):
    """Test a flow that creates an account."""
    mock_entity_platform(hass, "config_flow.test", None)

    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            return self.async_create_entry(
                title="Test Entry", data={"secret": "account_token"}
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == HTTPStatus.OK

    entries = hass.config_entries.async_entries("test")
    assert len(entries) == 1

    data = await resp.json()
    data.pop("flow_id")
    assert data == {
        "handler": "test",
        "title": "Test Entry",
        "type": "create_entry",
        "version": 1,
        "result": {
            "disabled_by": None,
            "domain": "test",
            "entry_id": entries[0].entry_id,
            "source": core_ce.SOURCE_USER,
            "state": core_ce.ConfigEntryState.LOADED.value,
            "supports_options": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "title": "Test Entry",
            "reason": None,
        },
        "description": None,
        "description_placeholders": None,
        "options": {},
    }


async def test_two_step_flow(hass, client, enable_custom_integrations):
    """Test we can finish a two step flow."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            return self.async_show_form(
                step_id="account", data_schema=vol.Schema({"user_title": str})
            )

        async def async_step_account(self, user_input=None):
            return self.async_create_entry(
                title=user_input["user_title"], data={"secret": "account_token"}
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )
        assert resp.status == HTTPStatus.OK
        data = await resp.json()
        flow_id = data.pop("flow_id")
        assert data == {
            "type": "form",
            "handler": "test",
            "step_id": "account",
            "data_schema": [{"name": "user_title", "type": "string"}],
            "description_placeholders": None,
            "errors": None,
            "last_step": None,
        }

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            f"/api/config/config_entries/flow/{flow_id}",
            json={"user_title": "user-title"},
        )
        assert resp.status == HTTPStatus.OK

        entries = hass.config_entries.async_entries("test")
        assert len(entries) == 1

        data = await resp.json()
        data.pop("flow_id")
        assert data == {
            "handler": "test",
            "type": "create_entry",
            "title": "user-title",
            "version": 1,
            "result": {
                "disabled_by": None,
                "domain": "test",
                "entry_id": entries[0].entry_id,
                "source": core_ce.SOURCE_USER,
                "state": core_ce.ConfigEntryState.LOADED.value,
                "supports_options": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "title": "user-title",
                "reason": None,
            },
            "description": None,
            "description_placeholders": None,
            "options": {},
        }


async def test_continue_flow_unauth(hass, client, hass_admin_user):
    """Test we can't finish a two step flow."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            return self.async_show_form(
                step_id="account", data_schema=vol.Schema({"user_title": str})
            )

        async def async_step_account(self, user_input=None):
            return self.async_create_entry(
                title=user_input["user_title"], data={"secret": "account_token"}
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )
        assert resp.status == HTTPStatus.OK
        data = await resp.json()
        flow_id = data.pop("flow_id")
        assert data == {
            "type": "form",
            "handler": "test",
            "step_id": "account",
            "data_schema": [{"name": "user_title", "type": "string"}],
            "description_placeholders": None,
            "errors": None,
            "last_step": None,
        }

    hass_admin_user.groups = []

    resp = await client.post(
        f"/api/config/config_entries/flow/{flow_id}",
        json={"user_title": "user-title"},
    )
    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_get_progress_index(hass, hass_ws_client):
    """Test querying for the flows that are in progress."""
    assert await async_setup_component(hass, "config", {})
    mock_entity_platform(hass, "config_flow.test", None)
    ws_client = await hass_ws_client(hass)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 5

        async def async_step_hassio(self, info):
            return await self.async_step_account()

        async def async_step_account(self, user_input=None):
            return self.async_show_form(step_id="account")

    with patch.dict(HANDLERS, {"test": TestFlow}):
        form = await hass.config_entries.flow.async_init(
            "test", context={"source": core_ce.SOURCE_HASSIO}
        )

    await ws_client.send_json({"id": 5, "type": "config_entries/flow/progress"})
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == [
        {
            "flow_id": form["flow_id"],
            "handler": "test",
            "step_id": "account",
            "context": {"source": core_ce.SOURCE_HASSIO},
        }
    ]


async def test_get_progress_index_unauth(hass, hass_ws_client, hass_admin_user):
    """Test we can't get flows that are in progress."""
    assert await async_setup_component(hass, "config", {})
    hass_admin_user.groups = []
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 5, "type": "config_entries/flow/progress"})
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"


async def test_get_progress_flow(hass, client):
    """Test we can query the API for same result as we get from init a flow."""
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required("username")] = str
            schema[vol.Required("password")] = str

            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                errors={"username": "Should be unique."},
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    resp2 = await client.get(
        "/api/config/config_entries/flow/{}".format(data["flow_id"])
    )

    assert resp2.status == HTTPStatus.OK
    data2 = await resp2.json()

    assert data == data2


async def test_get_progress_flow_unauth(hass, client, hass_admin_user):
    """Test we can can't query the API for result of flow."""
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required("username")] = str
            schema[vol.Required("password")] = str

            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                errors={"username": "Should be unique."},
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    hass_admin_user.groups = []

    resp2 = await client.get(
        "/api/config/config_entries/flow/{}".format(data["flow_id"])
    )

    assert resp2.status == HTTPStatus.UNAUTHORIZED


async def test_options_flow(hass, client):
    """Test we can change options."""

    class TestFlow(core_ce.ConfigFlow):
        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            class OptionsFlowHandler(data_entry_flow.FlowHandler):
                async def async_step_init(self, user_input=None):
                    schema = OrderedDict()
                    schema[vol.Required("enabled")] = bool
                    return self.async_show_form(
                        step_id="user",
                        data_schema=schema,
                        description_placeholders={"enabled": "Set to true to be true"},
                    )

            return OptionsFlowHandler()

    MockConfigEntry(
        domain="test",
        entry_id="test1",
        source="bla",
    ).add_to_hass(hass)
    entry = hass.config_entries.async_entries()[0]

    with patch.dict(HANDLERS, {"test": TestFlow}):
        url = "/api/config/config_entries/options/flow"
        resp = await client.post(url, json={"handler": entry.entry_id})

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    data.pop("flow_id")
    assert data == {
        "type": "form",
        "handler": "test1",
        "step_id": "user",
        "data_schema": [{"name": "enabled", "required": True, "type": "boolean"}],
        "description_placeholders": {"enabled": "Set to true to be true"},
        "errors": None,
        "last_step": None,
    }


async def test_two_step_options_flow(hass, client):
    """Test we can finish a two step options flow."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )

    class TestFlow(core_ce.ConfigFlow):
        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            class OptionsFlowHandler(data_entry_flow.FlowHandler):
                async def async_step_init(self, user_input=None):
                    return self.async_show_form(
                        step_id="finish", data_schema=vol.Schema({"enabled": bool})
                    )

                async def async_step_finish(self, user_input=None):
                    return self.async_create_entry(
                        title="Enable disable", data=user_input
                    )

            return OptionsFlowHandler()

    MockConfigEntry(
        domain="test",
        entry_id="test1",
        source="bla",
    ).add_to_hass(hass)
    entry = hass.config_entries.async_entries()[0]

    with patch.dict(HANDLERS, {"test": TestFlow}):
        url = "/api/config/config_entries/options/flow"
        resp = await client.post(url, json={"handler": entry.entry_id})

        assert resp.status == HTTPStatus.OK
        data = await resp.json()
        flow_id = data.pop("flow_id")
        assert data == {
            "type": "form",
            "handler": "test1",
            "step_id": "finish",
            "data_schema": [{"name": "enabled", "type": "boolean"}],
            "description_placeholders": None,
            "errors": None,
            "last_step": None,
        }

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            f"/api/config/config_entries/options/flow/{flow_id}",
            json={"enabled": True},
        )
        assert resp.status == HTTPStatus.OK
        data = await resp.json()
        data.pop("flow_id")
        assert data == {
            "handler": "test1",
            "type": "create_entry",
            "title": "Enable disable",
            "version": 1,
            "description": None,
            "description_placeholders": None,
        }


async def test_options_flow_with_invalid_data(hass, client):
    """Test an options flow with invalid_data."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )

    class TestFlow(core_ce.ConfigFlow):
        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            class OptionsFlowHandler(data_entry_flow.FlowHandler):
                async def async_step_init(self, user_input=None):
                    return self.async_show_form(
                        step_id="finish",
                        data_schema=vol.Schema(
                            {
                                vol.Required(
                                    "choices", default=["invalid", "valid"]
                                ): cv.multi_select({"valid": "Valid"})
                            }
                        ),
                    )

                async def async_step_finish(self, user_input=None):
                    return self.async_create_entry(
                        title="Enable disable", data=user_input
                    )

            return OptionsFlowHandler()

    MockConfigEntry(
        domain="test",
        entry_id="test1",
        source="bla",
    ).add_to_hass(hass)
    entry = hass.config_entries.async_entries()[0]

    with patch.dict(HANDLERS, {"test": TestFlow}):
        url = "/api/config/config_entries/options/flow"
        resp = await client.post(url, json={"handler": entry.entry_id})

        assert resp.status == HTTPStatus.OK
        data = await resp.json()
        flow_id = data.pop("flow_id")
        assert data == {
            "type": "form",
            "handler": "test1",
            "step_id": "finish",
            "data_schema": [
                {
                    "default": ["invalid", "valid"],
                    "name": "choices",
                    "options": {"valid": "Valid"},
                    "required": True,
                    "type": "multi_select",
                }
            ],
            "description_placeholders": None,
            "errors": None,
            "last_step": None,
        }

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            f"/api/config/config_entries/options/flow/{flow_id}",
            json={"choices": ["valid", "invalid"]},
        )
        assert resp.status == HTTPStatus.BAD_REQUEST
        data = await resp.json()
        assert data == {
            "message": "User input malformed: invalid is not a valid option for "
            "dictionary value @ data['choices']"
        }


async def test_update_prefrences(hass, hass_ws_client):
    """Test that we can update system options."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(domain="demo", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)

    assert entry.pref_disable_new_entities is False
    assert entry.pref_disable_polling is False

    await ws_client.send_json(
        {
            "id": 6,
            "type": "config_entries/update",
            "entry_id": entry.entry_id,
            "pref_disable_new_entities": True,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"]["require_restart"] is False
    assert response["result"]["config_entry"]["pref_disable_new_entities"] is True
    assert response["result"]["config_entry"]["pref_disable_polling"] is False

    assert entry.pref_disable_new_entities is True
    assert entry.pref_disable_polling is False

    await ws_client.send_json(
        {
            "id": 7,
            "type": "config_entries/update",
            "entry_id": entry.entry_id,
            "pref_disable_new_entities": False,
            "pref_disable_polling": True,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"]["require_restart"] is True
    assert response["result"]["config_entry"]["pref_disable_new_entities"] is False
    assert response["result"]["config_entry"]["pref_disable_polling"] is True

    assert entry.pref_disable_new_entities is False
    assert entry.pref_disable_polling is True


async def test_update_entry(hass, hass_ws_client):
    """Test that we can update entry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(domain="demo", title="Initial Title")
    entry.add_to_hass(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/update",
            "entry_id": entry.entry_id,
            "title": "Updated Title",
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"]["config_entry"]["title"] == "Updated Title"
    assert entry.title == "Updated Title"


async def test_update_entry_nonexisting(hass, hass_ws_client):
    """Test that we can update entry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/update",
            "entry_id": "non_existing",
            "title": "Updated Title",
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "not_found"


async def test_disable_entry(hass, hass_ws_client):
    """Test that we can disable entry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(domain="demo", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    assert entry.disabled_by is None

    # Disable
    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/disable",
            "entry_id": entry.entry_id,
            "disabled_by": core_ce.ConfigEntryDisabler.USER,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == {"require_restart": True}
    assert entry.disabled_by is core_ce.ConfigEntryDisabler.USER
    assert entry.state is core_ce.ConfigEntryState.FAILED_UNLOAD

    # Enable
    await ws_client.send_json(
        {
            "id": 6,
            "type": "config_entries/disable",
            "entry_id": entry.entry_id,
            "disabled_by": None,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == {"require_restart": True}
    assert entry.disabled_by is None
    assert entry.state == core_ce.ConfigEntryState.FAILED_UNLOAD

    # Enable again -> no op
    await ws_client.send_json(
        {
            "id": 7,
            "type": "config_entries/disable",
            "entry_id": entry.entry_id,
            "disabled_by": None,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == {"require_restart": False}
    assert entry.disabled_by is None
    assert entry.state == core_ce.ConfigEntryState.FAILED_UNLOAD


async def test_disable_entry_nonexisting(hass, hass_ws_client):
    """Test that we can disable entry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/disable",
            "entry_id": "non_existing",
            "disabled_by": core_ce.ConfigEntryDisabler.USER,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "not_found"


async def test_ignore_flow(hass, hass_ws_client):
    """Test we can ignore a flow."""
    assert await async_setup_component(hass, "config", {})
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_entity_platform(hass, "config_flow.test", None)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            await self.async_set_unique_id("mock-unique-id")
            return self.async_show_form(step_id="account")

    ws_client = await hass_ws_client(hass)

    with patch.dict(HANDLERS, {"test": TestFlow}):
        result = await hass.config_entries.flow.async_init(
            "test", context={"source": core_ce.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        await ws_client.send_json(
            {
                "id": 5,
                "type": "config_entries/ignore_flow",
                "flow_id": result["flow_id"],
                "title": "Test Integration",
            }
        )
        response = await ws_client.receive_json()

        assert response["success"]

    assert len(hass.config_entries.flow.async_progress()) == 0

    entry = hass.config_entries.async_entries("test")[0]
    assert entry.source == "ignore"
    assert entry.unique_id == "mock-unique-id"
    assert entry.title == "Test Integration"


async def test_ignore_flow_nonexisting(hass, hass_ws_client):
    """Test we can ignore a flow."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/ignore_flow",
            "flow_id": "non_existing",
            "title": "Test Integration",
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "not_found"


async def test_get_entries_ws(hass, hass_ws_client, clear_handlers):
    """Test get entries with the websocket api."""
    assert await async_setup_component(hass, "config", {})
    mock_integration(hass, MockModule("comp1"))
    mock_integration(
        hass, MockModule("comp2", partial_manifest={"integration_type": "helper"})
    )
    mock_integration(hass, MockModule("comp3"))
    entry = MockConfigEntry(
        domain="comp1",
        title="Test 1",
        source="bla",
    )
    entry.add_to_hass(hass)
    MockConfigEntry(
        domain="comp2",
        title="Test 2",
        source="bla2",
        state=core_ce.ConfigEntryState.SETUP_ERROR,
        reason="Unsupported API",
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="comp3",
        title="Test 3",
        source="bla3",
        disabled_by=core_ce.ConfigEntryDisabler.USER,
    ).add_to_hass(hass)

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/get",
        }
    )
    response = await ws_client.receive_json()
    assert response["id"] == 5
    assert response["result"] == [
        {
            "disabled_by": None,
            "domain": "comp1",
            "entry_id": ANY,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla",
            "state": "not_loaded",
            "supports_options": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 1",
        },
        {
            "disabled_by": None,
            "domain": "comp2",
            "entry_id": ANY,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": "Unsupported API",
            "source": "bla2",
            "state": "setup_error",
            "supports_options": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 2",
        },
        {
            "disabled_by": "user",
            "domain": "comp3",
            "entry_id": ANY,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla3",
            "state": "not_loaded",
            "supports_options": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 3",
        },
    ]

    await ws_client.send_json(
        {
            "id": 6,
            "type": "config_entries/get",
            "domain": "comp1",
            "type_filter": "integration",
        }
    )
    response = await ws_client.receive_json()
    assert response["id"] == 6
    assert response["result"] == [
        {
            "disabled_by": None,
            "domain": "comp1",
            "entry_id": ANY,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla",
            "state": "not_loaded",
            "supports_options": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 1",
        }
    ]
    # Verify we skip broken integrations

    with patch(
        "homeassistant.components.config.config_entries.async_get_integration",
        side_effect=IntegrationNotFound("any"),
    ):
        await ws_client.send_json(
            {
                "id": 7,
                "type": "config_entries/get",
                "type_filter": "integration",
            }
        )
        response = await ws_client.receive_json()

    assert response["id"] == 7
    assert response["result"] == [
        {
            "disabled_by": None,
            "domain": "comp1",
            "entry_id": ANY,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla",
            "state": "not_loaded",
            "supports_options": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 1",
        },
        {
            "disabled_by": None,
            "domain": "comp2",
            "entry_id": ANY,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": "Unsupported API",
            "source": "bla2",
            "state": "setup_error",
            "supports_options": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 2",
        },
        {
            "disabled_by": "user",
            "domain": "comp3",
            "entry_id": ANY,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla3",
            "state": "not_loaded",
            "supports_options": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 3",
        },
    ]

    # Verify we raise if something really goes wrong

    with patch(
        "homeassistant.components.config.config_entries.async_get_integration",
        side_effect=Exception,
    ):
        await ws_client.send_json(
            {
                "id": 8,
                "type": "config_entries/get",
                "type_filter": "integration",
            }
        )
        response = await ws_client.receive_json()

    assert response["id"] == 8
    assert response["success"] is False
