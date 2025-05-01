from frisquet_connect.domains.model_base import ModelBase


class Product(ModelBase):

    _gamme: str
    _chaudiere: str
    _version1: str
    _puissance: str

    def __init__(self, response_json: dict):
        super().__init__(response_json)

    def __str__(self):
        return (
            f"{self._chaudiere} - {self._version1} ({self._gamme} - {self._puissance})"
        )
