"""Test protocol validation, authenticated cloud selection and cleanup."""

import asyncio
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import aiohttp
import pytest
from pyvisonicalarm.exceptions import (
    ConnectionTimeoutError,
    InternalServerError,
    InvalidUserCodeError,
    NotFoundError,
    UnauthorizedError,
    WrongUsernameOrPasswordError,
)

from homeassistant.components.visonic.connection_test import ConnectionTest
from homeassistant.components.visonic.const import (
    CONF_CLOUD_APP_ID,
    CONF_DEVICE_BAUD,
    CONF_PANEL_SERIAL,
)
from homeassistant.components.visonic.visonic_types import DeviceType
from homeassistant.const import (
    CONF_CODE,
    CONF_DEVICE,
    CONF_EMAIL,
    CONF_EXTERNAL_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
)

MODULE = "homeassistant.components.visonic.connection_test"
CLOUD_DATA = {
    CONF_EXTERNAL_URL: "cloud.example.com",
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "password",
    CONF_CODE: "1234",
    CONF_CLOUD_APP_ID: "app-id",
}


@pytest.fixture
def cloud_api() -> Generator[MagicMock]:
    """Provide successful cloud authentication and panel access."""
    with patch(f"{MODULE}.API", autospec=True) as factory:
        api = factory.return_value
        api.authenticate_user.return_value = True
        api.panel_login.return_value = True
        api.get_panels.return_value = [{CONF_PANEL_SERIAL: "ABCDEF"}]
        yield api


@pytest.mark.parametrize(
    ("serial", "panels", "selected", "choices"),
    [
        pytest.param(
            "", [{CONF_PANEL_SERIAL: "ABCDEF"}], "ABCDEF", ["ABCDEF"], id="only-panel"
        ),
        pytest.param(
            "abcdef",
            [{CONF_PANEL_SERIAL: "ABCDEF"}],
            "ABCDEF",
            ["ABCDEF"],
            id="entered-serial",
        ),
        pytest.param(
            "",
            [{CONF_PANEL_SERIAL: "ABCDEF"}, {CONF_PANEL_SERIAL: "123456"}],
            "",
            ["ABCDEF", "123456"],
            id="multiple-panels",
        ),
    ],
)
async def test_cloud_panel_selection(
    cloud_api: MagicMock,
    serial: str,
    panels: list[dict[str, str]],
    selected: str,
    choices: list[str],
) -> None:
    """Select only authenticated account serials and retain available choices."""
    cloud_api.get_panels.return_value = panels
    tester = ConnectionTest(MagicMock(spec=aiohttp.ClientSession))
    data = CLOUD_DATA | {CONF_PANEL_SERIAL: serial}
    assert await tester.test_connection(DeviceType.CLOUD, data) is None
    assert data[CONF_PANEL_SERIAL] == selected
    assert list(tester.panels) == choices
    cloud_api.authenticate_user.assert_awaited_once_with("user@example.com", "password")


async def test_cloud_login_cleanup(cloud_api: MagicMock) -> None:
    """Validate the selected panel code and release the session slot."""
    tester = ConnectionTest(MagicMock(spec=aiohttp.ClientSession))
    assert await tester.test_connection(DeviceType.CLOUD, dict(CLOUD_DATA)) is None
    cloud_api.panel_login.assert_awaited_once_with("ABCDEF", "1234")
    cloud_api.panel_logout.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("panels", "expected"),
    [
        pytest.param([], "no_panels", id="empty-account"),
        pytest.param([{}], "settings_invalid", id="missing-serial"),
    ],
)
async def test_cloud_discovery_cannot_select_panel(
    cloud_api: MagicMock, panels: list[dict[str, str]], expected: str
) -> None:
    """Reject panel login when account discovery has no usable panel identity."""
    cloud_api.get_panels.return_value = panels
    tester = ConnectionTest(MagicMock(spec=aiohttp.ClientSession))
    assert await tester.test_connection(DeviceType.CLOUD, dict(CLOUD_DATA)) == expected
    cloud_api.panel_login.assert_not_awaited()


async def test_cloud_expired_token_clears_cached_account(cloud_api: MagicMock) -> None:
    """A rejected cached token forces fresh account authentication on retry."""
    tester = ConnectionTest(MagicMock(spec=aiohttp.ClientSession))
    account = {key: value for key, value in CLOUD_DATA.items() if key != CONF_CODE}
    assert await tester.test_connection(DeviceType.CLOUD, account) is None
    cloud_api.panel_login.side_effect = UnauthorizedError()
    assert (
        await tester.test_connection(DeviceType.CLOUD, dict(CLOUD_DATA))
        == "invalid_auth"
    )
    assert tester._cloud_api is None
    cloud_api.panel_login.side_effect = None
    assert await tester.test_connection(DeviceType.CLOUD, dict(CLOUD_DATA)) is None
    assert cloud_api.authenticate_user.await_count == 2


