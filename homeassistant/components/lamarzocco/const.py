"""Constants for the La Marzocco integration."""

from typing import Final

from lmcloud.const import LaMarzoccoModel

DOMAIN: Final = "lamarzocco"

CONF_MACHINE: Final = "machine"

KEYS_PER_MODEL: Final = {
    LaMarzoccoModel.LINEA_MICRA: None,
    LaMarzoccoModel.LINEA_MINI: None,
    LaMarzoccoModel.GS3_AV: 4,
    LaMarzoccoModel.GS3_MP: None,
}
