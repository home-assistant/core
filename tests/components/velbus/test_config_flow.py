"""Tests for the Velbus config flow."""

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pytest_homeassistant.common import MockConfigEntry
from velbusaio.exceptions import VelbusAuthenticationFailed, VelbusConnectionFailed

from homeassistant.components.velbus.config_flow import format_manager_dsn
from homeassistant.components.velbus.const import CONF_TLS, CONF_VLP_FILE, DOMAIN
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SOURCE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from . import init_integration
from .const import PORT_SERIAL

DISCOVERY_INFO = UsbServiceInfo(
    device=PORT_SERIAL,
    pid="10CF",
    vid="0B1B",
    serial_number="1234",
    description="Velbus VMB1USB",
    manufacturer="Velleman",
)


@pytest.fixture
def mock_process_uploaded_file(
    tmp_path: Path, mock_vlp_file: str
) -> Generator[MagicMock]:
    """Mock upload vlp file."""
    file_id_vlp = str(uuid4())

    @contextmanager
    def _mock_process_uploaded_file(
        hass: HomeAssistant, uploaded_file_id: str
    ) -> Iterator[Path | None]:
        with open(tmp_path / uploaded_file_id, "wb") as vlpfile:
            vlpfile.write(mock_vlp_file)
        yield tmp_path / uploaded_file_id

    with (
        patch(
            "homeassistant.components.velbus.config_flow.process_uploaded_file",
            side_effect=_mock_process_uploaded_file,
        ) as mock_upload,
        patch(
            "shutil.move",
        ),
    ):
        mock_upload.file_id = {
            CONF_VLP_FILE: file_id_vlp,
        }
        yield mock_upload


@pytest.fixture(autouse=True)
def override_async_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with (
        patch(
            "homeassistant.components.velbus.async_setup_entry", return_value=None
        ) as mock,
    ):
        yield mock


@pytest.fixture(name="controller_connection_failed")
def mock_controller_connection_failed():
    """Mock the velbus controller with an assert."""
    with patch("velbusaio.controller.Velbus", side_effect=VelbusConnectionFailed()):
        yield


@pytest.mark.parametrize(
    ("host", "port", "expected_dsn"),
    [
        ("127.0.0.1", 4201, "manager://127.0.0.1:4201"),
        ("2001:db8::1", 4201, "manager://[2001:db8::1]:4201"),
        ("[2001:db8::1]", 4201, "manager://[2001:db8::1]:4201"),
        ("manager", 4201, "manager://manager:4201"),
        ("velbus.local", 4201, "manager://velbus.local:4201"),
    ],
)
def test_format_manager_dsn(host: str, port: int, expected_dsn: str) -> None:
    """Test manager DSN formatting including IPv6 bracketing."""
    assert format_manager_dsn(host, port) == expected_dsn


@pytest.mark.usefixtures("controller")
async def test_user_manager_success(hass: HomeAssistant) -> None:
    """Test user Velbus Manager config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "manager"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result.get("step_id") == "manager"
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 4201,
            CONF_ACCESS_TOKEN: "token",
        },
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None
    assert result.get("title") == "Velbus Manager"
    data = result.get("data")
    assert data
    assert data[CONF_PORT] == "manager://127.0.0.1:4201"
    assert data[CONF_ACCESS_TOKEN] == "token"
    assert data[CONF_VLP_FILE] is None


@pytest.mark.usefixtures("controller")
async def test_user_manager_invalid_access_token(hass: HomeAssistant) -> None:
    """Test invalid access token during Manager setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "manager"},
    )
    with patch(
        "velbusaio.controller.Velbus",
        side_effect=VelbusAuthenticationFailed(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"),
            {
                CONF_HOST: "127.0.0.1",
                CONF_PORT: 4201,
                CONF_ACCESS_TOKEN: "bad-token",
            },
        )
    assert result.get("errors") == {CONF_ACCESS_TOKEN: "invalid_access_token"}

    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 4201,
            CONF_ACCESS_TOKEN: "good-token",
        },
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("controller_connection_failed")
async def test_user_manager_connect_failure(hass: HomeAssistant) -> None:
    """Test Velbus Manager connection failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "manager"},
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {CONF_HOST: "127.0.0.1", CONF_PORT: 4201},
    )
    assert result.get("errors") == {CONF_HOST: "cannot_connect"}

    with patch("velbusaio.controller.Velbus", return_value=AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"),
            {CONF_HOST: "127.0.0.1", CONF_PORT: 4201},
        )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("controller")
async def test_manager_reconfigure_ipv6(hass: HomeAssistant) -> None:
    """Reconfiguring a manager entry keeps IPv6 hosts bracketed in the DSN."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Velbus Manager",
        data={CONF_PORT: "manager://[2001:db8::1]:4201"},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result.get("step_id") == "manager"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "2001:db8::1", CONF_PORT: 4201},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PORT] == "manager://[2001:db8::1]:4201"


