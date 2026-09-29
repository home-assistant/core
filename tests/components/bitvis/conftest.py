"""Common fixtures for Bitvis Power Hub tests."""

from collections.abc import Callable, Generator, Iterator
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from bitvis_protobuf.listener import Filter, FilterIp
from bitvis_protobuf.parse import PayloadDiagnostic, PayloadSample, parse_payload
from bitvis_protobuf.powerhub_pb2 import Payload
from bitvis_protobuf.utils import InvalidMacAddressError
import pytest

from homeassistant.components.bitvis.const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

TEST_DEVICE_MAC = "aa:bb:cc:dd:ee:ff"
SECOND_DEVICE_MAC = "11:22:33:44:55:66"

type ListenerCallback = Callable[
    [PayloadSample | PayloadDiagnostic, tuple[str, int]], None
]
type ErrorCallback = Callable[[Exception, tuple[str, int]], None]


class FakeListener:
    """In-memory SharedListener stand-in for config-flow and coordinator tests."""

    def __init__(self) -> None:
        """Initialize callback storage and async start/stop mocks."""
        self._callbacks: dict[Filter, ListenerCallback] = {}
        self._error_callbacks: list[ErrorCallback] = []
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.register = MagicMock(side_effect=self._register)
        self.unregister = MagicMock(side_effect=self._unregister)
        self.register_error_callback = MagicMock(
            side_effect=self._error_callbacks.append
        )
        self.unregister_error_callback = MagicMock(side_effect=self._unregister_error)
        self.dispatch = MagicMock(side_effect=self._dispatch)

    @property
    def is_empty(self) -> bool:
        """Return True when no payload callbacks are registered."""
        return not self._callbacks

    def _register(self, filt: Filter, callback: ListenerCallback) -> None:
        if filt in self._callbacks:
            raise RuntimeError(f"Filter already registered: {filt}")
        self._callbacks[filt] = callback

    def _unregister(self, filt: Filter) -> None:
        self._callbacks.pop(filt, None)

    def _unregister_error(self, callback: ErrorCallback) -> None:
        if callback in self._error_callbacks:
            self._error_callbacks.remove(callback)

    def _dispatch(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            payload = parse_payload(data)
        except InvalidMacAddressError as err:
            for callback in self._error_callbacks:
                callback(err, addr)
            return
        if payload is None:
            return
        self.deliver(payload, addr)

    def deliver(
        self,
        payload: PayloadSample | PayloadDiagnostic,
        addr: tuple[str, int],
    ) -> None:
        """Deliver an already-parsed payload to matching callbacks."""
        host = addr[0]
        for filt, callback in self._callbacks.items():
            if filt.match(payload, host):
                callback(payload, addr)


@contextmanager
def patch_config_flow_connectivity(
    resolved_host: str,
    *,
    mac_address: str = TEST_DEVICE_MAC,
    deliver_mac: bool = True,
    invalid_mac: bool = False,
    port_bind_side_effect: BaseException | None = None,
    discovery_timeout: bool = False,
    register_side_effect: BaseException | None = None,
    shared_listener: FakeListener | None = None,
) -> Iterator[AsyncMock]:
    """Patch library connectivity helpers used by the config flow."""
    listener = shared_listener or FakeListener()

    if register_side_effect is not None:
        listener.register.side_effect = register_side_effect
    else:
        original_register = listener.register.side_effect

        def _on_register(filt: Filter, callback: ListenerCallback) -> None:
            original_register(filt, callback)
            if not isinstance(filt, FilterIp):
                return
            if invalid_mac:
                payload = Payload()
                payload.sample.SetInParent()
                listener.dispatch(payload.SerializeToString(), (resolved_host, 1234))
            elif deliver_mac and not discovery_timeout:
                callback(
                    PayloadSample(mac_address=mac_address, sample=MagicMock()),
                    (resolved_host, 1234),
                )

        listener.register.side_effect = _on_register

    with ExitStack() as stack:
        mock_verify = stack.enter_context(
            patch(
                "homeassistant.components.bitvis.config_flow.async_verify_udp_port_bindable",
                new_callable=AsyncMock,
                side_effect=port_bind_side_effect,
            )
        )
        stack.enter_context(
            patch(
                "homeassistant.components.bitvis.config_flow.async_resolve_host",
                new_callable=AsyncMock,
                return_value={resolved_host},
            )
        )
        stack.enter_context(
            patch(
                "homeassistant.components.bitvis.coordinator.SharedListener",
                return_value=listener,
            )
        )
        if discovery_timeout:
            stack.enter_context(
                patch(
                    "homeassistant.components.bitvis.config_flow.DISCOVERY_TIMEOUT",
                    0,
                )
            )
        yield mock_verify


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT},
        unique_id=TEST_DEVICE_MAC,
        title=DEFAULT_NAME,
    )


@pytest.fixture
def mock_zeroconf_config_entry() -> MockConfigEntry:
    """Return a mocked config entry for zeroconf discovery host."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.200", CONF_PORT: DEFAULT_PORT},
        unique_id=TEST_DEVICE_MAC,
        title=DEFAULT_NAME,
    )


@pytest.fixture
def mock_ipv6_config_entry() -> MockConfigEntry:
    """Return a mocked config entry with an IPv6 host."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "2001:db8::10", CONF_PORT: DEFAULT_PORT},
        unique_id=SECOND_DEVICE_MAC,
        title=DEFAULT_NAME,
    )


@pytest.fixture
def mock_second_config_entry() -> MockConfigEntry:
    """Return a second mocked config entry on the same UDP port."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.101", CONF_PORT: DEFAULT_PORT},
        unique_id=SECOND_DEVICE_MAC,
        title=DEFAULT_NAME,
    )


@pytest.fixture
def mock_shared_listener() -> FakeListener:
    """Return a fake bitvis_protobuf SharedListener."""
    return FakeListener()


@pytest.fixture
def patch_shared_listener(
    mock_shared_listener: FakeListener,
) -> Generator[FakeListener]:
    """Patch SharedListener to return a mocked instance."""
    with patch(
        "homeassistant.components.bitvis.coordinator.SharedListener",
        return_value=mock_shared_listener,
    ):
        yield mock_shared_listener


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bitvis.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_shared_listener: FakeListener,
) -> MockConfigEntry:
    """Set up the integration with a mocked UDP listener."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry
