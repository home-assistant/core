"""Tests for the config flow handlers."""

from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    start_reauth_flow,
)
from pyvisonicalarm.exceptions import Error, NotFoundError, UndefinedBadRequestError

from homeassistant.components.visonic.config_flow import FORM_DEVICE_NO_PANEL
from homeassistant.components.visonic.const import (
    CONF_ARM_CODE_AUTO,
    CONF_ARM_HOME_ENABLED,
    CONF_CLOUD_APP_ID,
    CONF_DOWNLOAD_CODE,
    CONF_ENABLE_REMOTE_ARM,
    CONF_ENABLE_REMOTE_DISARM,
    CONF_INSTANT_ARM_AWAY,
    CONF_INSTANT_ARM_HOME,
    CONF_PANEL_NUMBER,
    CONF_PANEL_SERIAL,
    CONF_USER_CODE_SLOT,
    CONFIG_CONNECTION_REFUSED,
    CONFIG_EMAIL_INVALID,
    CONFIG_SETTINGS_INVALID,
    CONFIG_SETTINGS_MISSING,
    DOMAIN,
    FORM_CLOUD,
    FORM_CONNECTION,
    FORM_DEVICE,
    FORM_ETHERNET,
    FORM_PANEL_ARMING,
    FORM_POWERLINK,
    FORM_SELECT_PANEL,
    FORM_SERIAL,
    VISONIC_UNIQUE_NAME,
)
from homeassistant.components.visonic.exceptions import (
    VisonicAuthException,
    VisonicException,
)
from homeassistant.components.visonic.visonic_types import DeviceType
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import (
    CONF_CODE,
    CONF_DEVICE,
    CONF_EMAIL,
    CONF_EXTERNAL_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.util import dt as dt_util

from .helpers import SetupIntegration

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

BAUD_ENTITY_ID = "select.baud_rate"
CLOUD_INPUT = {
    CONF_EXTERNAL_URL: "cloud.example.com",
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "password",
}
PANEL_INPUT = {CONF_PANEL_SERIAL: "ABCDEF", CONF_CODE: "1234"}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Keep completed flows from connecting to a real panel."""
    with patch(
        "homeassistant.components.visonic.async_setup_entry", return_value=None
    ) as mock:
        yield mock


@pytest.mark.parametrize(
    ("device_type", "connection_data", "connection_step"),
    [
        pytest.param(
            DeviceType.ETHERNET,
            {CONF_HOST: "192.0.2.1", CONF_PORT: "30000"},
            FORM_ETHERNET,
            id="ethernet",
        ),
        pytest.param(
            DeviceType.SERIAL, {CONF_DEVICE: "/dev/ttyUSB0"}, FORM_SERIAL, id="serial"
        ),
        pytest.param(
            DeviceType.SERIAL,
            {CONF_DEVICE: "esphome-hass://esphome/entry-id?port_name=uart"},
            FORM_SERIAL,
            id="esphome-serial-proxy",
        ),
        pytest.param(
            DeviceType.SERIAL,
            {CONF_DEVICE: "socket://192.0.2.1:30000"},
            FORM_SERIAL,
            id="socket-url",
        ),
    ],
)
async def test_user_flow_direct(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_connection_test: AsyncMock,
    device_type: DeviceType,
    connection_data: dict[str, str],
    connection_step: str,
) -> None:
    """Set up each direct connection through the actual form sequence."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == FORM_DEVICE
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: device_type.title(), CONF_PANEL_NUMBER: 2}
    )
    assert result["step_id"] == connection_step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], connection_data
    )
    credentials = {CONF_DOWNLOAD_CODE: "1234", CONF_USER_CODE_SLOT: 2}
    submissions = {
        FORM_POWERLINK: credentials,
        FORM_CONNECTION: {},
        FORM_PANEL_ARMING: {CONF_ARM_HOME_ENABLED: False},
    }
    for step in (FORM_POWERLINK,):
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == step
        assert not result["errors"]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], submissions[step]
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id is None
    assert entry.title == f"{VISONIC_UNIQUE_NAME} - Panel 2 ({device_type.title()})"
    assert (
        entry.data.items()
        >= (
            connection_data
            | credentials
            | {
                CONF_TYPE: device_type,
                CONF_PANEL_NUMBER: 2,
            }
        ).items()
    )
    assert entry.options[CONF_ARM_HOME_ENABLED] is True
    assert entry.options[CONF_ARM_CODE_AUTO] is False
    assert entry.options[CONF_INSTANT_ARM_AWAY] is False
    assert entry.options[CONF_INSTANT_ARM_HOME] is False
    assert CONF_ARM_HOME_ENABLED not in entry.data
    assert CONF_PANEL_NUMBER not in entry.options
    assert not credentials.keys() & entry.options.keys()
    mock_connection_test.assert_awaited_once_with(device_type, connection_data)
    mock_setup_entry.assert_awaited_once_with(hass, entry)