@pytest.mark.usefixtures("controller")
async def test_manager_reconfigure_aborts_on_duplicate(
    hass: HomeAssistant,
) -> None:
    """Reconfiguring a manager entry to an existing DSN aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        title="Velbus Manager A",
        data={CONF_PORT: "manager://127.0.0.1:4201"},
    ).add_to_hass(hass)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        title="Velbus Manager B",
        data={CONF_PORT: "manager://192.168.0.2:4201"},
    )
    entry_b.add_to_hass(hass)

    result = await entry_b.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_PORT: 4201},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("controller")
async def test_reauth_manager(hass: HomeAssistant) -> None:
    """Update a Velbus Manager access token through the reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Velbus Manager",
        data={
            CONF_PORT: "manager://127.0.0.1:4201",
            CONF_ACCESS_TOKEN: "old-token",
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCESS_TOKEN: "new-token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_ACCESS_TOKEN] == "new-token"


@pytest.mark.usefixtures("controller")
@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param({CONF_ACCESS_TOKEN: ""}, id="empty_token"),
        pytest.param({}, id="omitted_token"),
    ],
)
async def test_reauth_manager_clears_access_token(
    hass: HomeAssistant,
    user_input: dict[str, str],
) -> None:
    """Reauth can remove a stored Manager token while keeping connection data."""
    manager_dsn = "manager://127.0.0.1:4201"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Velbus Manager",
        data={
            CONF_PORT: manager_dsn,
            CONF_ACCESS_TOKEN: "old-token",
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert CONF_ACCESS_TOKEN not in entry.data
    assert entry.data[CONF_PORT] == manager_dsn


@pytest.mark.usefixtures("controller_connection_failed")
async def test_reauth_manager_cannot_connect(hass: HomeAssistant) -> None:
    """Test reauth reports connection errors on the base field."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Velbus Manager",
        data={
            CONF_PORT: "manager://127.0.0.1:4201",
            CONF_ACCESS_TOKEN: "old-token",
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCESS_TOKEN: "new-token"},
    )
    assert result.get("errors") == {"base": "cannot_connect"}

    with patch("velbusaio.controller.Velbus", return_value=AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ACCESS_TOKEN: "new-token"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_ACCESS_TOKEN] == "new-token"


@pytest.mark.usefixtures("controller")
async def test_reauth_manager_invalid_token_then_success(
    hass: HomeAssistant,
) -> None:
    """Test reauth handles invalid tokens before accepting a valid one."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Velbus Manager",
        data={
            CONF_PORT: "manager://127.0.0.1:4201",
            CONF_ACCESS_TOKEN: "old-token",
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)

    with patch(
        "velbusaio.controller.Velbus",
        side_effect=VelbusAuthenticationFailed(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ACCESS_TOKEN: "bad-token"},
        )
    assert result.get("errors") == {CONF_ACCESS_TOKEN: "invalid_access_token"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCESS_TOKEN: "good-token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_ACCESS_TOKEN] == "good-token"


@pytest.mark.usefixtures("controller")
async def test_manager_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfigure routes manager entries to the manager step."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Velbus Manager",
        data={CONF_PORT: "manager://127.0.0.1:4201"},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result.get("step_id") == "manager"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_PORT: 4201},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("controller")
@pytest.mark.parametrize(
    ("inputParams", "expected"),
    [
        (
            {
                CONF_TLS: True,
                CONF_PASSWORD: "password",
            },
            "tls://password@velbus:6000",
        ),
        (
            {
                CONF_TLS: True,
                CONF_PASSWORD: "",
            },
            "tls://velbus:6000",
        ),
        ({CONF_TLS: True}, "tls://velbus:6000"),
        ({CONF_TLS: False}, "velbus:6000"),
    ],
)
async def test_user_network_succes(
    hass: HomeAssistant, inputParams: str, expected: str
) -> None:
    """Test user network config."""
    # inttial menu show
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result
    assert result.get("flow_id")
    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "user"
    assert result.get("menu_options") == ["network", "manager", "usbselect"]
    # select the network option
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "network"},
    )
    assert result["type"] is FlowResultType.FORM
    # fill in the network form
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {
            CONF_HOST: "velbus",
            CONF_PORT: 6000,
            **inputParams,
        },
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "vlp"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result
    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    data = result.get("data")
    assert data
    assert data[CONF_PORT] == expected


