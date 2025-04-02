"""Unraid data models."""


class InfoModel:
    """Unraid info."""

    platform: str
    distro: str
    release: str
    uptime: str

    cpu_manufacturer: str
    cpu_brand: str
    cpu_cores: int
    cpu_threads: int

    def __init__(self, info_response: dict) -> None:
        """Initialize Unraid data."""

        self.platform = info_response["os"]["platform"]
        self.distro = info_response["os"]["distro"]
        self.release = info_response["os"]["release"]
        self.uptime = info_response["os"]["uptime"]

        self.cpu_manufacturer = info_response["cpu"]["manufacturer"]
        self.cpu_brand = info_response["cpu"]["brand"]
        self.cpu_cores = info_response["cpu"]["cores"]
        self.cpu_threads = info_response["cpu"]["threads"]


class ArrayDisk:
    """Unraid array disk."""

    name: str
    size: str
    status: str
    temp: int

    def __init__(self, disk_response: dict) -> None:
        """Initialize Unraid data."""

        self.name = disk_response["name"]
        self.size = disk_response["size"]
        self.status = disk_response["status"]
        self.temp = disk_response["temp"]


class ArrayModel:
    """Unraid array."""

    state: str
    capacity_disks: list[dict]
    disks: list[ArrayDisk]

    def __init__(self, array_response: dict) -> None:
        """Initialize Unraid data."""

        self.state = array_response["state"]
        self.capacity_disks = array_response["capacity"]["disks"]
        self.disks = [ArrayDisk(disk) for disk in array_response["disks"]]


class UnraidData:
    """Unraid data."""

    _data: dict

    info: InfoModel
    array: ArrayModel

    def __init__(self, response: dict) -> None:
        """Initialize Unraid data."""

        self._data = response["data"]
        self.info = InfoModel(self._data["info"])
        self.array = ArrayModel(self._data["array"])
