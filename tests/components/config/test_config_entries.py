"""Test config entries API."""

from collections import OrderedDict
from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import ANY, AsyncMock, patch

from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant import config_entries as core_ce, data_entry_flow, loader
from homeassistant.components.config import config_entries
from homeassistant.config_entries import HANDLERS, ConfigFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_flow, config_validation as cv
from homeassistant.helpers.discovery_flow import DiscoveryKey
from homeassistant.loader import IntegrationNotFound
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockUser,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture
def clear_handlers() -> Generator[None]:
    """Clear config entry handlers."""
    with patch.dict(HANDLERS, clear=True):
        yield


@pytest.fixture(autouse=True)
def mock_test_component(hass: HomeAssistant) -> None:
    """Ensure a component called 'test' exists."""
    mock_integration(hass, MockModule("test"))


@pytest.fixture
async def client(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> TestClient:
    """Fixture that can interact with the config manager API."""
    await async_setup_component(hass, "http", {})
    config_entries.async_setup(hass)
    return await hass_client()


@pytest.fixture
def mock_flow() -> Generator[None]:
    """Mock a config flow."""

    class Comp1ConfigFlow(ConfigFlow):
        """Config flow with options flow."""

        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            """Get options flow."""

    with mock_config_flow("comp1", Comp1ConfigFlow):
        yield


@pytest.mark.usefixtures("freezer")
@pytest.mark.usefixtures("clear_handlers", "mock_flow")
async def test_get_entries(hass: HomeAssistant, client: TestClient) -> None:
    """Test get entries."""
    mock_integration(hass, MockModule("comp1"))
    mock_integration(
        hass, MockModule("comp2", partial_manifest={"integration_type": "helper"})
    )
    mock_integration(
        hass, MockModule("comp3", partial_manifest={"integration_type": "hub"})
    )
    mock_integration(
        hass, MockModule("comp4", partial_manifest={"integration_type": "device"})
    )
    mock_integration(
        hass, MockModule("comp5", partial_manifest={"integration_type": "service"})
    )

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
    MockConfigEntry(
        domain="comp4",
        title="Test 4",
        source="bla4",
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="comp5",
        title="Test 5",
        source="bla5",
    ).add_to_hass(hass)

    resp = await client.get("/api/config/config_entries/entry")
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    for entry in data:
        entry.pop("entry_id")
    timestamp = utcnow().timestamp()
    assert data == [
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp1",
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla",
            "state": core_ce.ConfigEntryState.NOT_LOADED.value,
            "supported_subentry_flows": {},
            "supports_options": True,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": True,
            "title": "Test 1",
        },
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp2",
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": "Unsupported API",
            "source": "bla2",
            "state": core_ce.ConfigEntryState.SETUP_ERROR.value,
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 2",
        },
        {
            "created_at": timestamp,
            "disabled_by": core_ce.ConfigEntryDisabler.USER,
            "domain": "comp3",
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla3",
            "state": core_ce.ConfigEntryState.NOT_LOADED.value,
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 3",
        },
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp4",
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla4",
            "state": core_ce.ConfigEntryState.NOT_LOADED.value,
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 4",
        },
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp5",
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla5",
            "state": core_ce.ConfigEntryState.NOT_LOADED.value,
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 5",
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

    resp = await client.get("/api/config/config_entries/entry?type=hub")
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert len(data) == 2
    assert data[0]["domain"] == "comp1"
    assert data[1]["domain"] == "comp3"

    resp = await client.get("/api/config/config_entries/entry?type=device")
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert len(data) == 1
    assert data[0]["domain"] == "comp4"

    resp = await client.get("/api/config/config_entries/entry?type=service")
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert len(data) == 1
    assert data[0]["domain"] == "comp5"


