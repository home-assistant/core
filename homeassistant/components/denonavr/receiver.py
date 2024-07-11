"""Code to handle a DenonAVR receiver."""

from __future__ import annotations

from collections.abc import Callable
import logging

from denonavr import DenonAVR
import httpx

_LOGGER = logging.getLogger(__name__)


class ConnectDenonAVR:
    """Class to async connect to a DenonAVR receiver."""

    def __init__(
        self,
        host: str,
        timeout: float,
        show_all_inputs: bool,
        zone2: bool,
        zone3: bool,
        use_telnet: bool,
        update_audyssey: bool,
        async_client_getter: Callable[[], httpx.AsyncClient],
    ) -> None:
        """Initialize the class."""
        self._async_client_getter = async_client_getter
        self._receiver: DenonAVR | None = None
        self._host = host
        self._show_all_inputs = show_all_inputs
        self._timeout = timeout
        self._use_telnet = use_telnet
        self._update_audyssey = update_audyssey

        self._zones: dict[str, str | None] = {}
        if zone2:
            self._zones["Zone2"] = None
        if zone3:
            self._zones["Zone3"] = None

    @property
    def receiver(self) -> DenonAVR | None:
        """Return the class containing all connections to the receiver."""
        return self._receiver

    async def async_connect_receiver(self) -> bool:
        """Connect to the DenonAVR receiver."""
        await self.async_init_receiver_class()
        assert self._receiver

        if (
            self._receiver.manufacturer is None
            or self._receiver.name is None
            or self._receiver.model_name is None
            or self._receiver.receiver_type is None
        ):
            _LOGGER.error(
                (
                    "Missing receiver information: manufacturer '%s', name '%s', model"
                    " '%s', type '%s'"
                ),
                self._receiver.manufacturer,
                self._receiver.name,
                self._receiver.model_name,
                self._receiver.receiver_type,
            )
            return False

        _LOGGER.debug(
            "%s receiver %s at host %s connected, model %s, serial %s, type %s",
            self._receiver.manufacturer,
            self._receiver.name,
            self._receiver.host,
            self._receiver.model_name,
            self._receiver.serial_number,
            self._receiver.receiver_type,
        )

        return True

    async def async_init_receiver_class(self) -> None:
        """Initialize the DenonAVR class asynchronously."""
        receiver = DenonAVR(
            host=self._host,
            show_all_inputs=self._show_all_inputs,
            timeout=self._timeout,
            add_zones=self._zones,
        )
        # Use httpx.AsyncClient getter provided by Home Assistant
        receiver.set_async_client_getter(self._async_client_getter)
        await receiver.async_setup()
        # Do an initial update if telnet is used.
        if self._use_telnet:
            await receiver.async_update()
            if self._update_audyssey:
                await receiver.async_update_audyssey()
            await receiver.async_telnet_connect()

        self._receiver = receiver
