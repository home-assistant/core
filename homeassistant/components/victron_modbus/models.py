"""The Victron Modbus devices this integration supports."""

from dataclasses import dataclass

from victron_modbus.p1link import P1Link
from victron_modbus.vm_3p5a import VM3P5A
from victron_modbus.vm_3p75ct import VM3P75CT

type VictronDevice = VM3P75CT | VM3P5A | P1Link


@dataclass(frozen=True, kw_only=True)
class VictronModel:
    """One supported Victron Modbus device model."""

    name: str
    device_class: type[VictronDevice]


# Keyed by the model stored in the config entry.
MODELS: dict[str, VictronModel] = {
    "vm_3p75ct": VictronModel(name="VM-3P75CT", device_class=VM3P75CT),
    "vm_3p5a": VictronModel(name="VM-3P5A", device_class=VM3P5A),
    "p1link": VictronModel(name="P1Link", device_class=P1Link),
}

MODEL_BY_CLASS: dict[type[VictronDevice], str] = {
    model.device_class: key for key, model in MODELS.items()
}