async def test_cloud_multiple_panels_no_login(cloud_api: MagicMock) -> None:
    """Account discovery alone does not log in to an arbitrary panel."""
    cloud_api.get_panels.return_value = [
        {CONF_PANEL_SERIAL: "ABCDEF"},
        {CONF_PANEL_SERIAL: "123456"},
    ]
    tester = ConnectionTest(MagicMock(spec=aiohttp.ClientSession))
    assert await tester.test_connection(DeviceType.CLOUD, dict(CLOUD_DATA)) is None
    cloud_api.panel_login.assert_not_awaited()
    cloud_api.panel_logout.assert_not_awaited()


@pytest.mark.parametrize(
    "panels",
    [
        pytest.param([{CONF_PANEL_SERIAL: "123456"}], id="unregistered-serial"),
    ],
)
async def test_cloud_unregistered_serial(
    cloud_api: MagicMock, panels: list[dict[str, str]]
) -> None:
    """An empty account or an unregistered serial cannot complete configuration."""
    cloud_api.get_panels.return_value = panels
    tester = ConnectionTest(MagicMock(spec=aiohttp.ClientSession))
    assert (
        await tester.test_connection(
            DeviceType.CLOUD, CLOUD_DATA | {CONF_PANEL_SERIAL: "ABCDEF"}
        )
        == "settings_invalid"
    )
    cloud_api.panel_login.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "error", "expected"),
    [
        pytest.param(
            "authenticate_user",
            WrongUsernameOrPasswordError(),
            "invalid_auth",
            id="credentials",
        ),
        pytest.param(
            "panel_login", InvalidUserCodeError(), "invalid_auth", id="panel-code"
        ),
        pytest.param(
            "get_panels",
            ConnectionTimeoutError(),
            "cannot_connect_timeout",
            id="library-timeout",
        ),
        pytest.param(
            "get_panels", TimeoutError(), "cannot_connect_timeout", id="timeout"
        ),
        pytest.param(
            "get_panels",
            aiohttp.ClientConnectionError(),
            "cannot_connect_refused",
            id="network",
        ),
        pytest.param("get_panels", InternalServerError(), "cloud_error", id="server"),
    ],
)
async def test_cloud_error_mapping(
    cloud_api: MagicMock, method: str, error: Exception, expected: str
) -> None:
    """Keep authentication failures distinct from transient failures."""
    getattr(cloud_api, method).side_effect = error
    assert (
        await ConnectionTest(MagicMock(spec=aiohttp.ClientSession)).test_connection(
            DeviceType.CLOUD, dict(CLOUD_DATA)
        )
        == expected
    )
    cloud_api.panel_logout.assert_not_awaited()


@pytest.mark.parametrize(
    "method",
    [
        pytest.param("authenticate_user", id="account"),
        pytest.param("panel_login", id="panel-code"),
    ],
)
async def test_cloud_rejected_auth(cloud_api: MagicMock, method: str) -> None:
    """False authentication results cannot create a config entry."""
    getattr(cloud_api, method).return_value = False
    assert (
        await ConnectionTest(MagicMock(spec=aiohttp.ClientSession)).test_connection(
            DeviceType.CLOUD, dict(CLOUD_DATA)
        )
        == "invalid_auth"
    )


@pytest.mark.parametrize(
    ("device_type", "data", "baud", "expected"),
    [
        pytest.param(
            DeviceType.ETHERNET,
            {CONF_HOST: "192.0.2.1", CONF_PORT: "30000"},
            9600,
            {CONF_HOST: "192.0.2.1", CONF_PORT: "30000"},
            id="tcp",
        ),
        pytest.param(
            DeviceType.SERIAL,
            {CONF_DEVICE: "/dev/ttyUSB0"},
            9600,
            {CONF_DEVICE: "/dev/ttyUSB0", CONF_DEVICE_BAUD: 9600},
            id="serial-default",
        ),
        pytest.param(
            DeviceType.SERIAL,
            {CONF_DEVICE: "/dev/ttyUSB0"},
            38400,
            {CONF_DEVICE: "/dev/ttyUSB0", CONF_DEVICE_BAUD: 38400},
            id="serial-retained-powermaster-baud",
        ),
        pytest.param(
            DeviceType.SERIAL,
            {CONF_DEVICE: "/dev/ttyUSB0", CONF_DEVICE_BAUD: 38400},
            9600,
            {CONF_DEVICE: "/dev/ttyUSB0", CONF_DEVICE_BAUD: 9600},
            id="serial-power-loss-reset",
        ),
    ],
)
async def test_direct_quick_probe(
    device_type: DeviceType,
    data: dict[str, Any],
    baud: int,
    expected: dict[str, Any],
) -> None:
    """Delegate discovery to the library and retain only a verified serial baud."""
    with patch(f"{MODULE}.VisonicClient", autospec=True) as factory:
        client = factory.return_value
        client.async_test_connection.return_value = baud
        initial_baud = int(data.get(CONF_DEVICE_BAUD, 9600))

        assert await ConnectionTest().test_connection(device_type, data) is None

        assert data == expected
        factory.assert_called_once()
        settings = factory.call_args.args[0]
        assert settings.connection_type == device_type.value
        assert settings.baud == initial_baud
        client.async_test_connection.assert_awaited_once_with()
        client.connect.assert_not_called()


