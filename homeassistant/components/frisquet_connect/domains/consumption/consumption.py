from frisquet_connect.const import ConsumptionType
from frisquet_connect.domains.consumption.consumption_month import ConsumptionMonth
from frisquet_connect.domains.model_base import ModelBase


class Consumption(ModelBase):
    _type: str
    consumption_months: list[ConsumptionMonth]

    def __init__(self, consulmption_type: str, consumption_items: list[dict]):
        self._type = consulmption_type

        self.consumption_months = []
        for item in consumption_items:
            self.consumption_months.append(ConsumptionMonth(item))

    @property
    def type(self) -> ConsumptionType:
        return ConsumptionType(self._type)
