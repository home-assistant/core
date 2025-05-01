from frisquet_connect.const import SanitaryWaterMode, SanitaryWaterType
from frisquet_connect.domains.model_base import ModelBase


class WaterHeater(ModelBase):
    _TYPE_ECS: int
    _solaire: bool
    _MODE_ECS: dict
    _MODE_ECS_SOLAIRE: dict
    _MODE_ECS_PAC: dict

    def __init__(self, response_json: dict):
        super().__init__(response_json)

    @property
    def sanitary_water_type(self) -> SanitaryWaterType:
        return SanitaryWaterType(self._TYPE_ECS)

    @property
    def sanitary_water_mode(self) -> SanitaryWaterMode:
        if not self._solaire:
            return SanitaryWaterMode(self._MODE_ECS.get("id"))
        else:
            return SanitaryWaterMode(self._MODE_ECS_SOLAIRE.get("id"))
        # TODO: What about the PAC mode ?
        # return SanitaryWaterMode(self._MODE_ECS_PAC.get("id"))
