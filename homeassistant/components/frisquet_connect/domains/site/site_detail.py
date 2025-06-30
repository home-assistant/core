from datetime import datetime
from frisquet_connect.domains.model_base import ModelBase
from frisquet_connect.domains.site.utils import (
    convert_from_epoch_to_datetime,
)


class SiteDetail(ModelBase):

    _DATE_HEURE_CHAUDIERE: str
    _CHAUDIERE_EN_VEILLE: bool
    _AUTO_MANU: bool

    def __init__(self, response_json: dict):
        super().__init__(response_json)

    @property
    def current_boiler_timestamp(self) -> datetime:
        return convert_from_epoch_to_datetime(int(self._DATE_HEURE_CHAUDIERE))

    @property
    def is_boiler_standby(self) -> bool:
        return self._CHAUDIERE_EN_VEILLE

    @property
    def is_heat_auto_mode(self) -> bool:
        return self._AUTO_MANU
