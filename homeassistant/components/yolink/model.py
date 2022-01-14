"""VO."""

from typing import Dict

from pydantic import BaseModel

from .const import YoLinkAPIError


class BRDP(BaseModel):
    """BRDP of YoLink API."""

    code: str
    desc: str
    data: Dict

    def raise_for_status(self):
        """Check API Response."""
        if self.code != "000000":
            raise YoLinkAPIError(self.code, self.desc)


class BSDPHelper:
    """YoLink API -> BSDP Builder."""

    _bsdp: Dict

    def __init__(self, deviceId: str, deviceToken: str, method: str):
        """Constanst."""
        self._bsdp = {"method": method, "params": {}}
        if deviceId is not None:
            self._bsdp["targetDevice"] = deviceId
            self._bsdp["token"] = deviceToken

    def addParams(self, params: Dict):
        """Build params of BSDP."""
        self._bsdp.update
        self._bsdp["params"].update(params)
        return self

    # def addParams(self, **kwargs):
    #     self._bsdp["params"].update(kwargs)
    #     return self

    def build(self) -> Dict:
        """Generate BSDP."""
        return self._bsdp
