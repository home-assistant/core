import asyncio
from dataclasses import dataclass

import aiohttp


def _scale_Reading(value: str, scaler: int) -> str:
    """Scale a decimal integer string by a power of 10.

       Done in this complicated way to avoid any issues with floating point precision,
       which can lead to wrong values being returned this library if the value has a lot of digits.

    Examples:
        __scale_Reading('16226390', -1) -> '1622639.0'
        __scale_Reading('16226390', 2) -> '1622639000'
    """
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    if not isinstance(scaler, int):
        raise TypeError("scaler must be an int")
    if value == "":
        raise ValueError("value must not be empty")

    value = value.strip()

    sign = ""
    if value[0] in "+-":
        sign, value = value[0], value[1:]
    if not value.isdigit():
        raise ValueError("value must contain only digits after optional sign")

    if scaler == 0:
        return sign + value
    if scaler > 0:
        return sign + value + "0" * scaler

    # scaler < 0, find the position to insert the decimal point
    pos = len(value) + scaler
    if pos > 0:
        return sign + value[:pos] + "." + value[pos:]

    return sign + "0." + "0" * (-pos) + value


class ConexaSmgwErr(Exception):
    """Base class to catch them all."""


class UnexpectedReturnCode(ConexaSmgwErr):
    """The smgw returned something the logic did not expect."""


class NoUsagePtIdFound(ConexaSmgwErr):
    """The smgw returned no valid usage point ID."""


async def checkNetworkConnection(session: aiohttp.ClientSession, host):
    """Checks if the smgw can be reached on port 443."""
    writer = None
    try:
        # print(f"es ist {time.time()}")
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, 443), timeout=3
        )
        # print(f"Connected! {time.time()}")
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()