@pytest.mark.usefixtures("controller_connection_failed")
async def test_user_network_connect_failure(
    hass: HomeAssistant,
) -> None:
    """Test user network config."""
    # inttial menu show
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result
    assert result.get("flow_id")
    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "user"
    assert result.get("menu_options") == ["network", "manager", "usbselect"]
    # select the network option
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "network"},
    )
    assert result["type"] is FlowResultType.FORM
    # fill in the network form
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {
            CONF_HOST: "velbus",
            CONF_PORT: 6000,
            CONF_TLS: True,
            CONF_PASSWORD: "password",
        },
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"host": "cannot_connect"}

    with patch("velbusaio.controller.Velbus", return_value=AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"),
            {
                CONF_HOST: "velbus",
                CONF_PORT: 6000,
                CONF_TLS: True,
                CONF_PASSWORD: "password",
            },
        )
    assert result.get("step_id") == "vlp"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("controller_connection_failed")
async def test_user_usb_connect_failure(hass: HomeAssistant) -> None:
    """Test user usb step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "usbselect"},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PORT: PORT_SERIAL,
        },
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"port": "cannot_connect"}

    with patch("velbusaio.controller.Velbus", return_value=AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PORT: PORT_SERIAL,
            },
        )
    assert result.get("step_id") == "vlp"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("controller")
async def test_user_usb_success(hass: HomeAssistant) -> None:
    """Test user usb step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "usbselect"},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PORT: PORT_SERIAL,
        },
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "vlp"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result
    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Velbus USB"
    data = result.get("data")
    assert data
    assert data[CONF_PORT] == PORT_SERIAL


