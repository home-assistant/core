"""Module containing a representation of a supported EnOcean device type."""
from pathlib import Path

import yaml
from yaml import SafeLoader

from homeassistant.helpers import selector


class EnOceanSupportedDeviceType:
    """Representation of a supported EnOcean device type."""

    unique_id: str
    eep: str
    manufacturer: str
    model: str

    def __init__(
        self,
        unique_id: str = "",
        eep: str = "",
        model: str = "",
        manufacturer: str = "Generic",
    ) -> None:
        """Construct an EnOcean device type."""
        self.unique_id = unique_id
        self.eep = eep
        self.model = model
        self.manufacturer = manufacturer

    @property
    def select_option_dict(self) -> selector.SelectOptionDict:
        """Return a SelectOptionDict."""
        return selector.SelectOptionDict(
            value=self.unique_id, label=self.manufacturer + " " + self.model
        )


_supported_enocean_device_types: dict[str, EnOceanSupportedDeviceType] = {}


def get_supported_enocean_device_types() -> dict[str, EnOceanSupportedDeviceType]:
    """Get a dictionary mapping from EnOcean device type id to EnOceanSupportedDeviceType."""
    if len(_supported_enocean_device_types) > 0:
        return _supported_enocean_device_types

    device_type_ids = []
    file_path = Path(__file__).with_name("supported_device_types.yaml")

    with file_path.open("r", encoding="UTF-8") as file:
        device_types = yaml.load(file, Loader=SafeLoader)

        for device_type in device_types:
            if "uid" not in device_type:
                continue

            if "eep" not in device_type:
                continue

            if "model" not in device_type:
                continue

            device_type_id = device_type["uid"]
            if device_type_id in device_type_ids:
                continue
            device_type_ids.append(device_type_id)

            eep = device_type["eep"]
            if len(eep) != 8:
                continue

            model = device_type["model"]

            manufacturer = "Generic"
            if "manufacturer" in device_type:
                manufacturer = device_type["manufacturer"]

            enocean_device_type = EnOceanSupportedDeviceType(
                manufacturer=manufacturer,
                model=model,
                eep=eep,
                unique_id=device_type_id,
            )
            _supported_enocean_device_types[device_type_id] = enocean_device_type

    return _supported_enocean_device_types
