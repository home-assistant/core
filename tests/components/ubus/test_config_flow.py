"""Tests for the OpenWrt (ubus) config flow."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.device_tracker.const import CONF_CONSIDER_HOME
from homeassistant.components.ubus.config_flow import HUB_TITLE
from homeassistant.components.ubus.const import (
    CONF_DHCP_SOFTWARE,
    DOMAIN,
    SUBENTRY_TYPE_ROUTER,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MAC_PHONE,
    MOCK_CONFIG,
    MOCK_HOST,
    MOCK_HOST_B,
    MOCK_HOST_C,
    MOCK_HOST_CONFIG_B,
    MOCK_HOST_CONFIG_C,
    router_subentry_data,
)

USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "password",
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
}


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_ubus: MagicMock
) -> None:
    """Test the user flow creates the hub entry with a first router subentry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HUB_TITLE
    assert result["data"] == {}
    assert result["subentries"] == [router_subentry_data(MOCK_CONFIG)]


@pytest.mark.parametrize(
    ("ssl", "verify_ssl"),
    [
        pytest.param(False, False, id="http"),
        pytest.param(True, False, id="https"),
        pytest.param(True, True, id="https_verified"),
    ],
)
async def test_user_flow_ssl_options(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    ssl: bool,
    verify_ssl: bool,
) -> None:
    """Test the user flow stores the selected SSL options on the subentry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**USER_INPUT, CONF_SSL: ssl, CONF_VERIFY_SSL: verify_ssl},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry_data = result["subentries"][0]["data"]
    assert subentry_data[CONF_SSL] is ssl
    assert subentry_data[CONF_VERIFY_SSL] is verify_ssl
    mock_ubus.assert_called_once_with(
        f"{'https' if ssl else 'http'}://{MOCK_HOST}/ubus",
        "root",
        "password",
        verify=verify_ssl,
    )


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_ubus: MagicMock
) -> None:
    """Test the user flow recovers after a connection error."""
    mock_ubus.return_value.connect.side_effect = ConnectionError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_ubus.return_value.connect.side_effect = None
    mock_ubus.return_value.connect.return_value = "session-id"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "connect",
    [
        pytest.param(
            {"side_effect": PermissionError("Access denied")}, id="access_denied"
        ),
        pytest.param({"side_effect": None, "return_value": None}, id="no_session"),
    ],
)
async def test_user_flow_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    connect: dict,
) -> None:
    """Test the user flow reports invalid credentials and then recovers."""
    mock_ubus.return_value.connect.configure_mock(**connect)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_ubus.return_value.connect.configure_mock(
        side_effect=None, return_value="session-id"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_second_entry_aborts(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
) -> None:
    """Test a second entry flow is rejected: routers are added as subentries."""
    hub_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subentry_flow_adds_router(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
) -> None:
    """Test the subentry user flow adds a router to the hub."""
    hub_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (hub_entry.entry_id, SUBENTRY_TYPE_ROUTER),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={**USER_INPUT, CONF_HOST: MOCK_HOST_B}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST_B
    assert result["data"] == MOCK_HOST_CONFIG_B
    assert {subentry.unique_id for subentry in hub_entry.subentries.values()} == {
        MOCK_HOST,
        MOCK_HOST_B,
    }


async def test_subentry_flow_existing_host_form_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
) -> None:
    """Test adding a host the hub already has is a form error, not a flow abort."""
    hub_entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (hub_entry.entry_id, SUBENTRY_TYPE_ROUTER),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}
    assert len(hub_entry.subentries) == 1

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={**USER_INPUT, CONF_HOST: MOCK_HOST_B}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST_B
    assert {subentry.unique_id for subentry in hub_entry.subentries.values()} == {
        MOCK_HOST,
        MOCK_HOST_B,
    }


@pytest.mark.parametrize(
    ("connect", "reason"),
    [
        pytest.param(
            {"side_effect": ConnectionError("boom")},
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            {"side_effect": PermissionError("Access denied")},
            "invalid_auth",
            id="access_denied",
        ),
        pytest.param(
            {"side_effect": None, "return_value": None},
            "invalid_auth",
            id="no_session",
        ),
    ],
)
async def test_subentry_flow_connect_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
    connect: dict,
    reason: str,
) -> None:
    """Test the subentry flow reports connection failures as form errors."""
    hub_entry.add_to_hass(hass)
    mock_ubus.return_value.connect.configure_mock(**connect)

    result = await hass.config_entries.subentries.async_init(
        (hub_entry.entry_id, SUBENTRY_TYPE_ROUTER),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={**USER_INPUT, CONF_HOST: MOCK_HOST_B}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}
    assert len(hub_entry.subentries) == 1

    def _connect() -> str:
        mock_ubus.return_value.session_id = "session-id"
        return "session-id"

    mock_ubus.return_value.connect.side_effect = _connect
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={**USER_INPUT, CONF_HOST: MOCK_HOST_B}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST_B


async def test_subentry_reconfigure_updates_data_and_reloads(
    hass: HomeAssistant,
    hub_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> None:
    """Test reconfiguring a router updates the subentry and reloads the hub."""
    _mock, _ubus = mock_ubus_by_host
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    subentry = next(iter(hub_entry.subentries.values()))
    assert hub_entry.runtime_data[subentry.subentry_id].host == MOCK_HOST

    result = await hub_entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input=MOCK_HOST_CONFIG_B
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    # The entry update listener reloaded the hub, so the coordinator now
    # polls the new router.
    assert hub_entry.state is ConfigEntryState.LOADED
    updated = hub_entry.subentries[subentry.subentry_id]
    assert updated.data == MOCK_HOST_CONFIG_B
    assert updated.title == MOCK_HOST_B
    assert hub_entry.runtime_data[subentry.subentry_id].host == MOCK_HOST_B


async def test_subentry_reconfigure_host_collision_form_error(
    hass: HomeAssistant,
    two_router_hub: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> None:
    """Test reconfiguring a router to another subentry's host is a form error."""
    _mock, _ubus = mock_ubus_by_host
    two_router_hub.add_to_hass(hass)
    subentry_a = next(
        subentry
        for subentry in two_router_hub.subentries.values()
        if subentry.data[CONF_HOST] == MOCK_HOST
    )

    result = await two_router_hub.start_subentry_reconfigure_flow(
        hass, subentry_a.subentry_id
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input=MOCK_HOST_CONFIG_B
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}
    assert two_router_hub.subentries[subentry_a.subentry_id].data[CONF_HOST] == (
        MOCK_HOST
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input=dict(subentry_a.data)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_import_flow_creates_hub(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_ubus: MagicMock
) -> None:
    """Test importing a YAML configuration without entries creates the hub."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HUB_TITLE
    assert result["data"] == {}
    assert result["subentries"] == [router_subentry_data(MOCK_CONFIG)]


async def test_import_flow_adds_subentry_to_hub(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
) -> None:
    """Test importing with an existing hub adds the router as a subentry."""
    hub_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_HOST_CONFIG_B
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert {subentry.unique_id for subentry in hub_entry.subentries.values()} == {
        MOCK_HOST,
        MOCK_HOST_B,
    }


async def test_import_flow_host_as_subentry_aborts(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    hub_entry: MockConfigEntry,
) -> None:
    """Test importing a host which is already a subentry aborts without adding it."""
    hub_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hub_entry.subentries) == 1


async def test_import_flow_legacy_entries_join_lowest(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
) -> None:
    """Test importing with only legacy entries adds the subentry to the lowest one."""
    legacy_a = MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JZ5YXV8T000000000000000A",
        data=MOCK_CONFIG,
        title=MOCK_HOST,
    )
    legacy_a.add_to_hass(hass)
    legacy_b = MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JZ5YXV8T000000000000000B",
        data=MOCK_HOST_CONFIG_B,
        title=MOCK_HOST_B,
    )
    legacy_b.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_HOST_CONFIG_C
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert {subentry.unique_id for subentry in legacy_a.subentries.values()} == {
        MOCK_HOST_C
    }
    assert not legacy_b.subentries


async def test_import_flow_preserves_dhcp_software(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_ubus: MagicMock
) -> None:
    """Test a non-default DHCP software choice survives the import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**MOCK_CONFIG, CONF_DHCP_SOFTWARE: "odhcpd"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["subentries"][0]["data"][CONF_DHCP_SOFTWARE] == "odhcpd"


@pytest.mark.parametrize(
    ("ssl", "verify_ssl"),
    [
        pytest.param(False, False, id="http"),
        pytest.param(True, False, id="https"),
        pytest.param(True, True, id="https_verified"),
    ],
)
async def test_import_flow_preserves_ssl_options(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    ssl: bool,
    verify_ssl: bool,
) -> None:
    """Test the SSL options survive the import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**MOCK_CONFIG, CONF_SSL: ssl, CONF_VERIFY_SSL: verify_ssl},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry_data = result["subentries"][0]["data"]
    assert subentry_data[CONF_SSL] is ssl
    assert subentry_data[CONF_VERIFY_SSL] is verify_ssl
    mock_ubus.assert_called_once_with(
        f"{'https' if ssl else 'http'}://{MOCK_HOST}/ubus",
        "root",
        "password",
        verify=verify_ssl,
    )


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        pytest.param(TypeError, "cannot_connect", id="cannot_connect"),
        pytest.param(PermissionError, "invalid_auth", id="invalid_auth"),
    ],
)
async def test_import_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ubus: MagicMock,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test the import flow aborts when the router can't be logged in to."""
    mock_ubus.return_value.connect.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_options_flow_consider_home(
    hass: HomeAssistant,
    hub_entry: MockConfigEntry,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the options flow applies consider_home in place without a reload.

    A client last seen 200 s ago is not home under the default window,
    home under a raised one, and not home again under a lowered one; an
    unset option keeps the default semantics.
    """
    _mock, ubus = mock_ubus_by_host
    hub_entry.add_to_hass(hass)
    ubus[MOCK_HOST].get_hostapd_clients.return_value = {
        "clients": {MAC_PHONE: {"authorized": True}}
    }
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    subentry_id = next(iter(hub_entry.subentries))
    coordinator = hub_entry.runtime_data[subentry_id]

    # The phone is seen on the first poll, then leaves the router.
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, MAC_PHONE
    )
    assert hass.states.get(entity_id).state == STATE_HOME

    ubus[MOCK_HOST].get_hostapd_clients.return_value = {"clients": {}}
    # After 200 s the stamp is older than the default 180 s window.
    freezer.tick(timedelta(seconds=200))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_NOT_HOME

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CONSIDER_HOME: 300}
    )
    await hass.async_block_till_done()
    # The entry was not reloaded; the stamp is now within the 300 s window.
    assert hub_entry.runtime_data[subentry_id] is coordinator
    assert hass.states.get(entity_id).state == STATE_HOME

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CONSIDER_HOME: 150}
    )
    await hass.async_block_till_done()
    assert hub_entry.runtime_data[subentry_id] is coordinator
    assert hass.states.get(entity_id).state == STATE_NOT_HOME

    # An unset option keeps the default window.
    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert hub_entry.options == {}
    assert hass.states.get(entity_id).state == STATE_NOT_HOME