async def test_remove_entry(hass: HomeAssistant, client: TestClient) -> None:
    """Test removing an entry via the API."""
    entry = MockConfigEntry(domain="test", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    resp = await client.delete(f"/api/config/config_entries/entry/{entry.entry_id}")
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data == {"require_restart": True}
    assert len(hass.config_entries.async_entries()) == 0


async def test_reload_entry(hass: HomeAssistant, client: TestClient) -> None:
    """Test reloading an entry via the API."""
    entry = MockConfigEntry(domain="test", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    hass.config.components.add("test")
    resp = await client.post(
        f"/api/config/config_entries/entry/{entry.entry_id}/reload"
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data == {"require_restart": True}
    assert len(hass.config_entries.async_entries()) == 1


async def test_reload_invalid_entry(hass: HomeAssistant, client: TestClient) -> None:
    """Test reloading an invalid entry via the API."""
    resp = await client.post("/api/config/config_entries/entry/invalid/reload")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_remove_entry_unauth(
    hass: HomeAssistant, client: TestClient, hass_admin_user: MockUser
) -> None:
    """Test removing an entry via the API."""
    hass_admin_user.groups = []
    entry = MockConfigEntry(domain="demo", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    resp = await client.delete(f"/api/config/config_entries/entry/{entry.entry_id}")
    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert len(hass.config_entries.async_entries()) == 1


async def test_reload_entry_unauth(
    hass: HomeAssistant, client: TestClient, hass_admin_user: MockUser
) -> None:
    """Test reloading an entry via the API."""
    hass_admin_user.groups = []
    entry = MockConfigEntry(domain="demo", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    resp = await client.post(
        f"/api/config/config_entries/entry/{entry.entry_id}/reload"
    )
    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert len(hass.config_entries.async_entries()) == 1


async def test_reload_entry_in_failed_state(
    hass: HomeAssistant, client: TestClient, hass_admin_user: MockUser
) -> None:
    """Test reloading an entry via the API that has already failed to unload."""
    entry = MockConfigEntry(domain="demo", state=core_ce.ConfigEntryState.FAILED_UNLOAD)
    entry.add_to_hass(hass)
    hass.config.components.add("demo")
    resp = await client.post(
        f"/api/config/config_entries/entry/{entry.entry_id}/reload"
    )
    assert resp.status == HTTPStatus.FORBIDDEN
    assert len(hass.config_entries.async_entries()) == 1


async def test_reload_entry_in_setup_retry(
    hass: HomeAssistant, client: TestClient, hass_admin_user: MockUser
) -> None:
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
    mock_platform(hass, "comp.config_flow", None)
    entry = MockConfigEntry(domain="comp", state=core_ce.ConfigEntryState.SETUP_RETRY)
    entry.supports_unload = True
    entry.add_to_hass(hass)
    hass.config.components.add("comp")

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
    ("type_filter", "result"),
    [
        (None, {"hello", "another", "world"}),
        ("integration", {"hello", "another"}),
        ("helper", {"world"}),
    ],
)
async def test_available_flows(
    hass: HomeAssistant, client: TestClient, type_filter: str | None, result: set[str]
) -> None:
    """Test querying the available flows."""
    with patch.object(
        loader,
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


@pytest.mark.parametrize(
    "ignore_translations",
    ["component.test.config.error.Should be unique."],
)
async def test_initialize_flow(hass: HomeAssistant, client: TestClient) -> None:
    """Test we can initialize a flow."""
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required("username")] = str
            schema[vol.Required("password")] = str

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(schema),
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
        "preview": None,
    }


async def test_initialize_flow_unmet_dependency(
    hass: HomeAssistant, client: TestClient
) -> None:
    """Test unmet dependencies are listed."""
    mock_platform(hass, "test.config_flow", None)

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


async def test_initialize_flow_unauth(
    hass: HomeAssistant, client: TestClient, hass_admin_user: MockUser
) -> None:
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


@pytest.mark.parametrize(
    "ignore_translations",
    ["component.test.config.abort.bla"],
)
async def test_abort(hass: HomeAssistant, client: TestClient) -> None:
    """Test a flow that aborts."""
    mock_platform(hass, "test.config_flow", None)

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


@pytest.mark.usefixtures("enable_custom_integrations", "freezer")
async def test_create_account(hass: HomeAssistant, client: TestClient) -> None:
    """Test a flow that creates an account."""
    mock_platform(hass, "test.config_flow", None)

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

    timestamp = utcnow().timestamp()
    data = await resp.json()
    data.pop("flow_id")
    assert data == {
        "handler": "test",
        "title": "Test Entry",
        "type": "create_entry",
        "version": 1,
        "result": {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "test",
            "entry_id": entries[0].entry_id,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": core_ce.SOURCE_USER,
            "state": core_ce.ConfigEntryState.LOADED.value,
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test Entry",
        },
        "description": None,
        "description_placeholders": None,
        "options": {},
        "minor_version": 1,
        "subentries": [],
    }


@pytest.mark.usefixtures("enable_custom_integrations", "freezer")
async def test_two_step_flow(hass: HomeAssistant, client: TestClient) -> None:
    """Test we can finish a two step flow."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_platform(hass, "test.config_flow", None)

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
            "preview": None,
        }

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            f"/api/config/config_entries/flow/{flow_id}",
            json={"user_title": "user-title"},
        )
        assert resp.status == HTTPStatus.OK

        entries = hass.config_entries.async_entries("test")
        assert len(entries) == 1

        timestamp = utcnow().timestamp()
        data = await resp.json()
        data.pop("flow_id")
        assert data == {
            "handler": "test",
            "type": "create_entry",
            "title": "user-title",
            "version": 1,
            "result": {
                "created_at": timestamp,
                "disabled_by": None,
                "domain": "test",
                "entry_id": entries[0].entry_id,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": timestamp,
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": core_ce.SOURCE_USER,
                "state": core_ce.ConfigEntryState.LOADED.value,
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "user-title",
            },
            "description": None,
            "description_placeholders": None,
            "options": {},
            "minor_version": 1,
            "subentries": [],
        }


async def test_continue_flow_unauth(
    hass: HomeAssistant, client: TestClient, hass_admin_user: MockUser
) -> None:
    """Test we can't finish a two step flow."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_platform(hass, "test.config_flow", None)

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
            "preview": None,
        }

    hass_admin_user.groups = []

    resp = await client.post(
        f"/api/config/config_entries/flow/{flow_id}",
        json={"user_title": "user-title"},
    )
    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_get_progress_index(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test querying for the flows that are in progress."""
    assert await async_setup_component(hass, "config", {})
    mock_platform(hass, "test.config_flow", None)
    ws_client = await hass_ws_client(hass)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 5

        async def async_step_hassio(self, discovery_info):
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


async def test_get_progress_index_unauth(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test we can't get flows that are in progress."""
    assert await async_setup_component(hass, "config", {})
    hass_admin_user.groups = []
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 5, "type": "config_entries/flow/progress"})
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    "ignore_translations",
    ["component.test.config.error.Should be unique."],
)
async def test_get_progress_flow(hass: HomeAssistant, client: TestClient) -> None:
    """Test we can query the API for same result as we get from init a flow."""
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required("username")] = str
            schema[vol.Required("password")] = str

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(schema),
                errors={"username": "Should be unique."},
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    resp2 = await client.get(f"/api/config/config_entries/flow/{data['flow_id']}")

    assert resp2.status == HTTPStatus.OK
    data2 = await resp2.json()

    assert data == data2


