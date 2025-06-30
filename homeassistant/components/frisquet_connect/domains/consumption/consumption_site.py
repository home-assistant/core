from frisquet_connect.const import ConsumptionType
from frisquet_connect.domains.consumption.consumption import Consumption
from frisquet_connect.domains.model_base import ModelBase


class ConsumptionSite(ModelBase):
    _consumptions: dict[ConsumptionType]

    def __init__(self, reponse_json: dict):
        self._consumptions = {}
        for consulmption_type, consumption_items in reponse_json.items():
            if isinstance(consumption_items, list):
                consumption = Consumption(consulmption_type, consumption_items)
                self._consumptions[consumption.type] = consumption

    @property
    def consumptions(self) -> dict[Consumption]:
        return self._consumptions