@pytest.mark.parametrize("device_type", [DeviceType.SERIAL, DeviceType.ETHERNET])
async def test_direct_probe_failure(device_type: DeviceType) -> None:
    """A failed probe cannot save an unverified baud or complete configuration."""
    with patch(f"{MODULE}.VisonicClient", autospec=True) as factory:
        factory.return_value.async_test_connection.return_value = None
        data = {CONF_DEVICE_BAUD: 38400}

        assert await ConnectionTest().test_connection(device_type, data) == (
            "cannot_connect_timeout"
        )
        assert data == {CONF_DEVICE_BAUD: 38400}


async def test_direct_waits_for_probe() -> None:
    """Validation waits for the library probe and propagates cancellation."""
    pending: asyncio.Future[int | None] = asyncio.get_running_loop().create_future()

    async def probe() -> int | None:
        return await pending

    with patch(f"{MODULE}.VisonicClient", autospec=True) as factory:
        client = factory.return_value
        client.async_test_connection.side_effect = probe
        task = asyncio.create_task(
            ConnectionTest().test_connection(
                DeviceType.SERIAL, {CONF_DEVICE: "/dev/ttyUSB0"}
            )
        )
        await asyncio.sleep(0)
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        client.async_test_connection.assert_awaited_once_with()
        client.connect.assert_not_called()


async def test_cloud_discovery_then_selected_panel_login(cloud_api: MagicMock) -> None:
    """Use the account's existing user token, app ID and REST version for the selected panel."""
    cloud_api.get_panels.return_value = [
        {CONF_PANEL_SERIAL: "111111", "alias": "House"},
        {CONF_PANEL_SERIAL: "222222", "alias": "Garage"},
        {CONF_PANEL_SERIAL: "333333", "alias": "Office"},
        {CONF_PANEL_SERIAL: "444444", "alias": "Workshop"},
    ]
    data = {key: value for key, value in CLOUD_DATA.items() if key != CONF_CODE}
    tester = ConnectionTest(MagicMock(spec=aiohttp.ClientSession))
    assert await tester.test_connection(DeviceType.CLOUD, data) is None
    assert tester.panels["333333"] == "Office (333333)"
    cloud_api.panel_login.assert_not_awaited()
    assert (
        await tester.test_connection(
            DeviceType.CLOUD, data | {CONF_PANEL_SERIAL: "333333", CONF_CODE: "0001"}
        )
        is None
    )
    cloud_api.authenticate_user.assert_awaited_once_with("user@example.com", "password")
    cloud_api.set_rest_version.assert_awaited_once_with()
    cloud_api.get_panels.assert_awaited_once_with()
    cloud_api.panel_login.assert_awaited_once_with("333333", "0001")


async def test_cloud_logout_failure_does_not_reject_login(
    cloud_api: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """An unavailable logout endpoint must not turn valid credentials into a connection error."""
    cloud_api.panel_logout.side_effect = NotFoundError
    tester = ConnectionTest(MagicMock(spec=aiohttp.ClientSession))
    assert await tester.test_connection(DeviceType.CLOUD, dict(CLOUD_DATA)) is None
    cloud_api.panel_login.assert_awaited_once_with("ABCDEF", "1234")
    assert "logout failed after successful login (NotFoundError)" in caplog.text


async def test_cloud_login_server_rejection(
    cloud_api: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Report a server rejection separately from a refused network connection."""
    cloud_api.panel_login.side_effect = InternalServerError
    tester = ConnectionTest(MagicMock(spec=aiohttp.ClientSession))
    assert (
        await tester.test_connection(DeviceType.CLOUD, dict(CLOUD_DATA))
        == "cloud_error"
    )
    assert "Cloud API rejected the request (InternalServerError)" in caplog.text
    cloud_api.panel_logout.assert_not_awaited()
