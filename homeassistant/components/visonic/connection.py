"""Shared contract for Visonic connection helpers."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from .visonic_data_types import VisonicCoordinatorData
from .visonic_types import AlarmPanelCommand, CommandResult


@dataclass(frozen=True, slots=True)
class VisonicConnectionOptions:
    """Behavior settings shared by the connection helpers."""

    enable_remote_arm: bool = False
    enable_remote_disarm: bool = False
    arm_home_enabled: bool = True
    arm_without_usercode: bool = False
    eprom_attributes: bool = False
    retry_count: int = 1
    retry_delay: float = 90


@dataclass(frozen=True, slots=True)
class VisonicPanelMetadata:
    """Panel information reported by a connection."""

    model: str | None
    serial: str | None = None


@dataclass(slots=True)
class VisonicConnectionCallbacks:
    """Events a connection can report to its owner."""

    state_changed: Callable[[float], None]
    panel_ready: Callable[[], None]
    panel_metadata_changed: Callable[[VisonicPanelMetadata], None]
    baud_changed: Callable[[int], None]
    app_id_changed: Callable[[str], None]
    recovery_failed: Callable[[], None] | None = None


class VisonicConnection(ABC):
    """Define the operations required by the shared coordinator."""

    def __init__(
        self,
        options: VisonicConnectionOptions,
        callbacks: VisonicConnectionCallbacks,
    ) -> None:
        """Initialize behavior settings and event callbacks."""
        self.options = options
        self.callbacks = callbacks

    def update_options(self, options: VisonicConnectionOptions) -> None:
        """Apply changed behavior settings."""
        self.options = options

    @abstractmethod
    async def create_state_snapshot(self) -> VisonicCoordinatorData:
        """Return the current whole-panel state."""

    @abstractmethod
    async def async_panel_connect(self) -> bool:
        """Connect to the configured panel and report success."""

    @abstractmethod
    async def async_panel_stop(self) -> None:
        """Stop the connection and release its resources."""

    @abstractmethod
    async def send_command(
        self, command: AlarmPanelCommand, code: str | None
    ) -> CommandResult:
        """Send a panel command using the supplied code."""

    @abstractmethod
    def get_panel_pin_code(self, code: str | None) -> tuple[bool, str | None]:
        """Return whether the code is valid and the resolved panel code."""