@pytest.mark.parametrize(
    ("server", "normalized_server"),
    [
        pytest.param("cloud.example.com", "cloud.example.com", id="hostname"),
        pytest.param("https://cloud.example.com", "cloud.example.com", id="https-url"),
        pytest.param("https://cloud.example.com/", "cloud.example.com", id="root-path"),
        pytest.param("cloud.example.com/", "cloud.example.com", id="hostname-slash"),
        pytest.param(
            "  HTTPS://Cloud.Example.COM/  ",
            "cloud.example.com",
            id="case-and-whitespace",
        ),
        pytest.param(
            "cloud.example.com:8443", "cloud.example.com:8443", id="hostname-port"
        ),
        pytest.param(
            "https://cloud.example.com:8443/", "cloud.example.com:8443", id="https-port"
        ),
        pytest.param(
            "https://cloud.example.com:443/",
            "cloud.example.com:443",
            id="explicit-default-port",
        ),
    ],
)
async def test_user_flow_cloud(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    server: str,
    normalized_server: str,
) -> None:
    """Normalize cloud addresses before authentication and saving panel settings."""
    cloud_input = CLOUD_INPUT | {CONF_EXTERNAL_URL: server}
    with (
        patch(
            "homeassistant.components.visonic.connection_test.API", autospec=True
        ) as factory,
        patch(
            "homeassistant.components.visonic.config_flow.uuid",
        ) as uuid_module,
    ):
        uuid_module.uuid4.return_value = "test-app-id"
        api = factory.return_value
        api.authenticate_user.side_effect = [False, True]
        api.get_panels.return_value = [{CONF_PANEL_SERIAL: "ABCDEF", "alias": "House"}]
        api.panel_login.return_value = True
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TYPE: DeviceType.CLOUD.title(), CONF_PANEL_NUMBER: 2},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], cloud_input | {CONF_EMAIL: "invalid"}
        )
        assert result["errors"] == {"base": CONFIG_EMAIL_INVALID}
        api.authenticate_user.assert_not_awaited()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], cloud_input
        )
        assert result["errors"] == {"base": "invalid_auth"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], cloud_input
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        assert CONF_CODE not in CLOUD_INPUT
        api.panel_login.assert_not_awaited()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], PANEL_INPUT
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entry = result["result"]
        assert (
            entry.data.items()
            >= (
                CLOUD_INPUT
                | PANEL_INPUT
                | {
                    CONF_EXTERNAL_URL: normalized_server,
                    CONF_PANEL_NUMBER: 2,
                    CONF_CLOUD_APP_ID: "test-app-id",
                }
            ).items()
        )
        assert entry.title == f"{VISONIC_UNIQUE_NAME} - Panel 2 (Visonic Cloud)"
        assert entry.unique_id == "ABCDEF"
        assert CONF_PANEL_NUMBER not in entry.options
        assert CONF_CODE not in entry.options
        assert CONF_SCAN_INTERVAL not in entry.options
        assert CONF_SCAN_INTERVAL not in entry.data
        assert CONF_ARM_CODE_AUTO not in entry.options
        assert CONF_INSTANT_ARM_AWAY not in entry.options
        assert CONF_INSTANT_ARM_HOME not in entry.options
        api.panel_login.assert_awaited_once_with("ABCDEF", "1234")
        api.panel_logout.assert_awaited_once_with()
        assert api.authenticate_user.await_count == 2
        assert [item.args[1] for item in factory.call_args_list] == [
            normalized_server
        ] * 2
    await hass.async_block_till_done()
    mock_setup_entry.assert_awaited_once_with(hass, entry)


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "server",
    [
        pytest.param("http://cloud.example.com", id="http"),
        pytest.param("ftp://cloud.example.com", id="ftp"),
        pytest.param("//cloud.example.com", id="scheme-relative"),
        pytest.param("https://cloud.example.com/rest_api", id="path"),
        pytest.param("https://cloud.example.com//", id="double-slash-path"),
        pytest.param("https://cloud.example.com/%2F", id="encoded-path"),
        pytest.param("https://user:password@cloud.example.com", id="credentials"),
        pytest.param("https://user@cloud.example.com", id="username"),
        pytest.param("https://@cloud.example.com", id="empty-username"),
        pytest.param("https://cloud.example.com?key=value", id="query"),
        pytest.param("https://cloud.example.com?", id="empty-query"),
        pytest.param("https://cloud.example.com#fragment", id="fragment"),
        pytest.param("https://cloud.example.com#", id="empty-fragment"),
        pytest.param("cloud.example.com:invalid", id="invalid-port"),
        pytest.param("cloud.example.com:65536", id="out-of-range-port"),
        pytest.param("bad host.example.com", id="hostname-space"),
        pytest.param("cloud.exa\nmple.com", id="embedded-newline"),
        pytest.param("cloud.exa\tmple.com", id="embedded-tab"),
        pytest.param("cloud..example.com", id="empty-hostname-label"),
        pytest.param(".", id="dot-only"),
        pytest.param("https://", id="missing-hostname"),
        pytest.param("   ", id="whitespace-only"),
    ],
)
async def test_cloud_rejects_invalid_server(
    hass: HomeAssistant, mock_connection_test: AsyncMock, server: str
) -> None:
    """Reject invalid cloud addresses before making any connection attempt."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: DeviceType.CLOUD.title()}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CLOUD_INPUT | {CONF_EXTERNAL_URL: server}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == FORM_CLOUD
    assert result["errors"] == {"base": CONFIG_SETTINGS_INVALID}
    mock_connection_test.assert_not_awaited()
    assert not hass.config_entries.async_entries(DOMAIN)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CLOUD_INPUT
    )
    assert result["step_id"] == FORM_SELECT_PANEL
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], PANEL_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data[CONF_EXTERNAL_URL] == CLOUD_INPUT[CONF_EXTERNAL_URL]


@pytest.mark.usefixtures("mock_connection_test")
async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Reauthenticate through both forms without changing panel identity."""
    data = (
        CLOUD_INPUT
        | PANEL_INPUT
        | {
            CONF_TYPE: DeviceType.CLOUD,
            CONF_PANEL_NUMBER: 2,
            CONF_CLOUD_APP_ID: "existing-app-id",
            CONF_SCAN_INTERVAL: 90,
        }
    )
    entry = MockConfigEntry(
        domain=DOMAIN, data=data, options={CONF_ARM_HOME_ENABLED: False}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == FORM_CLOUD
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT | {CONF_PASSWORD: "new-password"}
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        assert entry.data == data
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], PANEL_INPUT
        )
    assert result["reason"] == "reauth_successful"
    expected_data = dict(data)
    expected_data.pop(CONF_SCAN_INTERVAL)
    assert entry.data == expected_data | {CONF_PASSWORD: "new-password"}
    assert entry.options == {CONF_ARM_HOME_ENABLED: False}
    reload.assert_awaited_once_with(entry.entry_id)
    await hass.async_block_till_done()