class ConexaSMGW:
    @dataclass
    class GatewayInfo:
        jsonVersion: str
        firmwareVersion: str
        smgwID: str

    m2mUrl: str
    gatewayInfo: GatewayInfo

    def __init__(self) -> None:
        """This is a private constructor. Use the create() method to get an instance of this class."""

    @classmethod
    async def create(cls, session: aiohttp.ClientSession, host, usr, pw):
        c = cls()
        c.host = host
        c.m2mUrl = await cls.buildCompleteUrl(session, host, usr, pw)
        c.__session = session
        c.__digest_auth = aiohttp.DigestAuthMiddleware(login=usr, password=pw)
        c.__default_post_kwargs = {
            "ssl": False,
            "headers": {"content-type": "application/json"},
            "allow_redirects": False,
            "middlewares": (c.__digest_auth,),
        }
        # One after the other to not overwhelm the smgw with too many requests at the same time,
        # which might lead to it blocking the connection for some time
        c.gatewayInfo = await c.__smgwInfo()
        c.__usagePtInfo = await c.__smgwUserInfo()
        await c.__smgwUsagePtInfo()
        # print(f"UsagePtInfo: {c.__usagePtInfo}")
        return c

    @staticmethod
    async def buildCompleteUrl(session: aiohttp.ClientSession, host, usr, pw) -> str:
        async with session.post(
            f"https://{host}/smgw/m2m",
            timeout=aiohttp.ClientTimeout(connect=6),
            ssl=False,
            headers={"content-type": "application/json"},
            allow_redirects=False,
            middlewares=(aiohttp.DigestAuthMiddleware(login=usr, password=pw),),
        ) as response:
            if response.status != 307:
                txt = await response.text()
                raise UnexpectedReturnCode(
                    f"SMGW should have returned 307 but instead it returned: {response.status} and following message: {txt}"
                )
        return f"https://{host}{response.headers.get('Location')}"

    @dataclass
    class MeterValue:
        value: str
        unit: str
        utcTimestamp: str

    async def getLatestValues(self) -> dict:
        """ "Gets the latest values for all channels of the connected metering device."""
        async with self.__session.post(
            self.m2mUrl,
            json={
                "method": "readings",
                "usage-point-id": self.__usagePtInfo.usagePtId,
                "database": "origin",
                "last-reading": "true",
            },
            **self.__default_post_kwargs,
        ) as response:
            ret = {}
            # print("Status:", response.status)
            # print("Content-type:", response.headers["content-type"])
            if response.status != 200:
                txt = await response.text()
                raise UnexpectedReturnCode(
                    f"SMGW should have returned 200 but instead it returned: {response.status} and following message: {txt}"
                )
            resp = await response.json()
            # print(json.dumps(resp, indent=4))
            for channel in resp["readings"]["channels"]:
                obis = channel["obis"]
                if obis not in self.__usagePtInfo.channelInfo:
                    raise UnexpectedReturnCode(
                        f"SMGW returned a reading for an unknown channel: {obis}"
                    )
                scaler = int(self.__usagePtInfo.channelInfo[obis].scaler)
                unit = self.__usagePtInfo.channelInfo[obis].unit
                value = channel["readings"][0]["value"]
                ret[obis] = self.MeterValue(
                    value=_scale_Reading(value, scaler),
                    unit=unit,
                    utcTimestamp=channel["readings"][0]["capture-time"],
                )
            return ret

    @dataclass
    class __ChannelInfo:
        scaler: int
        unit: str

    @dataclass
    class __UsagePtInfo:
        usagePtId: str
        usagePtName: str
        startTime: str
        tafNumber: int
        channelInfo: dict[str, ConexaSMGW.__ChannelInfo]

    async def __smgwInfo(self) -> GatewayInfo:
        # print("going to smgw-info")
        async with self.__session.post(
            self.m2mUrl, json={"method": "smgw-info"}, **self.__default_post_kwargs
        ) as response:
            # print("Status:", response.status)
            # print("Content-type:", response.headers["content-type"])
            resp = await response.json()
            return self.GatewayInfo(
                jsonVersion=resp["version"],
                firmwareVersion=resp["smgw-info"]["firmware-info"]["version"],
                smgwID=resp["smgw-info"]["smgw-id"],
            )

    async def __smgwUserInfo(self):
        # print("going to user-info")
        async with self.__session.post(
            self.m2mUrl, json={"method": "user-info"}, **self.__default_post_kwargs
        ) as response:
            # print("Status:", response.status)
            # print("Content-type:", response.headers["content-type"])
            resp = await response.json()
            # print(json.dumps(resp, indent=4))
            ret = None
            for usagePt in resp["user-info"]["usage-points"]:
                if usagePt["taf-number"] == "1" or usagePt["taf-number"] == "7":
                    # print(f"UsagePtId: {usagePt['usage-point-id']}")
                    # print(f"UsagePtName: {usagePt['usage-point-name']}")
                    # print(f"StartTime: {usagePt['start-time']}")
                    # print(f"TafNumber: {usagePt['taf-number']}")
                    ret = self.__UsagePtInfo(
                        usagePtId=usagePt["usage-point-id"],
                        usagePtName=usagePt["usage-point-name"],
                        startTime=usagePt["start-time"],
                        tafNumber=usagePt["taf-number"],
                        channelInfo={},  # Comes later
                    )
                    if usagePt["taf-number"] == "7":
                        # TAF 7 is the one we are interested in, so we can stop looking for more usage points
                        return ret
            if ret is None:
                raise NoUsagePtIdFound(
                    "The smgw did not return any usage point with TAF-number 1 or 7."
                )
            return ret

    async def __smgwUsagePtInfo(self):
        # print("going to usagePt-info")
        async with self.__session.post(
            self.m2mUrl,
            json={
                "method": "usage-point-info",
                "usage-point-id": self.__usagePtInfo.usagePtId,
                "database": "origin",
            },
            **self.__default_post_kwargs,
        ) as response:
            # print("Status:", response.status)
            # print("Content-type:", response.headers["content-type"])
            resp = await response.json()
            # print(json.dumps(resp, indent=4))
            unit_map = {26: "J", 30: "Wh"}
            for channel in resp["usage-point-info"]["databases"][0]["channels"]:
                # print(f"ChannelId: {channel['obis']}")
                # print(f"Scaler: {channel['scaler']}")
                # print(f"Unit: {channel['unit']}")
                try:
                    unit_value = int(channel["unit"])
                except (TypeError, ValueError) as e:
                    raise UnexpectedReturnCode(
                        f"Channel unit is not an integer: {channel['unit']}"
                    ) from e

                if unit_value not in unit_map:
                    raise UnexpectedReturnCode(
                        f"Unknown unit code returned: {unit_value}"
                    )

                self.__usagePtInfo.channelInfo[channel["obis"]] = self.__ChannelInfo(
                    scaler=channel["scaler"], unit=unit_map[unit_value]
                )
