"""Module containing a representation of a supported EnOcean device type."""
from homeassistant.helpers import selector


class EnOceanSupportedDeviceType:
    """Representation of a supported EnOcean device type."""

    manufacturer: str
    model: str
    eep: str

    def __init__(self, manufacturer: str = "", model: str = "", eep: str = "") -> None:
        """Construct an EnOcean device type."""
        self.manufacturer = manufacturer
        self.model = model
        self.eep = eep

    @property
    def unique_id(self) -> str:
        """Return a unique id for this device type."""
        return (
            self.eep.replace(";", "")
            + ";"
            + self.manufacturer.replace(";", "")
            + ";"
            + self.model.replace(";", "")
        )

    @property
    def select_option_dict(self) -> selector.SelectOptionDict:
        """Return a SelectOptionDict."""
        return selector.SelectOptionDict(
            value=self.unique_id, label=self.manufacturer + " " + self.model
        )
