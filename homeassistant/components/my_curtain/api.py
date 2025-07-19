"""My Curtain API客户端."""

import binascii
import logging
import asyncio
import aiohttp

_LOGGER = logging.getLogger(__name__)


class MyCurtainApiClient:
    """API客户端."""

    def __init__(
        self,
        username: str,
        password: str,
    ) -> None:
        """初始化API客户端."""
        _LOGGER.info("初始化API客户端" + username + "#" + password)  # noqa: G003
        self._username = username
        self._password = password
        self._devices = []  # 初始化为空列表，将从API获取
        self._token = None  # 存储获取到的Token
        self._auth_url = "https://wly87bcr9j.execute-api.cn-north-1.amazonaws.com.cn/prod/assistantLogin"
        self._device_url = " https://wly87bcr9j.execute-api.cn-north-1.amazonaws.com.cn/prod/findDeviceByAccount"  # 设备列表URL
        self._command_url = "https://wly87bcr9j.execute-api.cn-north-1.amazonaws.com.cn/prod/assistantSendOrder"  # 命令发送URL

    async def authenticate(self) -> None:
        """验证用户身份，通过实际URL请求，获取Token."""
        # 构建请求参数
        data = {"account": self._username, "password": self._password}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self._auth_url, json=data) as response:
                    result = await response.json()
                    # _LOGGER.info(f"响应 JSON 数据: {result}")  # noqa: G004
                    # 检查响应状态码
                    if result.get("code") != 200:
                        raise ValueError(f"认证请求失败，状态码: {result.get('code')}")
                    # 解析响应JSON获取token
                    result_data = result.get("data")
                    token = result_data.get("token")
                    if not token:
                        raise ValueError("认证响应中未包含Token")
                    # 存储Token
                    self._token = token
        except aiohttp.ClientError as e:
            raise ValueError(f"网络请求错误: {str(e)}")
        await asyncio.sleep(0.5)  # 模拟网络延迟

    async def get_devices(self) -> list[dict]:
        """获取设备列表"""
        # 如果没有token，先进行认证
        if not self._token:
            await self.authenticate()

        # 构建请求头，添加token
        headers = {
            "token": f"{self._token}"  # 假设使用Bearer token，根据实际API调整
        }

        # 构建请求体，添加account参数
        data = {}

        try:
            async with aiohttp.ClientSession() as session:  # noqa: SIM117
                # 修改为POST请求，传递JSON格式的account参数
                async with session.post(
                    self._device_url, headers=headers, json=data
                ) as response:
                    result = await response.json()
                    # _LOGGER.info(f"设备列表响应 JSON 数据: {result}")  # noqa: G004
                    # 检查响应状态码
                    if result.get("code") != 200:
                        raise ValueError(
                            f"获取设备列表失败，状态码: {result.get('code')}"
                        )

                    # 正确解析嵌套的列表结构
                    devices_data = []
                    data_list = result.get("data", {}).get("list", [])

                    # 检查列表是否为空
                    if data_list and len(data_list) > 0:
                        # 获取列表中的第一个元素
                        first_item = data_list[0]
                        # 从第一个元素中获取设备列表
                        if isinstance(first_item, dict):
                            devices_data = first_item.get("list", [])

                    # 转换为内部格式
                    self._devices = self._parse_devices(devices_data)
        except aiohttp.ClientError as e:
            raise ValueError(f"获取设备列表网络请求错误: {str(e)}")
        await asyncio.sleep(0.3)  # 模拟延迟
        return self._devices

    def _parse_devices(self, devices_data: list[dict]) -> list[dict]:
        """将API返回的设备数据解析为内部格式"""
        parsed_devices = []
        for device in devices_data:
            # 根据实际API返回的数据结构调整解析逻辑
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
                # 保留原始数据以便调试
                # "raw_data": device,
            }
            parsed_devices.append(parsed_device)
        return parsed_devices

    async def set_device_position(self, device_id: str, position: int) -> bool:
        """设置设备位置"""
        _LOGGER.info(f"更新设备 {device_id} 到位置 {position}")
        for device in self._devices:
            if device["id"] == device_id:
                device["state"] = (
                    "opening" if position > device["position"] else "closing"
                )
                device["position"] = position
                # 异步执行设备操作完成逻辑
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
        """发送请求修改设备的位置."""
        # 如果没有token，先进行认证
        if not self._token:
            await self.authenticate()

        # 构建请求头，添加token
        headers = {
            "token": f"{self._token}"  # 假设使用Bearer token，根据实际API调整
        }

        # 生成控制命令
        byte_data = device_id.encode("utf-8")  # 转换为字节
        hex_str = binascii.hexlify(byte_data).decode("ascii")  # 转换为十六进制字符串

        # 修正：将position转换为两位十六进制字符串
        hex_height = f"{position:02X}"

        # 修正：构建完整的res字符串并计算其长度
        res = f"01 {hex_str} 02 {hex_height}"
        res_bytes = res.replace(" ", "").encode("ascii")
        length = len(res_bytes) // 2

        # 修正：将长度转换为两位十六进制字符串
        hex_length = f"{length:02X}"

        # 构建完整命令
        order = f"4A640040FF{hex_length}00{res.replace(' ', '')}"

        # 计算校验和并添加到命令末尾
        checksum = self.make_checksum(order)
        order = order + checksum

        _LOGGER.info(f"生成的命令: {order}")  # noqa: G004

        # 构建请求体
        data = {"deviceId": subID, "order": order}

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    self._command_url, headers=headers, json=data
                ) as response1,
            ):
                result = await response1.json()
                # 检查响应状态码
                if result.get("code") != 200:
                    raise ValueError(  # noqa: TRY301
                        f"发送指令失败，状态码: {result.get('code')}, 响应: {result}"
                    )
                _LOGGER.info(
                    f"成功发送命令到设备 {device_id}，目标位置: {position}"  # noqa: G004
                )
        except aiohttp.ClientError as e:
            _LOGGER.error(f"发送设备命令网络请求错误: {e!s}")  # noqa: G004
            raise ValueError(f"发送设备命令网络请求错误: {e!s}")  # noqa: B904
        except Exception as e:
            _LOGGER.error(f"发送设备命令发生未知错误: {str(e)}")
            raise

    @staticmethod
    def make_checksum(data: str) -> str:
        """计算校验和"""
        if not data:
            return ""
        total = 0
        # 按每两个字符分割字符串并累加对应十六进制数值
        for i in range(0, len(data), 2):
            s = data[i : i + 2]
            total += int(s, 16)
        # 对总和取模256
        mod = total % 256
        # 转换为十六进制字符串并补零至两位
        hex_result = hex(mod)[2:].upper().zfill(2)
        return hex_result
