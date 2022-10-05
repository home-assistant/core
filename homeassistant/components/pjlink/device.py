"""PJLink projector factory."""
from __future__ import annotations

import asyncio

from pypjlink import Projector
from pypjlink.projector import ProjectorError

from .util import LampStateType, PJLinkConfig, format_input_source


class PJLinkDevice:
    """PJLink projector factory."""

    _name: str
    _encoding: str
    _timeout: int
    _power_state: str | None = None
    _muted: bool = False
    _lamp_states: list[LampStateType]
    _error_dict: dict[str, str]
    _other_info: str
    _current_source: str | None
    _source_list: list[str] | None = None
    _source_name_mapping: dict[str, tuple[str, int]]

    _manufacturer: str | None = None
    _model: str | None = None

    _lock: asyncio.Lock

    _first_metadata_run: bool = False

    def __init__(self, conf: PJLinkConfig) -> None:
        """Initialize a PJLink projector factory."""
        self.host = conf.host
        self.port = conf.port

        self._name = conf.name
        self._encoding = conf.encoding
        self._timeout = conf.timeout

        self._lock = asyncio.Lock()

        self.__password = conf.password

        self._error_dict = {}
        self._source_name_mapping = {}

    def get_projector(self) -> Projector:
        """Create PJLink Projector instance."""
        projector = Projector.from_address(
            self.host, self.port, self.encoding, self.timeout
        )

        projector.authenticate(self.__password)

        return projector

    def async_get_state(self) -> str | None:
        """Get the current power state."""
        return self._power_state

    def async_get_muted(self) -> bool:
        """Get the current volume mute state."""
        return self._muted

    def async_get_other_info(self) -> str:
        """Get other info reported by the projector."""
        return self._other_info

    def async_get_error_state(self, error_key: str) -> str:
        """Get the error state for a given error type."""
        return self._error_dict[error_key]

    def async_get_lamp_state(self, lamp_idx: int) -> LampStateType:
        """Get the lamp state for a given lamp index."""
        return self._lamp_states[lamp_idx]

    def async_get_current_source(self) -> str | None:
        """Get the current source."""
        return self._current_source

    def get_source_for_name(self, name: str) -> tuple[str, int]:
        """Get the projector source name for a given friendly name."""
        return self._source_name_mapping[name]

    async def async_update(self) -> None:
        """Update all polled parameters."""
        async with self._lock:
            with self.get_projector() as projector:
                pwstate = projector.get_power()

                self._power_state = pwstate

                if pwstate in ("on", "warm-up"):
                    self._muted = projector.get_mute()[1]
                    self._current_source = format_input_source(*projector.get_input())
                else:
                    self._muted = False
                    self._current_source = None

                if not self._first_metadata_run or pwstate == "on":
                    # Try and update metadata; some projectors won't report data if they're not on.
                    self._update_metadata(projector)

                # Lamp hours
                try:
                    lamp_states: list[LampStateType] = []

                    for lamp_hours, lamp_state in projector.get_lamps():
                        lamp_states.append({"state": lamp_state, "hours": lamp_hours})

                    self._lamp_states = lamp_states
                except ProjectorError:
                    pass

                # Errors
                try:
                    errors = projector.get_errors()

                    for key, value in errors.items():
                        if key == "temperature":
                            key = "temp"

                        self._error_dict[key] = value
                except ProjectorError:
                    pass

                # Get other info
                try:
                    self._other_info = projector.get_other_info()
                except ProjectorError:
                    pass

    def _update_metadata(self, projector: Projector) -> None:
        """Update metadata for the projector, skipping cached values."""
        self._first_metadata_run = True

        if not self._name:
            try:
                self._name = projector.get_name()
            except ProjectorError:
                pass

        if not self._manufacturer:
            try:
                self._manufacturer = projector.get_manufacturer()
            except ProjectorError:
                pass

        if not self._model:
            try:
                self._model = projector.get_product_name()
            except ProjectorError:
                pass

        if not self._source_list:
            try:
                inputs = projector.get_inputs()

                self._source_name_mapping = {format_input_source(*x): x for x in inputs}
                self._source_list = sorted(self._source_name_mapping.keys())
            except ProjectorError:
                pass

    def async_stop(self) -> None:
        """Destroy the device."""

    @property
    def manufacturer(self) -> str | None:
        """Get the projector manufacturer."""
        return self._manufacturer

    @property
    def model(self) -> str | None:
        """Get the projector model."""
        return self._model

    @property
    def name(self) -> str:
        """Get the projector name."""
        return self._name

    @property
    def encoding(self) -> str:
        """Get the projector encoding."""
        return self._encoding

    @property
    def timeout(self) -> int:
        """Get the timeout for the projector."""
        return self._timeout

    @property
    def source_list(self) -> list[str] | None:
        """Get the projector sources."""
        return self._source_list

    @property
    def lamp_count(self) -> int:
        """Get the count of lamps in the projector."""
        return len(self._lamp_states)
