from frisquet_connect.domains.model_base import ModelBase
from frisquet_connect.domains.site.alarm import Alarm


class SiteLight(ModelBase):
    _identifiant_chaudiere: str
    _nom: str
    _alarms: list[Alarm]

    def __init__(self, response_json: dict):
        super().__init__(response_json)
        if "alarmes" in response_json:
            self._alarms = []
            for alarm in response_json["alarmes"]:
                self._alarms.append(Alarm(alarm))

    @property
    def site_id(self) -> str:
        return self._identifiant_chaudiere

    @property
    def name(self) -> str:
        return self._nom

    @property
    def alarms(self) -> list[Alarm]:
        return self._alarms

    def __repr__(self):
        return self.name
