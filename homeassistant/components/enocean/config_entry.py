"""Config entry type runtime_data type specification for EnOcean integration."""

from homeassistant.config_entries import ConfigEntry

from .dongle import EnOceanDongle

type EnOceanConfigEntry = ConfigEntry[EnOceanConfigRuntimeData]


class EnOceanConfigRuntimeData:
    """Runtime data for EnOcean config entries."""

    def __init__(self, dongle: EnOceanDongle) -> None:
        """Initialize runtime data."""
        self._dongle = dongle

    @property
    def dongle(self) -> EnOceanDongle:
        """Return the EnOcean dongle."""
        return self._dongle
