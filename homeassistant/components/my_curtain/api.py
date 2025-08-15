"""My Curtain."""

import binascii
import logging
import asyncio
import aiohttp

_LOGGER = logging.getLogger(__name__)


class MyCurtainApiClient:
    """API client."""

    def __init__(
        self,
        username: str,
        password: str,
    ) -> None:
        """Initialize the API client."""
        _LOGGER.info("Initialize the API client" + username + "#" + password)  # noqa: G003
        self._username = username
        self._password = password
        self._devices = []  # 初始化为空列表，将从API获取
        self._token = None  # 存储获取到的Token
        self._auth_url = "https://wly87bcr9j.execute-api.cn-north-1.amazonaws.com.cn/prod/assistantLogin"
        self._device_url = " https://wly87bcr9j.execute-api.cn-north-1.amazonaws.com.cn/prod/findDeviceByAccount"  # 设备列表URL
        self._command_url = "https://wly87bcr9j.execute-api.cn-north-1.amazonaws.com.cn/prod/assistantSendOrder"  # 命令发送URL

    async def authenticate(self) -> None:
        """Authenticate the user and obtain a Token through an actual URL request."""
        # Construct request parameters
        data = {"account": self._username, "password": self._password}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self._auth_url, json=data) as response:
                    result = await response.json()
                    # Check the response status code
                    if result.get("code") != 200:
                        raise ValueError(
                            f"Authentication request failed, status code: {result.get('code')}"
                        )
                    # Parse the response JSON to obtain the token
                    result_data = result.get("data")
                    token = result_data.get("token")
                    if not token:
                        raise ValueError(
                            "The authentication response does not contain a Token."
                        )
                    # Store the Token
                    self._token = token
        except aiohttp.ClientError as e:
            raise ValueError(f"Network request error: {str(e)}")
        await asyncio.sleep(0.5)  # Simulate network delay

    async def get_devices(self) -> list[dict]:
        """Get the list of devices"""
        # If there is no token, perform authentication first.
        if not self._token:
            await self.authenticate()

        # Construct the request header and add the token
        headers = {
            "token": f"{self._token}"  # 假设使用Bearer token，根据实际API调整
        }

        # Construct the request body and add the account parameter
        data = {}

        try:
            async with aiohttp.ClientSession() as session:  # noqa: SIM117
                # Change to a POST request and pass the account parameter in JSON format.
                async with session.post(
                    self._device_url, headers=headers, json=data
                ) as response:
                    result = await response.json()
                    # Check the response status code
                    if result.get("code") != 200:
                        raise ValueError(
                            f"Failed to retrieve the device list, status code: {result.get('code')}"
                        )

                    # Correctly parse the nested list structure
                    devices_data = []
                    data_list = result.get("data", {}).get("list", [])

                    # Check if the list is empty
                    if data_list and len(data_list) > 0:
                        # Get the first element in the list
                        first_item = data_list[0]
                        # Get the device list from the first element
                        if isinstance(first_item, dict):
                            devices_data = first_item.get("list", [])

                    # Convert to internal format
                    self._devices = self._parse_devices(devices_data)
        except aiohttp.ClientError as e:
            raise ValueError(
                f"Network request error when getting the device list: {str(e)}"
            )
        await asyncio.sleep(0.3)  # Simulate delay
        return self._devices

    def _parse_devices(self, devices_data: list[dict]) -> list[dict]:
        """Parse the device data returned by the API into an internal format."""
        parsed_devices = []
        for device in devices_data:
            # Adjust the parsing logic according to the actual data structure returned by the API
            parsed_device = {
                "id": device.get("deviceId", ""),
                "name": device.get("deviceName", ""),
                "subID": device.get("gatewayMac", ""),
                "type": device.get("deviceType", "curtain"),
                "state": "idle",  # 假设初始状态为idle
                "position": device.get("position", 50),
                "is_open": device.get("position", 50) > 50,
                "is_closed": device.get("position", 50) == 0,
                "online_status": device.get("onlineStatus", 0),  # 添加在线状态
                "battery": device.get("electric", 100),  # 添加电池电量
                # Keep the original data for debugging purposes
                # "raw_data": device,
            }
            parsed_devices.append(parsed_device)
        return parsed_devices

    async def set_device_position(self, device_id: str, position: int) -> bool:
        """Set the device location."""
        for device in self._devices:
            if device["id"] == device_id:
                device["state"] = (
                    "opening" if position > device["position"] else "closing"
                )
                device["position"] = position
                # Asynchronously execute the device operation completion logic
                asyncio.create_task(  # noqa: RUF006
                    self._complete_device_operation(
                        device_id, position, f"{device['subID']}"
                    )
                )
                return True
        return False

    async def _complete_device_operation(
        self, device_id: str, position: int, subID: str
    ) -> None:
        """Send a request to modify the device's location."""
        # If there is no token, perform authentication first.
        if not self._token:
            await self.authenticate()

        # Construct request headers and add token
        headers = {
            "token": f"{self._token}"  # Assuming Bearer token is used, adjust according to the actual API.
        }

        # Generate control commands
        byte_data = device_id.encode("utf-8")  # Convert to bytes
        hex_str = binascii.hexlify(byte_data).decode(
            "ascii"
        )  # Convert to a hexadecimal string
        # Revise: Convert position to a two-digit hexadecimal string
        hex_height = f"{position:02X}"
        # Revise: Construct a complete res string and calculate its length
        res = f"01 {hex_str} 02 {hex_height}"
        res_bytes = res.replace(" ", "").encode("ascii")
        length = len(res_bytes) // 2

        # Revise: Convert the length to a two-digit hexadecimal string
        hex_length = f"{length:02X}"

        # Construct a complete command
        order = f"4A640040FF{hex_length}00{res.replace(' ', '')}"

        # Calculate the checksum and append it to the end of the command
        checksum = self.make_checksum(order)
        order = order + checksum

        # Construct the request body
        data = {"deviceId": subID, "order": order}

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    self._command_url, headers=headers, json=data
                ) as response1,
            ):
                result = await response1.json()
                if result.get("code") != 200:
                    raise ValueError(  # noqa: TRY301
                        f"Sending the command failed, status code: {result.get('code')}, Response: {result}"
                    )
        except aiohttp.ClientError as e:
            raise ValueError(
                f"Network request error when sending device commands: {e!s}"
            )  # noqa: B904
        except Exception as e:
            raise

    @staticmethod
    def make_checksum(data: str) -> str:
        if not data:
            return ""
        total = 0
        for i in range(0, len(data), 2):
            s = data[i : i + 2]
            total += int(s, 16)
        mod = total % 256
        hex_result = hex(mod)[2:].upper().zfill(2)
        return hex_result