async def test_loaded_cloud_reauth_with_unchanged_credentials(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Reload after successful unchanged reauth when an auth failure stopped polling."""
    _, entry = await setup_integration(
        data=CLOUD_INPUT
        | PANEL_INPUT
        | {CONF_TYPE: DeviceType.CLOUD, CONF_CLOUD_APP_ID: "existing-app-id"}
    )
    coordinator = entry.runtime_data.coordinator
    entry.async_on_unload(coordinator.async_add_listener(MagicMock()))
    with (
        patch.object(
            coordinator,
            "create_state_snapshot",
            side_effect=VisonicAuthException("Rejected credentials"),
        ),
        patch.object(entry, "async_start_reauth_if_available") as reauth,
    ):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    assert coordinator._unsub_refresh is None
    reauth.assert_called_once_with(hass)
    original_data = dict(entry.data)
    result = await start_reauth_flow(hass, entry)
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], PANEL_INPUT
        )
        await hass.async_block_till_done()

    assert result["reason"] == "reauth_successful"
    assert entry.data == original_data
    reload.assert_awaited_once_with(entry.entry_id)


@pytest.mark.parametrize(
    ("source", "initial_steps", "reason"),
    [
        pytest.param(SOURCE_REAUTH, [], "reauth_successful", id="reauth"),
        pytest.param(
            SOURCE_RECONFIGURE,
            [(FORM_DEVICE_NO_PANEL, {CONF_TYPE: DeviceType.CLOUD.title()})],
            "reconfigure_successful",
            id="reconfigure",
        ),
    ],
)
@pytest.mark.parametrize(
    "server",
    [
        pytest.param("cloud.example.com", id="hostname"),
        pytest.param("https://cloud.example.com/", id="https-url"),
        pytest.param(" HTTPS://Cloud.Example.COM/ ", id="case-and-whitespace"),
    ],
)
async def test_loaded_cloud_entry_updates(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    source: str,
    initial_steps: list[tuple[str, dict[str, str]]],
    reason: str,
    server: str,
) -> None:
    """Use the loaded entry listener to reload changed cloud credentials once."""
    _, entry = await setup_integration(
        data=CLOUD_INPUT | PANEL_INPUT | {CONF_TYPE: DeviceType.CLOUD}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source, "entry_id": entry.entry_id}, data=entry.data
    )
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        for step, data in (
            *initial_steps,
            (
                FORM_CLOUD,
                CLOUD_INPUT
                | {CONF_PASSWORD: "new-password", CONF_EXTERNAL_URL: server},
            ),
            (FORM_SELECT_PANEL, PANEL_INPUT),
        ):
            assert result["step_id"] == step
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], data
            )
        await hass.async_block_till_done()
    assert result["reason"] == reason
    assert entry.data[CONF_PASSWORD] == "new-password"
    assert entry.data[CONF_EXTERNAL_URL] == CLOUD_INPUT[CONF_EXTERNAL_URL]
    reload.assert_awaited_once_with(entry.entry_id)


@pytest.mark.parametrize(
    ("device_type", "connection_data", "step", "expected_connections", "panel_steps"),
    [
        pytest.param(
            DeviceType.ETHERNET,
            {
                CONF_HOST: "192.0.2.1",
                CONF_PORT: "30000",
            },
            FORM_ETHERNET,
            0,
            [(FORM_POWERLINK, {CONF_USER_CODE_SLOT: 1})],
            id="unchanged",
        ),
        pytest.param(
            DeviceType.ETHERNET,
            {
                CONF_HOST: "192.0.2.2",
                CONF_PORT: "30000",
            },
            FORM_ETHERNET,
            1,
            [(FORM_POWERLINK, {CONF_USER_CODE_SLOT: 1})],
            id="changed-host",
        ),
        pytest.param(
            DeviceType.SERIAL,
            {CONF_DEVICE: "/dev/ttyUSB0"},
            FORM_SERIAL,
            1,
            [(FORM_POWERLINK, {CONF_USER_CODE_SLOT: 1})],
            id="changed-type",
        ),
        pytest.param(
            DeviceType.SERIAL,
            {CONF_DEVICE: "esphome-hass://esphome/entry-id?port_name=uart"},
            FORM_SERIAL,
            1,
            [(FORM_POWERLINK, {CONF_USER_CODE_SLOT: 1})],
            id="esphome-serial-proxy",
        ),
        pytest.param(
            DeviceType.CLOUD,
            {
                CONF_EXTERNAL_URL: "cloud.example.com",
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "password",
            },
            FORM_CLOUD,
            2,
            [(FORM_SELECT_PANEL, PANEL_INPUT)],
            id="cloud",
        ),
    ],
)
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_connection_test: AsyncMock,
    device_type: DeviceType,
    connection_data: dict[str, str],
    step: str,
    expected_connections: int,
    panel_steps: list[tuple[str, dict[str, str | int]]],
) -> None:
    """Reconfigure connections while preserving panel identity and options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="visonic_security_system_panel_2",
        data={
            CONF_TYPE: DeviceType.ETHERNET,
            CONF_PANEL_NUMBER: 2,
            CONF_HOST: "192.0.2.1",
            CONF_PORT: "30000",
        },
        options={CONF_ARM_HOME_ENABLED: False},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == FORM_DEVICE_NO_PANEL
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: device_type.title()}
    )
    assert result["step_id"] == step
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            connection_data,
        )
        for panel_step, panel_data in panel_steps:
            assert result["step_id"] == panel_step
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], panel_data
            )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert (
        entry.data.items()
        >= (connection_data | {CONF_TYPE: device_type, CONF_PANEL_NUMBER: 2}).items()
    )
    assert entry.unique_id == "visonic_security_system_panel_2"
    assert entry.options == {CONF_ARM_HOME_ENABLED: False}
    assert mock_connection_test.await_count == expected_connections
    reload.assert_awaited_once_with(entry.entry_id)
    assert hass.config_entries.async_entries(DOMAIN) == [entry]