@pytest.mark.usefixtures("controller")
async def test_vlp_step_no_modules(
    hass: HomeAssistant,
    mock_process_uploaded_file: MagicMock,
) -> None:
    """Test VLP step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "network"},
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {
            CONF_TLS: False,
            CONF_HOST: "192.168.88.9",
            CONF_PORT: 27015,
            CONF_PASSWORD: "",
        },
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "vlp"

    with (
        patch(
            "homeassistant.components.velbus.async_setup_entry",
            return_value=None,
        ),
        patch(
            "velbusaio.vlp_reader.VlpFile.read",
            AsyncMock(return_value=True),
        ),
        patch(
            "velbusaio.vlp_reader.VlpFile.get",
            return_value=[],
        ),
    ):
        file_id = mock_process_uploaded_file.file_id
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"),
            {CONF_VLP_FILE: file_id[CONF_VLP_FILE]},
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {CONF_VLP_FILE: "no_modules"}

    with (
        patch("velbusaio.vlp_reader.VlpFile.read", AsyncMock(return_value=True)),
        patch("velbusaio.vlp_reader.VlpFile.get", return_value=[1, 2, 3, 4]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"),
            {CONF_VLP_FILE: file_id[CONF_VLP_FILE]},
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("controller")
async def test_vlp_step_success(
    hass: HomeAssistant,
    mock_process_uploaded_file: MagicMock,
) -> None:
    """Test VLP step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "network"},
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {
            CONF_TLS: False,
            CONF_HOST: "192.168.88.9",
            CONF_PORT: 27015,
            CONF_PASSWORD: "",
        },
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "vlp"

    with (
        patch(
            "homeassistant.components.velbus.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
        patch(
            "velbusaio.vlp_reader.VlpFile.read",
            AsyncMock(return_value=True),
        ),
        patch(
            "velbusaio.vlp_reader.VlpFile.get",
            return_value=[1, 2, 3, 4],
        ),
    ):
        file_id = mock_process_uploaded_file.file_id
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"),
            {CONF_VLP_FILE: file_id[CONF_VLP_FILE]},
        )
        await hass.async_block_till_done()

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("controller")
async def test_reconfigure_step(
    hass: HomeAssistant,
    mock_process_uploaded_file: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Testcase for the reconfigure step."""
    await init_integration(hass, config_entry)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "network"

    # Submit the network step with the same host/port
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {
            CONF_TLS: False,
            CONF_HOST: "127.0.1.0.1",
            CONF_PORT: 3788,
            CONF_PASSWORD: "",
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "vlp"

    with (
        patch(
            "velbusaio.vlp_reader.VlpFile.read",
            AsyncMock(return_value=True),
        ),
        patch(
            "velbusaio.vlp_reader.VlpFile.get",
            return_value=[1, 2, 3, 4],
        ),
    ):
        file_id = mock_process_uploaded_file.file_id
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"),
            {CONF_VLP_FILE: file_id[CONF_VLP_FILE]},
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("controller")
async def test_reconfigure_step_change_host_port(
    hass: HomeAssistant,
    mock_process_uploaded_file: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Testcase for the reconfigure step changing host and port."""
    await init_integration(hass, config_entry)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "network"

    # Submit the network step with a new host/port
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {
            CONF_TLS: False,
            CONF_HOST: "192.168.0.3",
            CONF_PORT: 3788,
            CONF_PASSWORD: "",
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "vlp"

    with (
        patch(
            "velbusaio.vlp_reader.VlpFile.read",
            AsyncMock(return_value=True),
        ),
        patch(
            "velbusaio.vlp_reader.VlpFile.get",
            return_value=[1, 2, 3, 4],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"),
            {},
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_PORT] == "192.168.0.3:3788"


@pytest.mark.usefixtures("controller")
async def test_reconfigure_step_password_preserved(
    hass: HomeAssistant,
    mock_process_uploaded_file: MagicMock,
) -> None:
    """Test that an existing password is pre-filled and preserved during reconfigure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: "tls://secret@192.168.0.1:27015"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "network"
    # Verify the password is pre-filled in the suggested values
    assert result["data_schema"](
        {
            CONF_TLS: True,
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 27015,
            CONF_PASSWORD: "secret",
        }
    )

    # Submit without changing the password
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {
            CONF_TLS: True,
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 27015,
            CONF_PASSWORD: "secret",
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "vlp"

    with (
        patch("velbusaio.vlp_reader.VlpFile.read", AsyncMock(return_value=True)),
        patch("velbusaio.vlp_reader.VlpFile.get", return_value=[1, 2, 3, 4]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"),
            {},
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PORT] == "tls://secret@192.168.0.1:27015"


@pytest.mark.usefixtures("controller")
async def test_network_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if Velbus is already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: "127.0.0.1:3788"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "network"},
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {
            CONF_TLS: False,
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 3788,
            CONF_PASSWORD: "",
        },
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("controller")
async def test_flow_usb(hass: HomeAssistant) -> None:
    """Test usb discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USB},
        data=DISCOVERY_INFO,
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result
    assert result["result"].unique_id == "1234"
    assert result.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("controller")
async def test_flow_usb_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if Velbus USB discovbery aborts in case it is already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: PORT_SERIAL},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "usbselect"},
    )
    assert result
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PORT: PORT_SERIAL,
        },
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("controller_connection_failed")
async def test_flow_usb_failed(hass: HomeAssistant) -> None:
    """Test usb discovery flow with a failed velbus test."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USB},
        data=DISCOVERY_INFO,
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"
