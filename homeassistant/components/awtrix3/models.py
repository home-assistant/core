"""AWTRIX models."""

class DeviceStat:
    """Represent device stat information."""

    bat: int
    bat_raw: int
    type: int
    lux: int
    ldr_raw: int
    ram: int
    bri: int
    temp: int
    hum: int
    uptime: int
    wifi_signal: int
    messages: int
    version: str
    indicator1: bool
    indicator2: bool
    indicator3: bool
    app: str
    uid: str
    matrix: bool
    ip_address: str

class AwtrixData(DeviceStat):
    """Represent device all state information."""

    abri: bool
    atrans: bool
    button_left: bool
    button_select: bool
    button_right: bool

    def __getitem__(self, item):
        """Get item."""
        return self.__dict__[item]