@pytest.mark.parametrize(
    ("device_type", "steps", "arm_code_option"),
    [
        pytest.param(
            DeviceType.ETHERNET,
            [FORM_CONNECTION, FORM_PANEL_ARMING],
            True,
            id="ethernet",
        ),
        pytest.param(
            DeviceType.SERIAL, [FORM_CONNECTION, FORM_PANEL_ARMING], True, id="serial"
        ),
        pytest.param(DeviceType.CLOUD, [FORM_PANEL_ARMING], False, id="cloud"),
    ],
)
async def test_options_flow(
    hass: HomeAssistant,
    device_type: DeviceType,
    steps: list[str],
    arm_code_option: bool,
) -> None:
    """Edit behavioral settings without changing connection data or unrelated options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TYPE: device_type, CONF_PANEL_NUMBER: 2},
        options={CONF_ARM_HOME_ENABLED: False, "unrelated_option": "preserved"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    for step in steps:
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == step
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ARM_HOME_ENABLED] is True
    assert entry.options["unrelated_option"] == "preserved"
    assert entry.data == {CONF_TYPE: device_type, CONF_PANEL_NUMBER: 2}
    assert not entry.data.keys() & entry.options.keys()
    assert (CONF_ARM_CODE_AUTO in entry.options) is arm_code_option
    assert (CONF_INSTANT_ARM_AWAY in entry.options) is arm_code_option
    assert (CONF_INSTANT_ARM_HOME in entry.options) is arm_code_option

    result = await hass.config_entries.options.async_init(entry.entry_id)
    for _step in steps[:-1]:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
    assert (
        CONF_ARM_CODE_AUTO in {key.schema for key in result["data_schema"].schema}
    ) is arm_code_option
    assert (
        CONF_INSTANT_ARM_AWAY in {key.schema for key in result["data_schema"].schema}
    ) is arm_code_option
    assert (
        CONF_INSTANT_ARM_HOME in {key.schema for key in result["data_schema"].schema}
    ) is arm_code_option
    field = next(
        key
        for key in result["data_schema"].schema
        if key.schema == CONF_ARM_HOME_ENABLED
    )
    assert field.description["suggested_value"] is True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ARM_HOME_ENABLED: False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ARM_HOME_ENABLED] is False


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({}, id="missing"),
        pytest.param({CONF_TYPE: "invalid"}, id="invalid"),
    ],
)
async def test_options_invalid_connection_type(
    hass: HomeAssistant, data: dict[str, str]
) -> None:
    """An unknown connection type cannot select an options flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_error"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_connection_error_retry(
    hass: HomeAssistant, mock_connection_test: AsyncMock
) -> None:
    """Failed submissions remain suggested and can be corrected without restarting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: DeviceType.ETHERNET.title()},
    )
    data = {
        CONF_HOST: "192.0.2.15",
        CONF_PORT: "1234",
    }
    mock_connection_test.side_effect = [CONFIG_CONNECTION_REFUSED, None]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["errors"] == {"base": CONFIG_CONNECTION_REFUSED}
    field = next(key for key in result["data_schema"].schema if key.schema == CONF_HOST)
    assert field.description["suggested_value"] == "192.0.2.15"
    assert not hass.config_entries.async_entries(DOMAIN)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["step_id"] == FORM_POWERLINK
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USER_CODE_SLOT: 1}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data.items() >= data.items()


async def test_reauth_error(
    hass: HomeAssistant, mock_connection_test: AsyncMock
) -> None:
    """Keep stored data on credential failure and recover through both forms."""
    data = (
        CLOUD_INPUT
        | PANEL_INPUT
        | {
            CONF_TYPE: DeviceType.CLOUD,
            CONF_PANEL_NUMBER: 2,
            CONF_CLOUD_APP_ID: "existing-app-id",
        }
    )
    entry = MockConfigEntry(
        domain=DOMAIN, data=data, options={CONF_ARM_HOME_ENABLED: False}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    mock_connection_test.return_value = CONFIG_CONNECTION_REFUSED
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CLOUD_INPUT | {CONF_PASSWORD: "new-password"}
    )
    assert result["errors"] == {"base": CONFIG_CONNECTION_REFUSED}
    assert entry.data == data
    mock_connection_test.return_value = None
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT | {CONF_PASSWORD: "new-password"}
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], PANEL_INPUT
        )
    assert result["reason"] == "reauth_successful"
    assert entry.data == data | {CONF_PASSWORD: "new-password"}
    assert entry.options == {CONF_ARM_HOME_ENABLED: False}
    reload.assert_awaited_once_with(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("device_type", "connection_data", "step", "panel_steps"),
    [
        pytest.param(
            DeviceType.ETHERNET,
            {
                CONF_HOST: "192.0.2.2",
                CONF_PORT: "30000",
            },
            FORM_ETHERNET,
            [(FORM_POWERLINK, {CONF_USER_CODE_SLOT: 1})],
            id="ethernet",
        ),
        pytest.param(
            DeviceType.SERIAL,
            {CONF_DEVICE: "/dev/ttyUSB1"},
            FORM_SERIAL,
            [(FORM_POWERLINK, {CONF_USER_CODE_SLOT: 1})],
            id="serial",
        ),
        pytest.param(
            DeviceType.CLOUD,
            CLOUD_INPUT,
            FORM_CLOUD,
            [(FORM_SELECT_PANEL, PANEL_INPUT)],
            id="cloud",
        ),
    ],
)
async def test_reconfigure_error_recovery(
    hass: HomeAssistant,
    mock_connection_test: AsyncMock,
    device_type: DeviceType,
    connection_data: dict[str, str],
    step: str,
    panel_steps: list[tuple[str, dict[str, str | int]]],
) -> None:
    """Retry a failed endpoint change without losing identity or existing settings."""
    data = {
        CONF_TYPE: DeviceType.ETHERNET,
        CONF_PANEL_NUMBER: 2,
        CONF_HOST: "192.0.2.1",
        CONF_PORT: "30000",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="visonic_security_system_panel_2",
        data=data,
        options={CONF_ARM_HOME_ENABLED: False},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: device_type.title()}
    )
    outcomes = iter([CONFIG_CONNECTION_REFUSED, None, None])

    async def validate(device_type: DeviceType, data: dict[str, str]) -> str | None:
        return next(outcomes)

    mock_connection_test.side_effect = validate
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], connection_data
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == step
        assert result["errors"] == {"base": CONFIG_CONNECTION_REFUSED}
        assert entry.data == data
        assert entry.options == {CONF_ARM_HOME_ENABLED: False}
        reload.assert_not_awaited()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], connection_data
        )
        for panel_step, panel_data in panel_steps:
            assert result["step_id"] == panel_step
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], panel_data
            )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data.items() >= (connection_data | {CONF_TYPE: device_type}).items()
    assert entry.unique_id == "visonic_security_system_panel_2"
    assert entry.options == {CONF_ARM_HOME_ENABLED: False}
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert mock_connection_test.await_count == 2 + (device_type == DeviceType.CLOUD)
    reload.assert_awaited_once_with(entry.entry_id)


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "interval",
    [pytest.param(5, id="fast"), pytest.param(60, id="slow")],
)
async def test_cloud_polling_interval_not_configurable(
    hass: HomeAssistant, mock_connection_test: AsyncMock, interval: int
) -> None:
    """Reject a removed polling field and allow resubmission without it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: DeviceType.CLOUD.title()}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CLOUD_INPUT
    )
    assert result["step_id"] == FORM_SELECT_PANEL
    with pytest.raises(InvalidData) as exc:
        await hass.config_entries.flow.async_configure(
            result["flow_id"], PANEL_INPUT | {CONF_SCAN_INTERVAL: interval}
        )
    assert exc.value.path == [CONF_SCAN_INTERVAL]
    assert mock_connection_test.await_count == 1
    assert not hass.config_entries.async_entries(DOMAIN)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], PANEL_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "ABCDEF"
    assert CONF_SCAN_INTERVAL not in result["result"].data
    assert result["result"].data[CONF_PANEL_NUMBER] == 0
    assert CONF_PANEL_NUMBER not in result["result"].options
    assert mock_connection_test.await_count == 2
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_connection_test")
async def test_reconfigure_clears_optional_credentials(hass: HomeAssistant) -> None:
    """Clearing a suggested download code removes its saved value."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: DeviceType.SERIAL,
            CONF_PANEL_NUMBER: 2,
            CONF_DEVICE: "/dev/ttyUSB0",
            CONF_DOWNLOAD_CODE: "1234",
            CONF_USER_CODE_SLOT: 2,
        },
        options={CONF_ARM_HOME_ENABLED: False},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: DeviceType.SERIAL.title()}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE: "/dev/ttyUSB0"},
    )
    assert result["step_id"] == FORM_POWERLINK
    field = next(
        key for key in result["data_schema"].schema if key.schema == CONF_DOWNLOAD_CODE
    )
    assert field.description["suggested_value"] == "1234"
    with patch.object(hass.config_entries, "async_reload", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USER_CODE_SLOT: 2}
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert CONF_DOWNLOAD_CODE not in entry.data
    assert entry.data[CONF_USER_CODE_SLOT] == 2
    assert entry.options == {CONF_ARM_HOME_ENABLED: False}


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("device_type", "data", "valid_data", "step", "error", "panel_steps"),
    [
        pytest.param(
            DeviceType.ETHERNET,
            {CONF_HOST: "", CONF_PORT: "1234"},
            {
                CONF_HOST: "192.0.2.1",
                CONF_PORT: "1234",
            },
            FORM_ETHERNET,
            CONFIG_SETTINGS_MISSING,
            [(FORM_POWERLINK, {CONF_USER_CODE_SLOT: 1})],
            id="empty-host",
        ),
        pytest.param(
            DeviceType.SERIAL,
            {CONF_DEVICE: ""},
            {CONF_DEVICE: "/dev/ttyUSB0"},
            FORM_SERIAL,
            CONFIG_SETTINGS_MISSING,
            [(FORM_POWERLINK, {CONF_USER_CODE_SLOT: 1})],
            id="empty-device",
        ),
        pytest.param(
            DeviceType.CLOUD,
            CLOUD_INPUT | {CONF_EXTERNAL_URL: ""},
            CLOUD_INPUT,
            FORM_CLOUD,
            CONFIG_SETTINGS_MISSING,
            [(FORM_SELECT_PANEL, PANEL_INPUT)],
            id="empty-cloud-server",
        ),
        pytest.param(
            DeviceType.CLOUD,
            CLOUD_INPUT | {CONF_EMAIL: ""},
            CLOUD_INPUT,
            FORM_CLOUD,
            CONFIG_SETTINGS_MISSING,
            [(FORM_SELECT_PANEL, PANEL_INPUT)],
            id="empty-email",
        ),
        pytest.param(
            DeviceType.CLOUD,
            CLOUD_INPUT | {CONF_PASSWORD: ""},
            CLOUD_INPUT,
            FORM_CLOUD,
            CONFIG_SETTINGS_MISSING,
            [(FORM_SELECT_PANEL, PANEL_INPUT)],
            id="empty-password",
        ),
        pytest.param(
            DeviceType.CLOUD,
            CLOUD_INPUT | {CONF_EXTERNAL_URL: "invalid"},
            CLOUD_INPUT,
            FORM_CLOUD,
            CONFIG_SETTINGS_INVALID,
            [(FORM_SELECT_PANEL, PANEL_INPUT)],
            id="invalid-cloud-server",
        ),
    ],
)
async def test_invalid_connection_settings(
    hass: HomeAssistant,
    mock_connection_test: AsyncMock,
    device_type: DeviceType,
    data: dict[str, str],
    valid_data: dict[str, str],
    step: str,
    error: str,
    panel_steps: list[tuple[str, dict[str, str | int]]],
) -> None:
    """Correct invalid input and finish the same flow without stale settings."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: device_type.title()}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step
    assert result["errors"] == {"base": error}
    mock_connection_test.assert_not_awaited()
    assert not hass.config_entries.async_entries(DOMAIN)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], valid_data
    )
    for panel_step, panel_data in panel_steps:
        assert result["step_id"] == panel_step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], panel_data
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data.items() >= valid_data.items()
    assert result["result"].unique_id == result["result"].data.get(CONF_PANEL_SERIAL)
    assert mock_connection_test.await_count == 1 + (device_type == DeviceType.CLOUD)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_valid_baud_selector(
    hass: HomeAssistant, mock_connection_test: AsyncMock
) -> None:
    """A compatible baud selector is saved when the connection test succeeds."""
    hass.states.async_set(
        BAUD_ENTITY_ID, "9600", {"options": ["9600", "19200", "38400"]}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: DeviceType.ETHERNET.title()},
    )
    data = {
        CONF_HOST: "192.0.2.1",
        CONF_PORT: "1234",
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["step_id"] == FORM_POWERLINK
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USER_CODE_SLOT: 1}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None
    mock_connection_test.assert_awaited_once_with(DeviceType.ETHERNET, data)


