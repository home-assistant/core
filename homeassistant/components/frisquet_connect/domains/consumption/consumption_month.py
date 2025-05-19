from datetime import datetime
from frisquet_connect.domains.model_base import ModelBase


class ConsumptionMonth(ModelBase):
    _mois: int
    _annee: str
    _valeur: int

    def __init__(self, response_json):
        super().__init__(response_json)

    @property
    def month_label(self) -> str:
        return datetime(1900, self._mois, 1).strftime("%B")

    @property
    def month_num(self) -> int:
        return self._mois

    @property
    def year(self) -> int:
        return int(self._annee)

    @property
    def value(self) -> int:
        return self._valeur
