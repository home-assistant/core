"""Config entry type runtime_data type specification for EnOcean integration."""

from homeassistant.config_entries import ConfigEntry

from .dongle import EnOceanDongle

type EnOceanConfigEntry = ConfigEntry[EnOceanConfigRuntimeData]


class EnOceanConfigRuntimeData:
    """Runtime data for EnOcean config entries."""

    def __init__(self, gateway: EnOceanDongle) -> None:
        """Initialize runtime data."""
        self._gateway = gateway

    @property
    def gateway(self) -> EnOceanDongle:
        """Return the EnOcean gateway."""
        return self._gateway