@pytest.mark.parametrize(
    "device_type",
    [
        pytest.param(DeviceType.ETHERNET, id="ethernet"),
        pytest.param(DeviceType.SERIAL, id="serial"),
    ],
)
async def test_reauth_direct_connection(
    hass: HomeAssistant, mock_connection_test: AsyncMock, device_type: DeviceType
) -> None:
    """Reauthentication is limited to cloud entries."""
    data = {CONF_TYPE: device_type, CONF_PANEL_NUMBER: 2}
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_error"
    assert entry.data == data
    mock_connection_test.assert_not_awaited()


async def test_yaml_import_unsupported(hass: HomeAssistant) -> None:
    """YAML import remains explicitly unsupported."""
    with pytest.raises(VisonicException, match="Import not supported") as err:
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={}
        )
    assert err.value.code == 600
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize(
    ("device_type", "existing", "proposed", "step"),
    [
        pytest.param(
            DeviceType.ETHERNET,
            {CONF_HOST: "Panel.Example.Com.", CONF_PORT: 30000},
            {CONF_HOST: "panel.example.com", CONF_PORT: "30000"},
            FORM_ETHERNET,
            id="hostname",
        ),
        pytest.param(
            DeviceType.ETHERNET,
            {CONF_HOST: "2001:db8::1", CONF_PORT: "30000"},
            {CONF_HOST: "[2001:0db8:0:0:0:0:0:1]", CONF_PORT: "30000"},
            FORM_ETHERNET,
            id="ipv6",
        ),
        pytest.param(
            DeviceType.SERIAL,
            {CONF_DEVICE: "/dev/ttyUSB0"},
            {CONF_DEVICE: "/dev/ttyUSB0"},
            FORM_SERIAL,
            id="serial-path",
        ),
        pytest.param(
            DeviceType.SERIAL,
            {CONF_DEVICE: "esphome-hass://esphome/entry-id?port_name=uart"},
            {CONF_DEVICE: "esphome-hass://esphome/entry-id?port_name=uart"},
            FORM_SERIAL,
            id="esphome-serial-proxy",
        ),
    ],
)
@pytest.mark.parametrize(
    "state",
    [
        pytest.param(ConfigEntryState.NOT_LOADED, id="unloaded"),
        pytest.param(ConfigEntryState.LOADED, id="loaded"),
    ],
)
async def test_duplicate_connection(
    hass: HomeAssistant,
    mock_connection_test: AsyncMock,
    device_type: DeviceType,
    existing: dict[str, str | int],
    proposed: dict[str, str],
    step: str,
    state: ConfigEntryState,
) -> None:
    """Duplicate endpoints or cloud serials are rejected regardless of entry state."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=existing | {CONF_TYPE: device_type},
        state=state,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: device_type.title()}
    )
    assert result["step_id"] == step
    result = await hass.config_entries.flow.async_configure(result["flow_id"], proposed)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_connection_test.assert_not_awaited()


async def test_concurrent_direct_connection(
    hass: HomeAssistant, mock_connection_test: AsyncMock
) -> None:
    """A flow awaiting Powerlink settings reserves its already validated endpoint."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    first = await hass.config_entries.flow.async_configure(
        first["flow_id"], {CONF_TYPE: DeviceType.ETHERNET.title()}
    )
    first = await hass.config_entries.flow.async_configure(
        first["flow_id"], {CONF_HOST: "panel.example.com", CONF_PORT: "30000"}
    )
    assert first["step_id"] == FORM_POWERLINK
    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_configure(
        second["flow_id"],
        {CONF_TYPE: DeviceType.ETHERNET.title(), CONF_PANEL_NUMBER: 1},
    )
    second = await hass.config_entries.flow.async_configure(
        second["flow_id"], {CONF_HOST: "PANEL.EXAMPLE.COM.", CONF_PORT: "30000"}
    )
    assert second["reason"] == "already_in_progress"
    assert mock_connection_test.await_count == 1