@pytest.mark.parametrize(
    "ignore_translations",
    ["component.test.config.error.Should be unique."],
)
async def test_get_progress_flow_unauth(
    hass: HomeAssistant, client: TestClient, hass_admin_user: MockUser
) -> None:
    """Test we can can't query the API for result of flow."""
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required("username")] = str
            schema[vol.Required("password")] = str

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(schema),
                errors={"username": "Should be unique."},
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    hass_admin_user.groups = []

    resp2 = await client.get(f"/api/config/config_entries/flow/{data['flow_id']}")

    assert resp2.status == HTTPStatus.UNAUTHORIZED


async def test_options_flow(hass: HomeAssistant, client: TestClient) -> None:
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
                        data_schema=vol.Schema(schema),
                        description_placeholders={"enabled": "Set to true to be true"},
                    )

                async def async_step_user(self, user_input=None):
                    raise NotImplementedError

            return OptionsFlowHandler()

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
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
        "preview": None,
    }


@pytest.mark.parametrize(
    ("endpoint", "method"),
    [
        ("/api/config/config_entries/options/flow", "post"),
        ("/api/config/config_entries/options/flow/1", "get"),
        ("/api/config/config_entries/options/flow/1", "post"),
    ],
)
async def test_options_flow_unauth(
    hass: HomeAssistant,
    client: TestClient,
    hass_admin_user: MockUser,
    endpoint: str,
    method: str,
) -> None:
    """Test unauthorized on options flow."""

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

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    MockConfigEntry(
        domain="test",
        entry_id="test1",
        source="bla",
    ).add_to_hass(hass)
    entry = hass.config_entries.async_entries()[0]

    hass_admin_user.groups = []

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await getattr(client, method)(endpoint, json={"handler": entry.entry_id})

    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_two_step_options_flow(hass: HomeAssistant, client: TestClient) -> None:
    """Test we can finish a two step options flow."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_platform(hass, "test.config_flow", None)

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
            "preview": None,
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
            "description": None,
            "description_placeholders": None,
        }


async def test_options_flow_with_invalid_data(
    hass: HomeAssistant, client: TestClient
) -> None:
    """Test an options flow with invalid_data."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_platform(hass, "test.config_flow", None)

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
            "preview": None,
        }

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            f"/api/config/config_entries/options/flow/{flow_id}",
            json={"choices": ["valid", "invalid"]},
        )
        assert resp.status == HTTPStatus.BAD_REQUEST
        data = await resp.json()
        assert data == {"errors": {"choices": "invalid is not a valid option"}}


