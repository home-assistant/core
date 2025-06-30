from frisquet_connect.const import ZoneMode, ZoneSelector
from frisquet_connect.domains.model_base import ModelBase
from frisquet_connect.domains.site.utils import (
    convert_api_temperature_to_float,
)


class ZoneDetail(ModelBase):
    _MODE: int
    _SELECTEUR: int
    _TAMB: int  # current temperature
    _CAMB: int  # target temperature
    _DERO: bool
    _CONS_RED: int  # consigne reduite
    _CONS_CONF: int  # consigne confort
    _CONS_HG: int  # consigne hors gel
    _ACTIVITE_BOOST: bool

    def __init__(self, response_json: dict):
        super().__init__(response_json)

    @property
    def current_temperature(self) -> float:
        return convert_api_temperature_to_float(self._TAMB)

    @property
    def target_temperature(self) -> float:
        return convert_api_temperature_to_float(self._CAMB)

    @property
    def is_exemption_enabled(self) -> bool:
        return self._DERO

    @property
    def reduced_temperature(self) -> float:
        return convert_api_temperature_to_float(self._CONS_RED)

    @property
    def comfort_temperature(self) -> float:
        return convert_api_temperature_to_float(self._CONS_CONF)

    @property
    def frost_protection_temperature(self) -> float:
        return convert_api_temperature_to_float(self._CONS_HG)

    @property
    def is_boosting(self) -> bool:
        return self._ACTIVITE_BOOST

    @property
    def mode(self) -> ZoneMode:
        return ZoneMode(self._MODE)

    @property
    def selector(self) -> ZoneSelector:
        return ZoneSelector(self._SELECTEUR)
