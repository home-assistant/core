"""Config entry type runtime_data type specification for EnOcean integration."""

from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.config_entries import ConfigEntry

type EnOceanConfigEntry = ConfigEntry[EnOceanConfigRuntimeData]


class EnOceanConfigRuntimeData:
    """Runtime data for EnOcean config entries."""

    def __init__(self, gateway: EnOceanHomeAssistantGateway) -> None:
        """Initialize runtime data."""
        self._gateway = gateway

    @property
    def gateway(self) -> EnOceanHomeAssistantGateway:
        """Return the EnOcean gateway."""
        return self._gateway
