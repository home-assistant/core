"""Common fixtures for Bitvis Power Hub tests."""

from collections.abc import Generator, Iterator
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from bitvis_protobuf.listener import FilterIp, FilterMac
from bitvis_protobuf.parse import PayloadSample, parse_payload
from bitvis_protobuf.powerhub_pb2 import Payload
import pytest

from homeassistant.components.bitvis.const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_DEVICE_MAC = "aa:bb:cc:dd:ee:ff"
SECOND_DEVICE_MAC = "11:22:33:44:55:66"


@contextmanager
def patch_config_flow_connectivity(
    resolved_host: str,
    *,
    mac_address: str = TEST_DEVICE_MAC,
    deliver_mac: bool = True,
    invalid_mac: bool = False,
    port_bind_side_effect: BaseException | None = None,
    discovery_timeout: bool = False,
    use_real_listener_registry: bool = False,
    shared_listener: MagicMock | None = None,
) -> Iterator[AsyncMock]:
    """Patch library connectivity helpers used by the config flow."""
    mock_listener = shared_listener or MagicMock()
    mock_listener.start = AsyncMock()
    mock_listener.stop = AsyncMock()

    if shared_listener is None:
        if invalid_mac:

            def _dispatch(data: bytes, addr: tuple[str, int]) -> None:
                parse_payload(data)

            mock_listener.dispatch = MagicMock(side_effect=_dispatch)

            def _on_register(_filt: MagicMock, _callback: MagicMock) -> None:
                payload = Payload()
                payload.sample.SetInParent()
                mock_listener.dispatch(
                    payload.SerializeToString(), (resolved_host, 1234)
                )

            mock_listener.register = MagicMock(side_effect=_on_register)
        elif deliver_mac and not discovery_timeout:

            def _on_register(_filt: MagicMock, callback: MagicMock) -> None:
                payload = PayloadSample(mac_address=mac_address, sample=MagicMock())
                callback(payload, (resolved_host, 1234))

            mock_listener.register = MagicMock(side_effect=_on_register)
        else:
            mock_listener.register = MagicMock()
        mock_listener.unregister = MagicMock()
        type(mock_listener).is_empty = PropertyMock(return_value=True)
    elif invalid_mac:

        def _dispatch(data: bytes, addr: tuple[str, int]) -> None:
            parse_payload(data)

        mock_listener.dispatch = MagicMock(side_effect=_dispatch)
        original_register = mock_listener.register.side_effect

        def _on_register(filt: FilterIp | FilterMac, callback: MagicMock) -> None:
            if isinstance(filt, FilterIp):
                payload = Payload()
                payload.sample.SetInParent()
                mock_listener.dispatch(
                    payload.SerializeToString(), (resolved_host, 1234)
                )
                return
            if original_register is not None:
                original_register(filt, callback)

        mock_listener.register = MagicMock(side_effect=_on_register)
    elif deliver_mac and not discovery_timeout:
        original_register = mock_listener.register.side_effect

        def _on_register(filt: FilterIp | FilterMac, callback: MagicMock) -> None:
            if isinstance(filt, FilterIp):
                payload = PayloadSample(mac_address=mac_address, sample=MagicMock())
                callback(payload, (resolved_host, 1234))
                return
            if original_register is not None:
                original_register(filt, callback)

        mock_listener.register = MagicMock(side_effect=_on_register)

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
        if not use_real_listener_registry:
            mock_registry = stack.enter_context(
                patch(
                    "homeassistant.components.bitvis.config_flow.async_get_listener_registry",
                )
            )
            mock_registry.return_value.has_listener.return_value = False
            mock_registry.return_value.async_get_or_create = AsyncMock(
                return_value=mock_listener
            )
            mock_registry.return_value.async_remove_if_unused = AsyncMock()
        else:
            stack.enter_context(
                patch(
                    "homeassistant.components.bitvis.coordinator.SharedListener",
                    return_value=mock_listener,
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
        unique_id="11:22:33:44:55:66",
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
def mock_shared_listener() -> MagicMock:
    """Return a mocked bitvis_protobuf SharedListener."""
    listener = MagicMock()
    listener._callbacks: dict[FilterMac, MagicMock] = {}
    listener.start = AsyncMock()
    listener.stop = AsyncMock()

    def register(filt: FilterMac, callback: MagicMock) -> None:
        listener._callbacks[filt] = callback

    def unregister(filt: FilterMac) -> None:
        listener._callbacks.pop(filt, None)

    listener.register = MagicMock(side_effect=register)
    listener.unregister = MagicMock(side_effect=unregister)
    type(listener).is_empty = PropertyMock(side_effect=lambda: not listener._callbacks)
    return listener


@pytest.fixture
def patch_shared_listener(mock_shared_listener: MagicMock) -> Generator[MagicMock]:
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
    patch_shared_listener: MagicMock,
) -> MockConfigEntry:
    """Set up the integration with a mocked UDP listener."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
