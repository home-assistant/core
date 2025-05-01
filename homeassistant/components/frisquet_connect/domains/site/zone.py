from typing import List
from frisquet_connect.domains.model_base import ModelBase
from frisquet_connect.domains.site.zone_detail import ZoneDetail
from frisquet_connect.domains.site.zone_scheduler import ZoneScheduler


class Zone(ModelBase):
    _boost_disponible: bool
    _identifiant: str
    _nom: str
    _zone_detail: ZoneDetail
    _zone_schedulers: List[ZoneScheduler]

    def __init__(self, response_json: dict):
        super().__init__(response_json)
        if "carac_zone" in response_json:
            self._zone_detail = ZoneDetail(response_json["carac_zone"])
        if "programmation" in response_json:
            self._zone_schedulers = []
            for prog in response_json["programmation"]:
                self._zone_schedulers.append(ZoneScheduler(prog))

    @property
    def name(self) -> str:
        return self._nom

    @property
    def label_id(self) -> str:
        return self._identifiant

    @property
    def detail(self) -> ZoneDetail:
        return self._zone_detail

    @property
    def is_boost_available(self) -> bool:
        return self._boost_disponible
