"""System Bridge integration data."""

from dataclasses import dataclass, field

from systembridgeconnector.models.modules import (
    CPU,
    GPU,
    Audio,
    Battery,
    Disks,
    Display,
    Media,
    Memory,
    Networks,
    Process,
    System,
)
from systembridgeconnector.models.settings import SettingsCommandDefinition


@dataclass
class SystemBridgeData:
    """System Bridge Data."""

    audio: Audio | None = None
    battery: Battery | None = None
    # The saved commands from the host's allowlist by ID, None until first fetched
    commands: dict[str, SettingsCommandDefinition] | None = None
    cpu: CPU = field(default_factory=CPU)
    disks: Disks | None = None
    displays: list[Display] = field(default_factory=list[Display])
    gpus: list[GPU] = field(default_factory=list[GPU])
    media: Media = field(default_factory=Media)
    memory: Memory | None = None
    networks: Networks | None = None
    processes: list[Process] = field(default_factory=list[Process])
    system: System | None = None
