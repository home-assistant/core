from frisquet_connect.const import AlarmType
from frisquet_connect.domains.model_base import ModelBase


class Alarm(ModelBase):
    _nom: str

    def __init__(self, response_json: dict):
        super().__init__(response_json)

    @property
    def description(self) -> str:
        return self._nom

    @property
    def alarme_type(self) -> AlarmType:
        if self._nom == "Box Frisquet Connect déconnectée":
            return AlarmType.DISCONNECTED
        return AlarmType(AlarmType.UNKNOWN)