async def test_subentry_flow(hass: HomeAssistant, client) -> None:
    """Test we can start a subentry flow."""

    class TestFlow(core_ce.ConfigFlow):
        class SubentryFlowHandler(core_ce.ConfigSubentryFlow):
            async def async_step_init(self, user_input=None):
                raise NotImplementedError

            async def async_step_user(self, user_input=None):
                schema = OrderedDict()
                schema[vol.Required("enabled")] = bool
                return self.async_show_form(
                    step_id="user",
                    data_schema=schema,
                    description_placeholders={"enabled": "Set to true to be true"},
                )

        @classmethod
        @callback
        def async_get_supported_subentry_flows(
            cls, config_entry: core_ce.ConfigEntry
        ) -> dict[str, type[core_ce.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    MockConfigEntry(
        domain="test",
        entry_id="test1",
        source="bla",
    ).add_to_hass(hass)
    entry = hass.config_entries.async_entries()[0]

    with patch.dict(HANDLERS, {"test": TestFlow}):
        url = "/api/config/config_entries/subentries/flow"
        resp = await client.post(url, json={"handler": [entry.entry_id, "test"]})

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    data.pop("flow_id")
    assert data == {
        "type": "form",
        "handler": ["test1", "test"],
        "step_id": "user",
        "data_schema": [{"name": "enabled", "required": True, "type": "boolean"}],
        "description_placeholders": {"enabled": "Set to true to be true"},
        "errors": None,
        "last_step": None,
        "preview": None,
    }


async def test_subentry_reconfigure_flow(hass: HomeAssistant, client) -> None:
    """Test we can start a subentry reconfigure flow."""

    class TestFlow(core_ce.ConfigFlow):
        class SubentryFlowHandler(core_ce.ConfigSubentryFlow):
            async def async_step_init(self, user_input=None):
                raise NotImplementedError

            async def async_step_user(self, user_input=None):
                raise NotImplementedError

            async def async_step_reconfigure(self, user_input=None):
                schema = OrderedDict()
                schema[vol.Required("enabled")] = bool
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=schema,
                    description_placeholders={"enabled": "Set to true to be true"},
                )

        @classmethod
        @callback
        def async_get_supported_subentry_flows(
            cls, config_entry: core_ce.ConfigEntry
        ) -> dict[str, type[core_ce.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    MockConfigEntry(
        domain="test",
        entry_id="test1",
        source="bla",
        subentries_data=[
            core_ce.ConfigSubentryData(
                data={}, subentry_id="mock_id", title="Title", unique_id=None
            )
        ],
    ).add_to_hass(hass)
    entry = hass.config_entries.async_entries()[0]

    with patch.dict(HANDLERS, {"test": TestFlow}):
        url = "/api/config/config_entries/subentries/flow"
        resp = await client.post(
            url, json={"handler": [entry.entry_id, "test"], "subentry_id": "mock_id"}
        )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    data.pop("flow_id")
    assert data == {
        "type": "form",
        "handler": ["test1", "test"],
        "step_id": "reconfigure",
        "data_schema": [{"name": "enabled", "required": True, "type": "boolean"}],
        "description_placeholders": {"enabled": "Set to true to be true"},
        "errors": None,
        "last_step": None,
        "preview": None,
    }


@pytest.mark.parametrize(
    ("endpoint", "method"),
    [
        ("/api/config/config_entries/subentries/flow", "post"),
        ("/api/config/config_entries/subentries/flow/1", "get"),
        ("/api/config/config_entries/subentries/flow/1", "post"),
    ],
)
async def test_subentry_flow_unauth(
    hass: HomeAssistant, client, hass_admin_user: MockUser, endpoint: str, method: str
) -> None:
    """Test unauthorized on subentry flow."""

    class TestFlow(core_ce.ConfigFlow):
        class SubentryFlowHandler(core_ce.ConfigSubentryFlow):
            async def async_step_init(self, user_input=None):
                schema = OrderedDict()
                schema[vol.Required("enabled")] = bool
                return self.async_show_form(
                    step_id="user",
                    data_schema=schema,
                    description_placeholders={"enabled": "Set to true to be true"},
                )

        @classmethod
        @callback
        def async_get_supported_subentry_flows(
            cls, config_entry: core_ce.ConfigEntry
        ) -> dict[str, type[core_ce.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    MockConfigEntry(
        domain="test",
        entry_id="test1",
        source="bla",
    ).add_to_hass(hass)
    entry = hass.config_entries.async_entries()[0]

    hass_admin_user.groups = []

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await getattr(client, method)(endpoint, json={"handler": entry.entry_id})

    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_two_step_subentry_flow(hass: HomeAssistant, client) -> None:
    """Test we can finish a two step subentry flow."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(core_ce.ConfigFlow):
        class SubentryFlowHandler(core_ce.ConfigSubentryFlow):
            async def async_step_user(self, user_input=None):
                return await self.async_step_finish()

            async def async_step_finish(self, user_input=None):
                if user_input:
                    return self.async_create_entry(
                        title="Mock title", data=user_input, unique_id="test"
                    )

                return self.async_show_form(
                    step_id="finish", data_schema=vol.Schema({"enabled": bool})
                )

        @classmethod
        @callback
        def async_get_supported_subentry_flows(
            cls, config_entry: core_ce.ConfigEntry
        ) -> dict[str, type[core_ce.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    MockConfigEntry(
        domain="test",
        entry_id="test1",
        source="bla",
    ).add_to_hass(hass)
    entry = hass.config_entries.async_entries()[0]

    with patch.dict(HANDLERS, {"test": TestFlow}):
        url = "/api/config/config_entries/subentries/flow"
        resp = await client.post(url, json={"handler": [entry.entry_id, "test"]})

        assert resp.status == HTTPStatus.OK
        data = await resp.json()
        flow_id = data["flow_id"]
        expected_data = {
            "data_schema": [{"name": "enabled", "type": "boolean"}],
            "description_placeholders": None,
            "errors": None,
            "flow_id": flow_id,
            "handler": ["test1", "test"],
            "last_step": None,
            "preview": None,
            "step_id": "finish",
            "type": "form",
        }
        assert data == expected_data

        resp = await client.get(f"/api/config/config_entries/subentries/flow/{flow_id}")
        assert resp.status == HTTPStatus.OK
        data = await resp.json()
        assert data == expected_data

        resp = await client.post(
            f"/api/config/config_entries/subentries/flow/{flow_id}",
            json={"enabled": True},
        )
        assert resp.status == HTTPStatus.OK
        data = await resp.json()
        assert data == {
            "description_placeholders": None,
            "description": None,
            "flow_id": flow_id,
            "handler": ["test1", "test"],
            "title": "Mock title",
            "type": "create_entry",
            "unique_id": "test",
        }


async def test_subentry_flow_with_invalid_data(hass: HomeAssistant, client) -> None:
    """Test a subentry flow with invalid_data."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(core_ce.ConfigFlow):
        class SubentryFlowHandler(core_ce.ConfigSubentryFlow):
            async def async_step_user(self, user_input=None):
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
                return self.async_create_entry(title="Enable disable", data=user_input)

        @classmethod
        @callback
        def async_get_supported_subentry_flows(
            cls, config_entry: core_ce.ConfigEntry
        ) -> dict[str, type[core_ce.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    MockConfigEntry(
        domain="test",
        entry_id="test1",
        source="bla",
    ).add_to_hass(hass)
    entry = hass.config_entries.async_entries()[0]

    with patch.dict(HANDLERS, {"test": TestFlow}):
        url = "/api/config/config_entries/subentries/flow"
        resp = await client.post(url, json={"handler": [entry.entry_id, "test"]})

        assert resp.status == HTTPStatus.OK
        data = await resp.json()
        flow_id = data.pop("flow_id")
        assert data == {
            "type": "form",
            "handler": ["test1", "test"],
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
            "preview": None,
        }

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            f"/api/config/config_entries/subentries/flow/{flow_id}",
            json={"choices": ["valid", "invalid"]},
        )
        assert resp.status == HTTPStatus.BAD_REQUEST
        data = await resp.json()
        assert data == {"errors": {"choices": "invalid is not a valid option"}}


@pytest.mark.usefixtures("freezer")
async def test_get_single(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that we can get a config entry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(domain="test", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)

    assert entry.pref_disable_new_entities is False
    assert entry.pref_disable_polling is False

    await ws_client.send_json_auto_id(
        {
            "type": "config_entries/get_single",
            "entry_id": entry.entry_id,
        }
    )
    response = await ws_client.receive_json()

    timestamp = utcnow().timestamp()
    assert response["success"]
    assert response["result"]["config_entry"] == {
        "created_at": timestamp,
        "disabled_by": None,
        "domain": "test",
        "entry_id": entry.entry_id,
        "error_reason_translation_key": None,
        "error_reason_translation_placeholders": None,
        "modified_at": timestamp,
        "num_subentries": 0,
        "pref_disable_new_entities": False,
        "pref_disable_polling": False,
        "reason": None,
        "source": "user",
        "state": "loaded",
        "supported_subentry_flows": {},
        "supports_options": False,
        "supports_reconfigure": False,
        "supports_remove_device": False,
        "supports_unload": False,
        "title": "Mock Title",
    }

    await ws_client.send_json_auto_id(
        {
            "type": "config_entries/get_single",
            "entry_id": "blah",
        }
    )
    response = await ws_client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "not_found",
        "message": "Config entry not found",
    }


async def test_update_prefrences(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that we can update system options."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(domain="test", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    hass.config.components.add("test")

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


async def test_update_entry(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
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


async def test_update_entry_nonexisting(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
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


async def test_disable_entry(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that we can disable entry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(domain="test", state=core_ce.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    assert entry.disabled_by is None
    hass.config.components.add("test")

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


async def test_disable_entry_nonexisting(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
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


@pytest.mark.parametrize(
    (
        "flow_context",
        "entry_discovery_keys",
    ),
    [
        (
            {},
            {},
        ),
        (
            {"discovery_key": DiscoveryKey(domain="test", key="blah", version=1)},
            {"test": (DiscoveryKey(domain="test", key="blah", version=1),)},
        ),
    ],
)
async def test_ignore_flow(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    flow_context: dict,
    entry_discovery_keys: dict[str, tuple[DiscoveryKey, ...]],
) -> None:
    """Test we can ignore a flow."""
    assert await async_setup_component(hass, "config", {})
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            await self.async_set_unique_id("mock-unique-id")
            return self.async_show_form(step_id="account")

        async def async_step_account(self, user_input=None):
            raise NotImplementedError

    ws_client = await hass_ws_client(hass)

    with patch.dict(HANDLERS, {"test": TestFlow}):
        result = await hass.config_entries.flow.async_init(
            "test", context={"source": core_ce.SOURCE_USER} | flow_context
        )
        assert result["type"] is FlowResultType.FORM

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
    assert entry.data == {}
    assert entry.discovery_keys == entry_discovery_keys


async def test_ignore_flow_nonexisting(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
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


@pytest.mark.usefixtures("clear_handlers", "freezer")
async def test_get_matching_entries_ws(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get entries with the websocket api."""
    assert await async_setup_component(hass, "config", {})
    mock_integration(hass, MockModule("comp1"))
    mock_integration(
        hass, MockModule("comp2", partial_manifest={"integration_type": "helper"})
    )
    mock_integration(
        hass, MockModule("comp3", partial_manifest={"integration_type": "hub"})
    )
    mock_integration(
        hass, MockModule("comp4", partial_manifest={"integration_type": "device"})
    )
    mock_integration(
        hass, MockModule("comp5", partial_manifest={"integration_type": "service"})
    )

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
    MockConfigEntry(
        domain="comp4",
        title="Test 4",
        source="bla4",
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="comp5",
        title="Test 5",
        source="bla5",
    ).add_to_hass(hass)

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id({"type": "config_entries/get"})
    response = await ws_client.receive_json()
    timestamp = utcnow().timestamp()
    assert response["result"] == [
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp1",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 1",
        },
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp2",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": "Unsupported API",
            "source": "bla2",
            "state": "setup_error",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 2",
        },
        {
            "created_at": timestamp,
            "disabled_by": "user",
            "domain": "comp3",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla3",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 3",
        },
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp4",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla4",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 4",
        },
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp5",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla5",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 5",
        },
    ]

    await ws_client.send_json_auto_id(
        {
            "type": "config_entries/get",
            "domain": "comp1",
            "type_filter": "hub",
        }
    )
    response = await ws_client.receive_json()
    assert response["result"] == [
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp1",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 1",
        }
    ]

    await ws_client.send_json_auto_id(
        {
            "type": "config_entries/get",
            "type_filter": ["service", "device"],
        }
    )
    response = await ws_client.receive_json()
    assert response["result"] == [
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp4",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla4",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 4",
        },
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp5",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla5",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 5",
        },
    ]

    await ws_client.send_json_auto_id(
        {
            "type": "config_entries/get",
            "type_filter": "hub",
        }
    )
    response = await ws_client.receive_json()
    assert response["result"] == [
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp1",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 1",
        },
        {
            "created_at": timestamp,
            "disabled_by": "user",
            "domain": "comp3",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla3",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 3",
        },
    ]

    # Verify we skip broken integrations
    with patch(
        "homeassistant.components.config.config_entries.async_get_integrations",
        return_value={"any": IntegrationNotFound("any")},
    ):
        await ws_client.send_json_auto_id(
            {
                "type": "config_entries/get",
                "type_filter": "hub",
            }
        )
        response = await ws_client.receive_json()

    assert response["result"] == [
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp1",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 1",
        },
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp2",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": "Unsupported API",
            "source": "bla2",
            "state": "setup_error",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 2",
        },
        {
            "created_at": timestamp,
            "disabled_by": "user",
            "domain": "comp3",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla3",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 3",
        },
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp4",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla4",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 4",
        },
        {
            "created_at": timestamp,
            "disabled_by": None,
            "domain": "comp5",
            "entry_id": ANY,
            "error_reason_translation_key": None,
            "error_reason_translation_placeholders": None,
            "modified_at": timestamp,
            "num_subentries": 0,
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "reason": None,
            "source": "bla5",
            "state": "not_loaded",
            "supported_subentry_flows": {},
            "supports_options": False,
            "supports_reconfigure": False,
            "supports_remove_device": False,
            "supports_unload": False,
            "title": "Test 5",
        },
    ]

    # Verify we don't send config entries when only helpers are requested
    with patch(
        "homeassistant.components.config.config_entries.async_get_integrations",
        return_value={"any": IntegrationNotFound("any")},
    ):
        await ws_client.send_json_auto_id(
            {
                "type": "config_entries/get",
                "type_filter": ["helper"],
            }
        )
        response = await ws_client.receive_json()

    assert response["result"] == []

    # Verify we raise if something really goes wrong

    with patch(
        "homeassistant.components.config.config_entries.async_get_integrations",
        return_value={"any": Exception()},
    ):
        await ws_client.send_json_auto_id(
            {
                "type": "config_entries/get",
                "type_filter": ["device", "hub", "service"],
            }
        )
        response = await ws_client.receive_json()

    assert response["success"] is False


@pytest.mark.usefixtures("clear_handlers")
async def test_subscribe_entries_ws(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test subscribe entries with the websocket api."""
    assert await async_setup_component(hass, "config", {})
    mock_integration(hass, MockModule("comp1"))
    mock_integration(
        hass, MockModule("comp2", partial_manifest={"integration_type": "helper"})
    )
    mock_integration(
        hass, MockModule("comp3", partial_manifest={"integration_type": "device"})
    )
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
            "type": "config_entries/subscribe",
        }
    )
    response = await ws_client.receive_json()
    assert response["id"] == 5
    assert response["result"] is None
    assert response["success"] is True
    assert response["type"] == "result"
    response = await ws_client.receive_json()
    assert response["id"] == 5
    created = utcnow().timestamp()
    assert response["event"] == [
        {
            "type": None,
            "entry": {
                "created_at": created,
                "disabled_by": None,
                "domain": "comp1",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": created,
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": "bla",
                "state": "not_loaded",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "Test 1",
            },
        },
        {
            "type": None,
            "entry": {
                "created_at": created,
                "disabled_by": None,
                "domain": "comp2",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": created,
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": "Unsupported API",
                "source": "bla2",
                "state": "setup_error",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "Test 2",
            },
        },
        {
            "type": None,
            "entry": {
                "created_at": created,
                "disabled_by": "user",
                "domain": "comp3",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": created,
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": "bla3",
                "state": "not_loaded",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "Test 3",
            },
        },
    ]
    freezer.tick()
    modified = utcnow().timestamp()
    assert hass.config_entries.async_update_entry(entry, title="changed")
    response = await ws_client.receive_json()
    assert response["id"] == 5
    assert response["event"] == [
        {
            "entry": {
                "created_at": created,
                "disabled_by": None,
                "domain": "comp1",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": modified,
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": "bla",
                "state": "not_loaded",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "changed",
            },
            "type": "updated",
        }
    ]
    freezer.tick()
    modified = utcnow().timestamp()
    await hass.config_entries.async_remove(entry.entry_id)
    response = await ws_client.receive_json()
    assert response["id"] == 5
    assert response["event"] == [
        {
            "entry": {
                "created_at": created,
                "disabled_by": None,
                "domain": "comp1",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": modified,
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": "bla",
                "state": "not_loaded",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "changed",
            },
            "type": "removed",
        }
    ]
    freezer.tick()
    await hass.config_entries.async_add(entry)
    response = await ws_client.receive_json()
    assert response["id"] == 5
    assert response["event"] == [
        {
            "entry": {
                "created_at": entry.created_at.timestamp(),
                "disabled_by": None,
                "domain": "comp1",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": entry.modified_at.timestamp(),
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": "bla",
                "state": "not_loaded",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "changed",
            },
            "type": "added",
        }
    ]


@pytest.mark.usefixtures("clear_handlers")
async def test_subscribe_entries_ws_filtered(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test subscribe entries with the websocket api with a type filter."""
    created = utcnow().timestamp()
    assert await async_setup_component(hass, "config", {})
    mock_integration(hass, MockModule("comp1"))
    mock_integration(
        hass, MockModule("comp2", partial_manifest={"integration_type": "helper"})
    )
    mock_integration(
        hass, MockModule("comp3", partial_manifest={"integration_type": "device"})
    )
    mock_integration(
        hass, MockModule("comp4", partial_manifest={"integration_type": "service"})
    )
    entry = MockConfigEntry(
        domain="comp1",
        title="Test 1",
        source="bla",
    )
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(
        domain="comp2",
        title="Test 2",
        source="bla2",
        state=core_ce.ConfigEntryState.SETUP_ERROR,
        reason="Unsupported API",
    )
    entry2.add_to_hass(hass)
    entry3 = MockConfigEntry(
        domain="comp3",
        title="Test 3",
        source="bla3",
        disabled_by=core_ce.ConfigEntryDisabler.USER,
    )
    entry3.add_to_hass(hass)
    entry4 = MockConfigEntry(
        domain="comp4",
        title="Test 4",
        source="bla4",
    )
    entry4.add_to_hass(hass)

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/subscribe",
            "type_filter": ["hub", "device"],
        }
    )
    response = await ws_client.receive_json()
    assert response["id"] == 5
    assert response["result"] is None
    assert response["success"] is True
    assert response["type"] == "result"
    response = await ws_client.receive_json()
    assert response["id"] == 5
    assert response["event"] == [
        {
            "type": None,
            "entry": {
                "created_at": created,
                "disabled_by": None,
                "domain": "comp1",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": created,
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": "bla",
                "state": "not_loaded",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "Test 1",
            },
        },
        {
            "type": None,
            "entry": {
                "created_at": created,
                "disabled_by": "user",
                "domain": "comp3",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": created,
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": "bla3",
                "state": "not_loaded",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "Test 3",
            },
        },
    ]
    freezer.tick()
    modified = utcnow().timestamp()
    assert hass.config_entries.async_update_entry(entry, title="changed")
    assert hass.config_entries.async_update_entry(entry3, title="changed too")
    assert hass.config_entries.async_update_entry(entry4, title="changed but ignored")
    response = await ws_client.receive_json()
    assert response["id"] == 5
    assert response["event"] == [
        {
            "entry": {
                "created_at": created,
                "disabled_by": None,
                "domain": "comp1",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": modified,
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": "bla",
                "state": "not_loaded",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "changed",
            },
            "type": "updated",
        }
    ]
    response = await ws_client.receive_json()
    assert response["id"] == 5
    assert response["event"] == [
        {
            "entry": {
                "created_at": created,
                "disabled_by": "user",
                "domain": "comp3",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": modified,
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": "bla3",
                "state": "not_loaded",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "changed too",
            },
            "type": "updated",
        }
    ]
    freezer.tick()
    modified = utcnow().timestamp()
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.config_entries.async_remove(entry2.entry_id)
    response = await ws_client.receive_json()
    assert response["id"] == 5
    assert response["event"] == [
        {
            "entry": {
                "created_at": created,
                "disabled_by": None,
                "domain": "comp1",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": modified,
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": "bla",
                "state": "not_loaded",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "changed",
            },
            "type": "removed",
        }
    ]
    freezer.tick()
    await hass.config_entries.async_add(entry)
    response = await ws_client.receive_json()
    assert response["id"] == 5
    assert response["event"] == [
        {
            "entry": {
                "created_at": entry.created_at.timestamp(),
                "disabled_by": None,
                "domain": "comp1",
                "entry_id": ANY,
                "error_reason_translation_key": None,
                "error_reason_translation_placeholders": None,
                "modified_at": entry.modified_at.timestamp(),
                "num_subentries": 0,
                "pref_disable_new_entities": False,
                "pref_disable_polling": False,
                "reason": None,
                "source": "bla",
                "state": "not_loaded",
                "supported_subentry_flows": {},
                "supports_options": False,
                "supports_reconfigure": False,
                "supports_remove_device": False,
                "supports_unload": False,
                "title": "changed",
            },
            "type": "added",
        }
    ]


async def test_flow_with_multiple_schema_errors(
    hass: HomeAssistant, client: TestClient
) -> None:
    """Test an config flow with multiple schema errors."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_LATITUDE): cv.latitude,
                        vol.Required(CONF_LONGITUDE): cv.longitude,
                        vol.Required(CONF_RADIUS): vol.All(int, vol.Range(min=5)),
                    }
                ),
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )
        assert resp.status == HTTPStatus.OK
        flow_id = (await resp.json())["flow_id"]

        resp = await client.post(
            f"/api/config/config_entries/flow/{flow_id}",
            json={"latitude": 30000, "longitude": 30000, "radius": 1},
        )
        assert resp.status == HTTPStatus.BAD_REQUEST
        data = await resp.json()
        assert data == {
            "errors": {
                "latitude": "invalid latitude",
                "longitude": "invalid longitude",
                "radius": "value must be at least 5",
            }
        }


async def test_flow_with_multiple_schema_errors_base(
    hass: HomeAssistant, client: TestClient
) -> None:
    """Test an config flow with multiple schema errors where fields are not in the schema."""
    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_LATITUDE): cv.latitude,
                    }
                ),
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow", json={"handler": "test"}
        )
        assert resp.status == HTTPStatus.OK
        flow_id = (await resp.json())["flow_id"]

        resp = await client.post(
            f"/api/config/config_entries/flow/{flow_id}",
            json={"invalid": 30000, "invalid_2": 30000},
        )
        assert resp.status == HTTPStatus.BAD_REQUEST
        data = await resp.json()
        assert data == {
            "errors": {
                "base": [
                    "extra keys not allowed @ data['invalid']",
                    "extra keys not allowed @ data['invalid_2']",
                ],
                "latitude": "required key not provided",
            }
        }


@pytest.mark.parametrize(
    "ignore_translations",
    ["component.test.config.abort.reconfigure_successful"],
)
@pytest.mark.usefixtures("enable_custom_integrations", "freezer")
async def test_supports_reconfigure(
    hass: HomeAssistant,
    client: TestClient,
) -> None:
    """Test a flow that support reconfigure step."""
    mock_platform(hass, "test.config_flow", None)

    mock_integration(
        hass, MockModule("test", async_setup_entry=AsyncMock(return_value=True))
    )

    entry = MockConfigEntry(domain="test", title="Test", entry_id="1")
    entry.add_to_hass(hass)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            return self.async_create_entry(
                title="Test Entry", data={"secret": "account_token"}
            )

        async def async_step_reconfigure(self, user_input=None):
            if user_input is None:
                return self.async_show_form(
                    step_id="reconfigure", data_schema=vol.Schema({})
                )
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                title="Test Entry",
                data={"secret": "account_token"},
            )

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            "/api/config/config_entries/flow",
            json={"handler": "test", "entry_id": "1"},
        )

    assert resp.status == HTTPStatus.OK

    data = await resp.json()
    flow_id = data.pop("flow_id")

    assert data == {
        "type": "form",
        "handler": "test",
        "step_id": "reconfigure",
        "data_schema": [],
        "last_step": None,
        "preview": None,
        "description_placeholders": None,
        "errors": None,
    }

    with patch.dict(HANDLERS, {"test": TestFlow}):
        resp = await client.post(
            f"/api/config/config_entries/flow/{flow_id}",
            json={},
        )
    assert resp.status == HTTPStatus.OK

    entries = hass.config_entries.async_entries("test")
    assert len(entries) == 1

    data = await resp.json()
    data.pop("flow_id")
    assert data == {
        "handler": "test",
        "reason": "reconfigure_successful",
        "type": "abort",
        "description_placeholders": None,
    }


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_does_not_support_reconfigure(
    hass: HomeAssistant, client: TestClient
) -> None:
    """Test a flow that does not support reconfigure step."""
    mock_platform(hass, "test.config_flow", None)

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
            "/api/config/config_entries/flow",
            json={"handler": "test", "entry_id": "1"},
        )

    assert resp.status == HTTPStatus.BAD_REQUEST
    response = await resp.text()
    assert (
        response
        == '{"message":"Handler ConfigEntriesFlowManager doesn\'t support step reconfigure"}'
    )


async def test_list_subentries(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that we can list subentries."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(
        domain="test",
        state=core_ce.ConfigEntryState.LOADED,
        subentries_data=[
            core_ce.ConfigSubentryData(
                data={"test": "test"},
                subentry_id="mock_id",
                title="Mock title",
                unique_id="test",
            )
        ],
    )
    entry.add_to_hass(hass)

    assert entry.pref_disable_new_entities is False
    assert entry.pref_disable_polling is False

    await ws_client.send_json_auto_id(
        {
            "type": "config_entries/subentries/list",
            "entry_id": entry.entry_id,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == [
        {"subentry_id": "mock_id", "title": "Mock title", "unique_id": "test"},
    ]

    # Try listing subentries for an unknown entry
    await ws_client.send_json_auto_id(
        {
            "type": "config_entries/subentries/list",
            "entry_id": "no_such_entry",
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": "not_found",
        "message": "Config entry not found",
    }


async def test_delete_subentry(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that we can delete a subentry."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(
        domain="test",
        state=core_ce.ConfigEntryState.LOADED,
        subentries_data=[
            core_ce.ConfigSubentryData(
                data={"test": "test"}, subentry_id="mock_id", title="Mock title"
            )
        ],
    )
    entry.add_to_hass(hass)

    assert entry.pref_disable_new_entities is False
    assert entry.pref_disable_polling is False

    await ws_client.send_json_auto_id(
        {
            "type": "config_entries/subentries/delete",
            "entry_id": entry.entry_id,
            "subentry_id": "mock_id",
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] is None

    await ws_client.send_json_auto_id(
        {
            "type": "config_entries/subentries/list",
            "entry_id": entry.entry_id,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == []

    # Try deleting the subentry again
    await ws_client.send_json_auto_id(
        {
            "type": "config_entries/subentries/delete",
            "entry_id": entry.entry_id,
            "subentry_id": "mock_id",
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": "not_found",
        "message": "Config subentry not found",
    }

    # Try deleting subentry from an unknown entry
    await ws_client.send_json_auto_id(
        {
            "type": "config_entries/subentries/delete",
            "entry_id": "no_such_entry",
            "subentry_id": "mock_id",
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": "not_found",
        "message": "Config entry not found",
    }