async def test_duplicate_before_completion(
    hass: HomeAssistant, mock_connection_test: AsyncMock
) -> None:
    """A connection configured while another flow waits cannot be saved twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: DeviceType.ETHERNET.title()}
    )
    data = {CONF_HOST: "192.0.2.1", CONF_PORT: "30000"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["step_id"] == FORM_POWERLINK
    entry = MockConfigEntry(domain=DOMAIN, data=data | {CONF_TYPE: DeviceType.ETHERNET})
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "already_configured"
    assert mock_connection_test.await_count == 1


async def test_reconfigure_duplicate_endpoint(
    hass: HomeAssistant, mock_connection_test: AsyncMock
) -> None:
    """Reconfiguration excludes its own entry and rejects another panel's endpoint."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: DeviceType.ETHERNET,
            CONF_HOST: "192.0.2.1",
            CONF_PORT: "30000",
        },
    )
    other = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: DeviceType.ETHERNET,
            CONF_HOST: "192.0.2.2",
            CONF_PORT: "30000",
        },
    )
    entry.add_to_hass(hass)
    other.add_to_hass(hass)
    saved = dict(entry.data)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: DeviceType.ETHERNET.title()}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.0.2.2",
            CONF_PORT: "30000",
        },
    )
    assert result["reason"] == "already_configured"
    assert entry.data == saved
    mock_connection_test.assert_not_awaited()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_cloud_panel_alias_selection(hass: HomeAssistant) -> None:
    """Authenticate before displaying typed Panel aliases and validate the choice."""
    with patch(
        "homeassistant.components.visonic.connection_test.API", autospec=True
    ) as factory:
        api = factory.return_value
        api.authenticate_user.return_value = True
        api.panel_login.return_value = True
        api.get_panels.return_value = [
            {CONF_PANEL_SERIAL: "ABCDEF", "alias": "Home"},
            {CONF_PANEL_SERIAL: "123456", "alias": "Office"},
        ]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TYPE: DeviceType.CLOUD.title()}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT
        )
        assert result["step_id"] == "select_panel"
        api.authenticate_user.assert_awaited_once_with("user@example.com", "password")
        assert api.mock_calls.index(
            call.authenticate_user("user@example.com", "password")
        ) < api.mock_calls.index(call.get_panels())
        field = next(iter(result["data_schema"].schema.values()))
        assert field.config["options"] == [
            {"value": "ABCDEF", "label": "Home (ABCDEF)"},
            {"value": "123456", "label": "Office (123456)"},
        ]
        api.panel_login.assert_not_awaited()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], PANEL_INPUT | {CONF_PANEL_SERIAL: "123456"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].data[CONF_PANEL_SERIAL] == "123456"
        assert result["result"].unique_id == "123456"
        api.panel_login.assert_awaited_once_with("123456", "1234")
        api.panel_logout.assert_awaited_once_with()
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("panels", "expected_type", "error", "completion_inputs"),
    [
        pytest.param(
            [],
            FlowResultType.FORM,
            {"base": "no_panels"},
            [CLOUD_INPUT, PANEL_INPUT],
            id="empty-account",
        ),
        pytest.param(
            [{CONF_PANEL_SERIAL: "ABCDEF", "alias": "Home"}],
            FlowResultType.FORM,
            None,
            [PANEL_INPUT],
            id="only-panel",
        ),
    ],
)
async def test_cloud_account_panel_count(
    hass: HomeAssistant,
    panels: list[dict[str, str]],
    expected_type: FlowResultType,
    error: dict[str, str] | None,
    completion_inputs: list[dict[str, str | int]],
) -> None:
    """Handle empty and single-panel accounts without asking for an arbitrary index."""
    with patch(
        "homeassistant.components.visonic.connection_test.API", autospec=True
    ) as factory:
        api = factory.return_value
        api.authenticate_user.return_value = True
        api.panel_login.return_value = True
        api.get_panels.return_value = panels
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TYPE: DeviceType.CLOUD.title()}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT
        )
        assert result["type"] is expected_type
        assert result.get("errors") == error
        api.get_panels.return_value = [{CONF_PANEL_SERIAL: "ABCDEF", "alias": "Home"}]
        for user_input in completion_inputs:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "ABCDEF"
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_setup_entry", "mock_connection_test")
async def test_distinct_direct_connection(hass: HomeAssistant) -> None:
    """A different endpoint can be configured without assigning a local panel number."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: DeviceType.ETHERNET,
            CONF_HOST: "192.0.2.1",
            CONF_PORT: "30000",
        },
    )
    existing.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: DeviceType.ETHERNET.title()}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.0.2.2",
            CONF_PORT: "30000",
        },
    )
    assert result["step_id"] == FORM_POWERLINK
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USER_CODE_SLOT: 1}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None
    assert result["result"].data[CONF_PANEL_NUMBER] == 0
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_connection_test")
async def test_reconfigure_preserves_panel_number(hass: HomeAssistant) -> None:
    """Changing connection type retains the configured panel number."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: DeviceType.ETHERNET,
            CONF_PANEL_NUMBER: 2,
            CONF_HOST: "192.0.2.1",
            CONF_PORT: "30000",
        },
    )
    entry.add_to_hass(hass)
    entry_id = entry.entry_id
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: DeviceType.SERIAL.title()}
    )
    with patch.object(hass.config_entries, "async_reload", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "/dev/ttyUSB0"},
        )
        assert result["step_id"] == FORM_POWERLINK
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USER_CODE_SLOT: 1}
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.entry_id == entry_id
    assert entry.unique_id is None
    assert entry.data[CONF_PANEL_NUMBER] == 2
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("saved_serial", "unique_id", "saved_type"),
    [
        pytest.param("ABCDEF", "ABCDEF", DeviceType.CLOUD, id="hardware-unique-id"),
        pytest.param(
            "abcdef",
            "visonic_security_system_panel_2",
            DeviceType.CLOUD,
            id="legacy-unique-id",
        ),
        pytest.param(
            "ABCDEF",
            "visonic_security_system_panel_2",
            DeviceType.ETHERNET,
            id="direct-to-cloud",
        ),
    ],
)
async def test_cloud_reconfigure_preserves_panel_identity(
    hass: HomeAssistant,
    saved_serial: str,
    unique_id: str,
    saved_type: DeviceType,
) -> None:
    """Reject another panel before login, then allow corrected same-panel settings."""
    saved_data = (
        CLOUD_INPUT
        | PANEL_INPUT
        | {
            CONF_TYPE: saved_type,
            CONF_PANEL_NUMBER: 2,
            CONF_PANEL_SERIAL: saved_serial,
            CONF_CLOUD_APP_ID: "saved-app-id",
            CONF_SCAN_INTERVAL: 90,
        }
    )
    saved_options = {
        CONF_ARM_HOME_ENABLED: False,
        CONF_ENABLE_REMOTE_ARM: True,
        CONF_ENABLE_REMOTE_DISARM: False,
        CONF_ARM_CODE_AUTO: True,
        CONF_INSTANT_ARM_HOME: True,
        CONF_INSTANT_ARM_AWAY: True,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data=saved_data,
        options=saved_options,
        title="Original panel",
    )
    entry.add_to_hass(hass)
    entry_id = entry.entry_id
    changed_credentials = CLOUD_INPUT | {
        CONF_EXTERNAL_URL: "new-cloud.example.com",
        CONF_EMAIL: "new-user@example.com",
        CONF_PASSWORD: "new-password",
    }
    with patch(
        "homeassistant.components.visonic.connection_test.API", autospec=True
    ) as factory:
        api = factory.return_value
        api.authenticate_user.return_value = True
        api.panel_login.return_value = True
        api.get_panels.return_value = [
            {CONF_PANEL_SERIAL: "ABCDEF", "alias": "Home"},
            {CONF_PANEL_SERIAL: "123456", "alias": "Office"},
        ]
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TYPE: DeviceType.CLOUD.title()}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], changed_credentials
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        with patch.object(
            hass.config_entries, "async_reload", return_value=True
        ) as reload:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], PANEL_INPUT | {CONF_PANEL_SERIAL: "123456"}
            )
            assert result["type"] is FlowResultType.FORM
            assert result["step_id"] == FORM_SELECT_PANEL
            assert result["errors"] == {"base": "panel_mismatch"}
            assert entry.data == saved_data
            assert entry.unique_id == unique_id
            assert entry.title == "Original panel"
            assert entry.options == saved_options
            api.panel_login.assert_not_awaited()
            reload.assert_not_awaited()

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], PANEL_INPUT
            )
            await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.data.items() >= (changed_credentials | PANEL_INPUT).items()
        assert CONF_SCAN_INTERVAL not in entry.data
        assert entry.unique_id == unique_id
        assert entry.entry_id == entry_id
        assert entry.options == {
            CONF_ARM_HOME_ENABLED: False,
            CONF_ENABLE_REMOTE_ARM: True,
            CONF_ENABLE_REMOTE_DISARM: False,
        }
        api.panel_login.assert_awaited_once_with("ABCDEF", "1234")
        api.panel_logout.assert_awaited_once_with()
        reload.assert_awaited_once_with(entry_id)
        assert hass.config_entries.async_entries(DOMAIN) == [entry]


