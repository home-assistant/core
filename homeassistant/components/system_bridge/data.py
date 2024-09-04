"""System Bridge integration data."""

from dataclasses import dataclass, field

from systembridgemodels.modules import (
    CPU,
    GPU,
    Battery,
    Disks,
    Display,
    Media,
    Memory,
    Process,
    System,
)


@dataclass
class SystemBridgeData:
    """System Bridge Data."""

    battery: Battery = field(default_factory=Battery)
    cpu: CPU = field(default_factory=CPU)
    disks: Disks = None
    displays: list[Display] = field(default_factory=list[Display])
    gpus: list[GPU] = field(default_factory=list[GPU])
    media: Media = field(default_factory=Media)
    memory: Memory = None
    processes: list[Process] = field(default_factory=list[Process])
    system: System = None
