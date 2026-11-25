"""Tests for the EcoNet integration setup."""

from collections.abc import Awaitable, Callable, Generator
import ssl
import threading
from unittest.mock import MagicMock, call, patch

from aiohttp import ClientError
from pyeconet import EcoNetApiInterface
from pyeconet.equipment import Equipment
from pyeconet.errors import InvalidCredentialsError, PyeconetError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.econet.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


@pytest.fixture
def mqtt_subscription(
    mock_api: MagicMock,
    mock_equipment: Equipment,
) -> Generator[tuple[Callable[[], None], list[tuple[str, int]]]]:
    """Use real MQTT TLS setup without connecting to the broker."""
    api = EcoNetApiInterface(
        "test@example.com", "password", account_id="test", user_token="test"
    )
    api._equipment = {mock_equipment.serial_number: mock_equipment}
    certificate_calls: list[tuple[str, int]] = []
    original_load_default_certs = ssl.SSLContext.load_default_certs
    original_set_default_verify_paths = ssl.SSLContext.set_default_verify_paths
    mock_subscribe = mock_api.subscribe

    # The test executor runs mocks inline, so pass a real callable.
    def subscribe() -> None:
        mock_subscribe()
        api.subscribe()

    def load_default_certs(
        context: ssl.SSLContext, purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH
    ) -> None:
        certificate_calls.append(("load_default_certs", threading.get_ident()))
        original_load_default_certs(context, purpose)

    def set_default_verify_paths(context: ssl.SSLContext) -> None:
        certificate_calls.append(("set_default_verify_paths", threading.get_ident()))
        original_set_default_verify_paths(context)

    with (
        patch.object(ssl.SSLContext, "load_default_certs", load_default_certs),
        patch.object(
            ssl.SSLContext, "set_default_verify_paths", set_default_verify_paths
        ),
        patch("paho.mqtt.client.Client.connect_async"),
        patch("paho.mqtt.client.Client.loop_start"),
    ):
        yield subscribe, certificate_calls


@pytest.mark.parametrize("platform", [Platform.WATER_HEATER])
async def test_subscribe_runs_in_executor(
    mock_api: MagicMock,
    setup_integration: Callable[[], Awaitable[None]],
    mqtt_subscription: tuple[Callable[[], None], list[tuple[str, int]]],
) -> None:
    """Load MQTT certificates outside the event loop during setup."""
    loop_thread = threading.get_ident()
    subscribe, certificate_calls = mqtt_subscription
    mock_api.subscribe = subscribe

    await setup_integration()

    assert {name for name, _ in certificate_calls} == {
        "load_default_certs",
        "set_default_verify_paths",
    }
    assert all(thread != loop_thread for _, thread in certificate_calls)


@pytest.mark.parametrize("platform", [Platform.WATER_HEATER])
async def test_resubscribe_runs_in_executor(
    mock_api: MagicMock,
    setup_integration: Callable[[], Awaitable[None]],
    mqtt_subscription: tuple[Callable[[], None], list[tuple[str, int]]],
) -> None:
    """Keep scheduled MQTT certificate loading outside the event loop."""
    loop_thread = threading.get_ident()
    subscribe, certificate_calls = mqtt_subscription
    with patch(
        "homeassistant.components.econet.async_track_time_interval"
    ) as mock_track_time_interval:
        await setup_integration()

    mock_api.reset_mock()
    mock_api.subscribe = subscribe
    certificate_calls.clear()
    resubscribe = mock_track_time_interval.call_args.args[1]
    with patch("homeassistant.components.econet.asyncio.sleep", return_value=None):
        await resubscribe(dt_util.utcnow())

    assert {name for name, _ in certificate_calls} == {
        "load_default_certs",
        "set_default_verify_paths",
    }
    assert all(thread != loop_thread for _, thread in certificate_calls)
    assert mock_api.mock_calls == [
        call.unsubscribe(),
        call.subscribe(),
        call.refresh_equipment(),
    ]


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(PyeconetError(), id="library_error"),
        pytest.param(ClientError("certificate has expired"), id="client_error"),
    ],
)
async def test_login_error_retries_setup(
    hass: HomeAssistant, exception: Exception
) -> None:
    """Test setup is retried when logging in fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "admin@localhost.com", CONF_PASSWORD: "password0"},
    )
    entry.add_to_hass(hass)

    with patch("pyeconet.EcoNetApiInterface.login", side_effect=exception):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_invalid_credentials(hass: HomeAssistant) -> None:
    """Test setup fails and starts reauth with invalid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "admin@localhost.com", CONF_PASSWORD: "password0"},
    )
    entry.add_to_hass(hass)

    with patch(
        "pyeconet.EcoNetApiInterface.login", side_effect=InvalidCredentialsError
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Invalid credentials provided"

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id