@pytest.mark.usefixtures("mock_connection_test")
async def test_cancelled_cloud_reconfigure_preserves_options(
    hass: HomeAssistant,
) -> None:
    """Do not remove local arming settings before cloud setup is completed."""
    saved_data = {
        CONF_TYPE: DeviceType.ETHERNET,
        CONF_PANEL_NUMBER: 2,
        CONF_HOST: "192.0.2.1",
        CONF_PORT: "30000",
    }
    saved_options = {
        CONF_ENABLE_REMOTE_ARM: False,
        CONF_ENABLE_REMOTE_DISARM: True,
        CONF_ARM_CODE_AUTO: True,
        CONF_INSTANT_ARM_HOME: True,
        CONF_INSTANT_ARM_AWAY: True,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=saved_data, options=saved_options)
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: DeviceType.CLOUD.title()}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CLOUD_INPUT
    )
    assert result["step_id"] == FORM_SELECT_PANEL
    hass.config_entries.flow.async_abort(result["flow_id"])
    assert entry.data == saved_data
    assert entry.options == saved_options


# The saved panel is absent from the account, so this flow cannot finish.
async def test_cloud_reconfigure_missing_saved_panel(hass: HomeAssistant) -> None:
    """An account missing the original serial cannot replace it with another panel."""
    # pylint: disable=home-assistant-tests-config-flow-error-recovery
    saved_data = CLOUD_INPUT | PANEL_INPUT | {CONF_TYPE: DeviceType.CLOUD}
    entry = MockConfigEntry(domain=DOMAIN, unique_id="ABCDEF", data=saved_data)
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.visonic.connection_test.API", autospec=True
        ) as factory,
        patch.object(hass.config_entries, "async_reload", return_value=True) as reload,
    ):
        api = factory.return_value
        api.authenticate_user.return_value = True
        api.get_panels.return_value = [{CONF_PANEL_SERIAL: "123456", "alias": "Other"}]
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TYPE: DeviceType.CLOUD.title()}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], PANEL_INPUT | {CONF_PANEL_SERIAL: "123456"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "panel_mismatch"}
        api.panel_login.assert_not_awaited()
        reload.assert_not_awaited()
    assert entry.data == saved_data
    assert entry.unique_id == "ABCDEF"
    await hass.async_block_till_done()


async def test_cloud_registered_duplicate(hass: HomeAssistant) -> None:
    """An automatically selected cloud serial is checked against completed entries."""
    existing = MockConfigEntry(
        domain=DOMAIN, data={CONF_TYPE: DeviceType.CLOUD, CONF_PANEL_SERIAL: "abcdef"}
    )
    existing.add_to_hass(hass)
    with patch(
        "homeassistant.components.visonic.connection_test.API", autospec=True
    ) as factory:
        api = factory.return_value
        api.authenticate_user.return_value = True
        api.panel_login.return_value = True
        api.get_panels.return_value = [{CONF_PANEL_SERIAL: "ABCDEF", "alias": "Home"}]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TYPE: DeviceType.CLOUD.title()}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], PANEL_INPUT
        )
        assert result["reason"] == "already_configured"
        api.panel_login.assert_not_awaited()
    assert hass.config_entries.async_entries(DOMAIN) == [existing]


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "device",
    [
        pytest.param(
            "esphome-hass://esphome/entry-id?port_name=uart2", id="different-port"
        ),
        pytest.param(
            "esphome-hass://esphome/other-entry?port_name=uart", id="different-device"
        ),
    ],
)
async def test_distinct_serial_proxies(
    hass: HomeAssistant, mock_connection_test: AsyncMock, device: str
) -> None:
    """Different proxy devices and UARTs can represent separate panels."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: DeviceType.SERIAL,
            CONF_DEVICE: "esphome-hass://esphome/entry-id?port_name=uart",
        },
    )
    existing.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: DeviceType.SERIAL.title()}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: device}
    )
    assert result["step_id"] == FORM_POWERLINK
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USER_CODE_SLOT: 1}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None
    assert result["result"].data[CONF_DEVICE] == device
    mock_connection_test.assert_awaited_once_with(
        DeviceType.SERIAL, {CONF_DEVICE: device}
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_serial_symlink_retained(
    hass: HomeAssistant,
    mock_connection_test: AsyncMock,
    tmp_path: Path,
) -> None:
    """Preserve a stable symlink and reject another path to the same serial device."""
    device = tmp_path / "ttyUSB0"
    device.touch()
    stable = tmp_path / "by-id"
    stable.symlink_to(device)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: DeviceType.SERIAL.title()}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE: str(stable)},
    )
    assert result["step_id"] == FORM_POWERLINK
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USER_CODE_SLOT: 1}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None
    assert result["result"].data[CONF_DEVICE] == str(stable)
    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    duplicate = await hass.config_entries.flow.async_configure(
        duplicate["flow_id"],
        {CONF_TYPE: DeviceType.SERIAL.title(), CONF_PANEL_NUMBER: 1},
    )
    duplicate = await hass.config_entries.flow.async_configure(
        duplicate["flow_id"],
        {CONF_DEVICE: str(device)},
    )
    assert duplicate["reason"] == "already_configured"
    mock_connection_test.assert_awaited_once()
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_selected_cloud_panel_auth_recovery(hass: HomeAssistant) -> None:
    """Correct a rejected user code on the same panel form using the same authenticated API."""
    with patch(
        "homeassistant.components.visonic.connection_test.API", autospec=True
    ) as factory:
        api = factory.return_value
        api.authenticate_user.return_value = True
        api.panel_login.side_effect = [False, True]
        api.get_panels.return_value = [
            {CONF_PANEL_SERIAL: "ABCDEF", "alias": "Home"},
            {CONF_PANEL_SERIAL: "123456", "alias": "Office"},
        ]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TYPE: DeviceType.CLOUD.title()}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["step_id"] == FORM_SELECT_PANEL
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], PANEL_INPUT | PANEL_INPUT | {CONF_PANEL_SERIAL: "123456"}
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        assert result["errors"] == {"base": "invalid_auth"}
        assert not hass.config_entries.async_entries(DOMAIN)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            PANEL_INPUT | {CONF_PANEL_SERIAL: "123456", CONF_CODE: "5678"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].data[CONF_CODE] == "5678"
        assert result["result"].data[CONF_PANEL_SERIAL] == "123456"
        api.panel_login.assert_has_awaits(
            [call("123456", "1234"), call("123456", "5678")]
        )
        api.panel_logout.assert_awaited_once_with()
        api.authenticate_user.assert_awaited_once_with("user@example.com", "password")
        assert factory.call_count == 1
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_single_cloud_panel_requires_settings(hass: HomeAssistant) -> None:
    """A sole panel is preselected, but its code still requires submission."""
    with patch(
        "homeassistant.components.visonic.connection_test.API", autospec=True
    ) as factory:
        api = factory.return_value
        api.authenticate_user.return_value = True
        api.get_panels.return_value = [{CONF_PANEL_SERIAL: "ABCDEF", "alias": "House"}]
        api.panel_login.return_value = True
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TYPE: DeviceType.CLOUD.title(), CONF_PANEL_NUMBER: 1},
        )
        assert {field.schema for field in result["data_schema"].schema} == {
            CONF_EXTERNAL_URL,
            CONF_EMAIL,
            CONF_PASSWORD,
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        fields = {field.schema: field for field in result["data_schema"].schema}
        assert set(fields) == {CONF_PANEL_SERIAL, CONF_CODE}
        assert fields[CONF_PANEL_SERIAL].description["suggested_value"] == "ABCDEF"
        assert not hass.config_entries.async_entries(DOMAIN)
        api.panel_login.assert_not_awaited()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PANEL_SERIAL: "ABCDEF", CONF_CODE: "0001"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "ABCDEF"
        assert result["result"].data[CONF_CODE] == "0001"
        assert CONF_SCAN_INTERVAL not in result["result"].data
        assert result["result"].data[CONF_PANEL_NUMBER] == 1
        assert CONF_PANEL_NUMBER not in result["result"].options
        api.panel_login.assert_awaited_once_with("ABCDEF", "0001")
        assert factory.call_count == 1
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(NotFoundError(), id="not-found"),
        pytest.param(UndefinedBadRequestError("{'error': 10001}"), id="bad-request"),
    ],
)
async def test_cloud_login_survives_logout_endpoint_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    error: Error,
) -> None:
    """Log logout failures without rejecting successful authentication."""
    with patch(
        "homeassistant.components.visonic.connection_test.API", autospec=True
    ) as factory:
        api = factory.return_value
        api.authenticate_user.return_value = True
        api.get_panels.return_value = [
            {CONF_PANEL_SERIAL: "ABCDEF", "alias": "House"},
            {CONF_PANEL_SERIAL: "123456", "alias": "Garage"},
        ]
        api.panel_login.return_value = True
        api.panel_logout.side_effect = error
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TYPE: DeviceType.CLOUD.title()}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], PANEL_INPUT
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        api.panel_login.assert_awaited_once_with("ABCDEF", "1234")
        api.panel_logout.assert_awaited_once_with()
    assert f"({type(error).__name__}): {error}" in caplog.text
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_panel_number_collision_recovery(
    hass: HomeAssistant, mock_connection_test: AsyncMock
) -> None:
    """The naming number is stored in data and cannot collide with another panel's number."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: DeviceType.ETHERNET,
            CONF_HOST: "192.0.2.1",
            CONF_PORT: "30000",
            CONF_PANEL_NUMBER: 1,
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: DeviceType.ETHERNET.title(), CONF_PANEL_NUMBER: 1},
    )
    assert result["step_id"] == FORM_DEVICE
    assert result["errors"] == {"base": "panel_number_in_use"}
    mock_connection_test.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: DeviceType.ETHERNET.title(), CONF_PANEL_NUMBER: 2},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.0.2.2",
            CONF_PORT: "30000",
        },
    )
    assert result["step_id"] == FORM_POWERLINK
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USER_CODE_SLOT: 1}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data[CONF_PANEL_NUMBER] == 2
    assert CONF_PANEL_NUMBER not in result["result"].options
    assert result["result"].title == f"{VISONIC_UNIQUE_NAME} - Panel 2 (Ethernet)"
    assert result["result"].unique_id is None
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_concurrent_panel_number_reservation(
    hass: HomeAssistant, mock_connection_test: AsyncMock
) -> None:
    """Concurrent configurations reserve their naming numbers before network validation."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    first = await hass.config_entries.flow.async_configure(
        first["flow_id"], {CONF_TYPE: DeviceType.ETHERNET.title(), CONF_PANEL_NUMBER: 1}
    )
    assert first["step_id"] == FORM_ETHERNET
    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_configure(
        second["flow_id"], {CONF_TYPE: DeviceType.SERIAL.title(), CONF_PANEL_NUMBER: 1}
    )
    assert second["errors"] == {"base": "panel_number_in_use"}
    second = await hass.config_entries.flow.async_configure(
        second["flow_id"], {CONF_TYPE: DeviceType.SERIAL.title(), CONF_PANEL_NUMBER: 2}
    )
    assert second["step_id"] == FORM_SERIAL
    mock_connection_test.assert_not_awaited()
    second = await hass.config_entries.flow.async_configure(
        second["flow_id"], {CONF_DEVICE: "/dev/ttyUSB0"}
    )
    second = await hass.config_entries.flow.async_configure(
        second["flow_id"], {CONF_USER_CODE_SLOT: 1}
    )
    assert second["type"] is FlowResultType.CREATE_ENTRY
    assert second["result"].unique_id is None
    assert second["result"].data[CONF_PANEL_NUMBER] == 2
    await hass.async_block_till_done()


async def test_reauth_unregistered_panel(hass: HomeAssistant) -> None:
    """Reauthentication cannot silently select a replacement physical panel."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CLOUD_INPUT
        | PANEL_INPUT
        | {CONF_TYPE: DeviceType.CLOUD, CONF_PANEL_NUMBER: 0},
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.visonic.connection_test.API", autospec=True
    ) as factory:
        api = factory.return_value
        api.authenticate_user.return_value = True
        api.get_panels.return_value = [{CONF_PANEL_SERIAL: "123456", "alias": "Other"}]
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT
        )
        assert result["step_id"] == FORM_CLOUD
        assert result["errors"] == {"base": "panel_not_registered"}
        api.panel_login.assert_not_awaited()
        api.get_panels.return_value = [{CONF_PANEL_SERIAL: "ABCDEF", "alias": "Home"}]
        api.panel_login.return_value = True
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CLOUD_INPUT
        )
        with patch.object(hass.config_entries, "async_reload", return_value=True):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], PANEL_INPUT
            )
            await hass.async_block_till_done()
        assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PANEL_SERIAL] == "ABCDEF"


async def test_panel_number_collision_before_completion(
    hass: HomeAssistant, mock_connection_test: AsyncMock
) -> None:
    """A naming-number collision arising while the Powerlink form is open cannot create duplicate IDs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: DeviceType.ETHERNET.title(), CONF_PANEL_NUMBER: 1},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.1", CONF_PORT: "30000"}
    )
    assert result["step_id"] == FORM_POWERLINK
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: DeviceType.ETHERNET,
            CONF_HOST: "192.0.2.2",
            CONF_PORT: "30000",
            CONF_PANEL_NUMBER: 1,
        },
    )
    existing.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [existing]
    mock_connection_test.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_serial_proxy_not_ready_retry(hass: HomeAssistant) -> None:
    """A proxy still loading leaves the serial form available for retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: DeviceType.SERIAL.title()}
    )
    path = "esphome-hass://esphome/entry-id?port_name=uart"
    with patch(
        "homeassistant.components.visonic.connection_test.VisonicClient", autospec=True
    ) as factory:
        probe = factory.return_value.async_test_connection
        probe.side_effect = [ConfigEntryNotReady("ESPHome is not loaded"), 9600]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: path}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == FORM_SERIAL
        assert result["errors"] == {"base": "cannot_connect"}
        assert not hass.config_entries.async_entries(DOMAIN)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: path}
        )
        assert result["step_id"] == FORM_POWERLINK
        assert probe.await_count == 2
        assert factory.call_args.args[0].path == path
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USER_CODE_SLOT: 1}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].data[CONF_DEVICE] == path
