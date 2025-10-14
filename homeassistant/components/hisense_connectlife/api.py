"""API client for Hisense ConnectLife."""
from __future__ import annotations

import logging
import json
import time
import uuid
import hashlib
import base64
from typing import Any, Dict, List, Callable
import zoneinfo
from datetime import datetime, timedelta
import pytz
import re
import hmac
import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    API_BASE_URL,
    API_DEVICE_LIST,
    API_GET_PROPERTY_LTST,
    API_QUERY_STATIC_DATA,
    API_DEVICE_CONTROL,
    StatusKey,
    CLIENT_ID,
    CLIENT_SECRET,
    DeviceType,
    DEVICE_TYPES, DOMAIN, API_GET_HOUR_POWER, API_SELF_CHECK,
)
from .devices.base import DeviceAttribute
from .oauth2 import OAuth2Session
from .websocket import HisenseWebSocket
from .devices import get_device_parser, BaseBeanParser, BaseDeviceParser, SplitWater035699Parser, Humidity007Parser, \
    Split006299Parser
from .models import DeviceInfo, HisenseApiError

_LOGGER = logging.getLogger(__name__)

class HisenseApiClient:
    """Hisense API client."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: OAuth2Session,
    ) -> None:
        """Initialize API client."""
        self.failed_data: dict[str, list[str]] = {}
        self.hass = hass
        self.oauth_session = oauth_session
        self.session = oauth_session.session
        self._devices: dict[str, DeviceInfo] = {}
        self.parsers: dict[str, BaseDeviceParser] = {}
        self.static_data: dict[str, Any] = {}
        self._status_callbacks: dict[str, Callable[[dict[str, Any]], None]] = {}
        self._websocket: HisenseWebSocket | None = None
        self._source_id: str | None = None

        hass.data[f"{DOMAIN}.translations"] = {}
        supported_langs = ["en", "zh-Hans"]
        for lang in supported_langs:
            try:
                # # 更新 async_get_translations 的调用
                # translations = await async_get_translations(
                #     hass,
                #     language=lang,
                #     category="sensor",
                #     integrations=DOMAIN  # 正确参数
                # )
                if lang == "zh-Hans":
                    hass.data[f"{DOMAIN}.translations"][lang] = {
                        "indoor_temperature": "室内温度",
                        "power_consumption": "能耗",
                        "indoor_humidity": "室内湿度",
                        "in_water_temp": "进水口温度",
                        "out_water_temp": "出水口温度",
                        "f_zone1water_temp1": "温区1实际值",
                        "f_zone2water_temp2": "温区2实际值",
                        "f_e_intemp": "室内温度传感器故障",
                        "f_e_incoiltemp": "室内盘管温度传感器故障",
                        "f_e_inhumidity": "室内湿度传感器故障",
                        "f_e_infanmotor": "室内风机电机运转异常故障",
                        "f_e_arkgrille": "柜机格栅保护告警",
                        "f_e_invzero": "室内电压过零检测故障",
                        "f_e_incom": "室内外通信故障",
                        "f_e_indisplay": "室内控制板与显示板通信故障",
                        "f_e_inkeys": "室内控制板与按键板通信故障",
                        "f_e_inwifi": "WIFI控制板与室内控制板通信故障",
                        "f_e_inele": "室内控制板与室内电量板通信故障",
                        "f_e_ineeprom": "室内控制板EEPROM出错",
                        "f_e_outeeprom": "室外EEPROM出错",
                        "f_e_outcoiltemp": "室外盘管温度传感器故障",
                        "f_e_outgastemp": "排气温度传感器故障",
                        "f_e_outtemp": "室外环境温度传感器故障",
                        "f_e_push": "推送故障",
                        "f_e_waterfull": "水满报警",
                        "f_e_upmachine": "室内（上部）直流风机电机运转异常故障",
                        "f_e_dwmachine": "室外（下部）直流风机电机运转异常故障",
                        "f_e_filterclean": "过滤网清洁告警",
                        "f_e_wetsensor": "湿敏传感器故障",
                        "f_e_tubetemp": "管温传感器故障",
                        "f_e_temp": "室温传感器故障",
                        "f_e_pump": "水泵故障",
                        "f_e_exhaust_hightemp": "排气温度过高",
                        "f_e_high_pressure": "高压故障",
                        "f_e_low_pressure": "低压故障",
                        "f_e_wire_drive": "通信故障",
                        "f_e_coiltemp": "盘管温度传感器故障",
                        "f_e_env_temp": "环境温度传感器故障",
                        "f_e_exhaust": "排气温度传感器故障",
                        "f_e_inwater": "进水温度传感器故障",
                        "f_e_water_tank": "水箱温度传感器故障",
                        "f_e_return_air": "回气温度传感器故障",
                        "f_e_outwater": "出水温度传感器故障",
                        "f_e_solar_temperature": "太阳能温度传感器故障",
                        "f_e_compressor_overload": "压缩机过载",
                        "f_e_excessive_current": "电流过大",
                        "f_e_fan_fault": "风机故障",
                        "f_e_displaycom_fault": "显示板通信故障",
                        "f_e_upwatertank_fault": "水箱上部温度传感器故障",
                        "f_e_downwatertank_fault": "水箱下部温度传感器故障",
                        "f_e_suctiontemp_fault": "吸气温度传感器故障",
                        "f_e_e2data_fault": "EEPROM数据故障",
                        "f_e_drivecom_fault": "驱动板通信故障",
                        "f_e_drive_fault": "驱动板故障",
                        "f_e_returnwatertemp_fault": "回水温度传感器故障",
                        "f_e_clockchip_fault": "时钟芯片故障",
                        "f_e_eanode_fault": "电子阳极故障",
                        "f_e_powermodule_fault": "电量模块故障",
                        "f_e_fan_fault_tip": "外风机故障",
                        "f_e_pressuresensor_fault_tip": "压力传感器故障",
                        "f_e_tempfault_solarwater_tip": "太阳能水温感温故障",
                        "f_e_tempfault_mixedwater_tip": "混水感温故障",
                        "f_e_tempfault_balance_watertank_tip": "平衡水箱感温故障",
                        "f_e_tempfault_eheating_outlet_tip": "内置电加热出水感温故障",
                        "f_e_tempfault_refrigerant_outlet_tip": "冷媒出口温感故障",
                        "f_e_tempfault_refrigerant_inlet_tip": "冷媒进口温感故障",
                        "f_e_inwaterpump_tip": "内置水泵故障",
                        "f_e_outeeprom_tip": "外机EEPROM故障",
                        "quiet_mode": "静音模式",
                        "rapid_mode": "快速制热/制冷",
                        "8heat_mode": "8度制热模式",
                        "eco_mode": "节能",
                        "fan_speed_自动": "自动风",
                        "fan_speed_中风": "中速",
                        "fan_speed_高风": "高速",
                        "fan_speed_低风": "低速",
                        "t_zone1water_settemp1": "1温区设置值",
                        "t_zone2water_settemp2": "2温区设置值",
                        "STATE_CONTINUOUS": "持续",
                        "STATE_NORMAL": "手动",
                        "STATE_AUTO": "自动",
                        "STATE_DRY": "干衣",
                        "STATE_OFF": "关闭",
                        "STATE_ELECTRIC": "电加热",
                        "STATE_DUAL_MODE": "双能模式",
                        "STATE_DUAL_MODE_": "双能",
                        "STATE_DUAL_1": "快",
                        "STATE_DUAL_1_": "双能1",
                        "STATE_HEAT": "制热",
                        "STATE_COOL": "制冷",
                        "STATE_HOT_WATER_COOL": "制冷+生活热水",
                        "STATE_HOT_WATER_AUTO": "自动+生活热水",
                        "STATE_HOT_WATER": "仅生活热水",
                        "STATE_HOT_WATER_HEAT": "制热+生活热水",
                        "fan_speed_ultra_low": "中低",
                        "fan_speed_ultra_high": "中高",
                        "fan_speed_low": "低",
                        "fan_speed_high": "高",
                    }
                else:
                    hass.data[f"{DOMAIN}.translations"][lang] = {
                        "indoor_temperature": "Indoor Temperature",
                        "power_consumption": "Power Consumption",
                        "indoor_humidity": "Indoor Humidity",
                        "in_water_temp": "In Water Temp",
                        "out_water_temp": "Out Water Temp",
                        "f_zone1water_temp1": "Zone 1 Actual Temp",
                        "f_zone2water_temp2": "Zone 2 Actual Temp",
                        "f_e_intemp": "Indoor Temperature Sensor Fault",
                        "f_e_incoiltemp": "Indoor Coil Temperature Sensor Fault",
                        "f_e_inhumidity": "Indoor Humidity Sensor Fault",
                        "f_e_infanmotor": "Indoor Fan Motor Fault",
                        "f_e_arkgrille": "Cabinet Grill Protection Alert",
                        "f_e_invzero": "Indoor Zero Voltage Detection Fault",
                        "f_e_incom": "Indoor-Outdoor Communication Fault",
                        "f_e_indisplay": "Indoor Display Board Communication Fault",
                        "f_e_inkeys": "Indoor Key Panel Communication Fault",
                        "f_e_inwifi": "WiFi Control Board Communication Fault",
                        "f_e_inele": "Indoor Power Board Communication Fault",
                        "f_e_ineeprom": "Indoor EEPROM Error",
                        "f_e_outeeprom": "Outdoor EEPROM Error",
                        "f_e_outcoiltemp": "Outdoor Coil Temperature Sensor Fault",
                        "f_e_outgastemp": "Exhaust Temperature Sensor Fault",
                        "f_e_outtemp": "Outdoor Ambient Temperature Sensor Fault",
                        "f_e_push": "Push Notification Fault",
                        "f_e_waterfull": "Tank Full Alert",
                        "f_e_upmachine": "Upper Indoor Fan Fault",
                        "f_e_dwmachine": "Lower Outdoor Fan Fault",
                        "f_e_filterclean": "Filter Clean Alert",
                        "f_e_wetsensor": "Moisture Sensor Fault",
                        "f_e_tubetemp": "Pipe Temperature Sensor Fault",
                        "f_e_temp": "Room Temperature Sensor Fault",
                        "f_e_pump": "Pump Fault",
                        "f_e_exhaust_hightemp": "Exhaust Overheating",
                        "f_e_high_pressure": "High Pressure Fault",
                        "f_e_low_pressure": "Low Pressure Fault",
                        "f_e_wire_drive": "Communication Fault",
                        "f_e_coiltemp": "Coil Temperature Sensor Fault",
                        "f_e_env_temp": "Environmental Temperature Sensor Fault",
                        "f_e_exhaust": "Exhaust Temperature Sensor Fault",
                        "f_e_inwater": "Inlet Water Temperature Sensor Fault",
                        "f_e_water_tank": "Tank Temperature Sensor Fault",
                        "f_e_return_air": "Return Air Temperature Sensor Fault",
                        "f_e_outwater": "Outlet Water Temperature Sensor Fault",
                        "f_e_solar_temperature": "Solar Temperature Sensor Fault",
                        "f_e_compressor_overload": "Compressor Overload",
                        "f_e_excessive_current": "Overcurrent",
                        "f_e_fan_fault": "Fan Fault",
                        "f_e_displaycom_fault": "Display Board Communication Fault",
                        "f_e_upwatertank_fault": "Upper Tank Temperature Sensor Fault",
                        "f_e_downwatertank_fault": "Lower Tank Temperature Sensor Fault",
                        "f_e_suctiontemp_fault": "Suction Temperature Sensor Fault",
                        "f_e_e2data_fault": "EEPROM Data Fault",
                        "f_e_drivecom_fault": "Drive Board Communication Fault",
                        "f_e_drive_fault": "Drive Board Fault",
                        "f_e_returnwatertemp_fault": "Return Water Temperature Sensor Fault",
                        "f_e_clockchip_fault": "Clock Chip Fault",
                        "f_e_eanode_fault": "Anode Fault",
                        "f_e_powermodule_fault": "Power Module Fault",
                        "f_e_fan_fault_tip": "Outdoor Fan Fault",
                        "f_e_pressuresensor_fault_tip": "Pressure Sensor Fault",
                        "f_e_tempfault_solarwater_tip": "Solar Water Sensor Fault",
                        "f_e_tempfault_mixedwater_tip": "Mixed Water Sensor Fault",
                        "f_e_tempfault_balance_watertank_tip": "Balance Tank Sensor Fault",
                        "f_e_tempfault_eheating_outlet_tip": "Electric Heater Outlet Sensor Fault",
                        "f_e_tempfault_refrigerant_outlet_tip": "Refrigerant Outlet Sensor Fault",
                        "f_e_tempfault_refrigerant_inlet_tip": "Refrigerant Inlet Sensor Fault",
                        "f_e_inwaterpump_tip": "Pump Fault",
                        "f_e_outeeprom_tip": "Outdoor EEPROM Fault",
                        "quiet_mode": "Quiet Mode",
                        "rapid_mode": "Fast Heating/Cooling",
                        "8heat_mode": "8 Heat Mode",
                        "eco_mode": "Eco",
                        "fan_speed_自动": "Auto speed",
                        "fan_speed_中风": "Medium",
                        "fan_speed_高风": "High",
                        "fan_speed_低风": "Low",
                        "t_zone1water_settemp1": "Zone 1 Set Temp",
                        "t_zone2water_settemp2": "Zone 2 Set Temp",
                        "STATE_CONTINUOUS": "Continuous",
                        "STATE_NORMAL": "Manual",
                        "STATE_AUTO": "Auto",
                        "STATE_DRY": "Clothes dry",
                        "STATE_OFF": "Off",
                        "STATE_ELECTRIC": "Electric heating",
                        "STATE_DUAL_MODE": "Dual Mode",
                        "STATE_DUAL_MODE_": "Boost",
                        "STATE_DUAL_1": "Fast",
                        "STATE_DUAL_1_": "Boost1",
                        "STATE_HEAT": "Heat",
                        "STATE_COOL": "Cool",
                        "STATE_HOT_WATER_COOL": "Cool & DHW",
                        "STATE_HOT_WATER_AUTO": "Auto & DHW",
                        "STATE_HOT_WATER": "only DHW",
                        "STATE_HOT_WATER_HEAT": "Heat & DHW",
                        "fan_speed_ultra_low": "Ultra Low",
                        "fan_speed_ultra_high": "Ultra High",
                        "fan_speed_low": "Low",
                        "fan_speed_high": "High",
                    }
                _LOGGER.debug("Loaded translations for %s: %s", lang)
            except Exception as e:
                _LOGGER.error(f"Failed to load translations for {lang}: {e}")
    def calculate_signature_sha256(self, secret, params):
        return base64.b64encode(hmac.new(bytes(secret, 'utf-8'), bytes(params, 'utf-8'), hashlib.sha256).digest()).decode('utf-8')

    def calculate_body_digest_sha256(self, body):
        if body and len(body) > 0:
            return base64.b64encode(hashlib.sha256(json.dumps(body).encode('utf-8')).digest()).decode('utf-8')
        return '47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='

    def calculate_GMT_date(self):
        GMT_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
        # return 'Fri, 24 Jan 2025 06:50:51 GMT'
        return datetime.now(pytz.utc).strftime(GMT_FORMAT)

    def calculate_path(self, url):
        return re.sub(r'^https://[^/]*', '', url)

    def calaulate_encrypt(self, secret_key, method, path, gmt_date, header):
        return f'{secret_key}\n{method} {path}\ndate: {gmt_date}\n{header}\n'
        
    def _generate_uuid(self) -> str:
        """Generate a UUID string without dashes."""
        return f"{uuid.uuid1().hex}{int(time.time() * 1000)}"

    def _get_source_id(self) -> str:
        """Get or generate source ID."""
        if not self._source_id:
            uuid_str = self._generate_uuid()
            md5_uuid = hashlib.md5(uuid_str.encode()).hexdigest()
            self._source_id = f'td001002000{md5_uuid}'
        return self._source_id


    async def _api_request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        """Make an API request."""
        _LOGGER.debug("Making API request: %s %s", method, endpoint)
        try:
            # Ensure token is valid
            await self.oauth_session.async_ensure_token_valid()
            
            # Get system parameters
            params = await self._get_system_parameters()
            _LOGGER.debug("System parameters: %s", json.dumps(params, indent=2))
            
            # Merge with provided data if any
            request_data = data if data else {}
            _LOGGER.debug("Request data: %s", request_data)
            # Add system parameters at the root level
            request_data.update(params)
            
            # Log final request data
            _LOGGER.debug("Final request data: %s", json.dumps(request_data, indent=2))
            
            if headers is None:
                headers = {}
            # Add accessToken to headers only for GET requests
            if method.upper() == "GET":
                headers.update({
                    "accessToken": await self.oauth_session.async_get_access_token()
                })
            
            # Build full URL
            url = f"{API_BASE_URL}{endpoint}"
            
            # For GET requests, append parameters to URL
            if method.upper() == "GET":
                # Convert parameters to URL query string
                query_params = []
                # Create a copy of request_data and remove accessToken
                url_params = request_data.copy()
                url_params.pop("accessToken", None)
                
                for key, value in url_params.items():
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    query_params.append(f"{key}={value}")
                query_string = "&".join(query_params)
                url = f"{url}?{query_string}"
                request_data = None  # Clear request body for GET
            

            app_id = CLIENT_ID
            app_secret = CLIENT_SECRET
            header_key = 'hi-params-encrypt'
            gmt_date = self.calculate_GMT_date()
            params = self.calaulate_encrypt(
                app_id,
                method,
                self.calculate_path(url),
                gmt_date,
                f'{header_key}: {app_id}'
            )
            _LOGGER.debug(f'params: \n{params}')

            sign = self.calculate_signature_sha256(
                app_secret,
                params,
            )
            _LOGGER.debug(f'sign: {sign}')
            # Prepare headers
            headers.update({
                f'{header_key}': f'{app_id}',
                'Date': gmt_date,
                'Authorization': f'Signature signature="{sign}", keyId="{app_id}",algorithm="hmac-sha256", headers="@request-target date {header_key}"',
                'Content-Type': 'application/json',
                'Digest': f'SHA-256={self.calculate_body_digest_sha256(request_data)}'
            })

            # Log request details
            _LOGGER.debug("Request details:")
            _LOGGER.debug("URL: %s", url)
            _LOGGER.debug("Method: %s", method)
            _LOGGER.debug("Headers: %s", {
                k: v if k.lower() != 'accessToken' else '***' 
                for k, v in headers.items()
            })
            if request_data:
                _LOGGER.debug("Body: %s", json.dumps(request_data, indent=2))
            
            # Convert request_data to JSON string for POST requests
            data = json.dumps(request_data) if request_data else None
            
            async with self.session.request(
                method, 
                url, 
                data=data,
                headers=headers
            ) as resp:
                response_text = await resp.text()
                
                # Log response details
                _LOGGER.debug("Response details:")
                _LOGGER.debug("Status: %d", resp.status)
                _LOGGER.debug("Headers: %s", dict(resp.headers))
                _LOGGER.debug("Body: %s", response_text)
                
                # if resp.status == 401:
                #     _LOGGER.warning("Token expired, refreshing...")
                #     await self.oauth_session.async_ensure_token_valid()
                #     # Retry the request once
                #     return await self._api_request(method, endpoint, data, headers)
                    
                resp.raise_for_status()
                
                try:
                    response_data = json.loads(response_text)
                except json.JSONDecodeError as err:
                    _LOGGER.error("Failed to parse response as JSON: %s", err)
                    raise HisenseApiError(f"Invalid JSON response: {response_text}")
                    
                if not isinstance(response_data, dict):
                    raise HisenseApiError(f"Unexpected response format: {response_data}")
                    
                if response_data.get("resultCode") != 0:
                    error_msg = response_data.get("msg", "Unknown error")
                    raise HisenseApiError(f"API error: {error_msg}")
                # _LOGGER.debug("API response: %s", json.dumps(response_data, indent=2))    
                return response_data
                
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP request failed: %s", err)
            raise HisenseApiError(f"HTTP request failed: {err}")
        except Exception as err:
            _LOGGER.error("API request failed: %s", err)
            raise HisenseApiError(f"API request failed: {err}")

    async def _get_system_parameters(self) -> dict[str, Any]:
        """Generate system parameters."""
        # Get current timestamp
        timestamp = int(time.time() * 1000)
        
        # Generate random string
        uuid_str = str(uuid.uuid1()) + str(timestamp)
        random_str = hashlib.md5(uuid_str.encode()).hexdigest()
        
        # Get timezone
        timezone = str(self.hass.config.time_zone or "UTC")
        
        params = {
            "timeStamp": str(timestamp),
            "version": "8.1",
            "languageId": "1",
            "timezone": timezone,
            "randStr": random_str,
            "appId": CLIENT_ID,
            "sourceId": self._get_source_id(),
            "platformId": 5,  # Adding platformId as required by the API
        }
        
        # Add access token if available
        access_token = await self.oauth_session.async_get_access_token()
        if access_token:
            params["accessToken"] = access_token
            
        return params

    @property
    async def async_get_devices(self) -> dict[str, DeviceInfo]:
        """Get list of devices with their current status."""
        _LOGGER.debug("Fetching device list with status")
        try:
            # Get device list with status from /clife-svc/pu/get_device_status_list
            response = await self._api_request("GET", API_DEVICE_LIST)
            if not response:
                return {}
            
            devices = {}
            device_list = response.get("deviceList", [])
            _LOGGER.debug("Found %d devices in response", len(device_list))
            
            for device_data in device_list:
                deviceTypeCode = device_data.get("deviceTypeCode")
                deviceFeatureCode = device_data.get("deviceFeatureCode")
                deviceFeatureName = device_data.get("deviceFeatureName")
                try:
                    device = DeviceInfo(device_data)
                    supported_device_types = ["009", "008", "007", "006", "016", "035"]
                    if deviceTypeCode in supported_device_types:
                        devices[device.device_id] = device
                        self._devices[device.device_id] = device
                        _LOGGER.debug(
                            "Added supported device:\n%s",
                            device.debug_info()
                        )

                        response = await self.async_get_property_list(deviceTypeCode,deviceFeatureCode)
                        if "99" in deviceFeatureCode:
                            re = await self.async_query_static_data(device.puid)
                            _LOGGER.debug("Static data for re %s: %s", deviceFeatureCode,
                                          re)
                            self.static_data[device.device_id] = re.get("status")
                        propertyList = response.get("status")
                        _LOGGER.debug("Static data for propertyList %s: %s", deviceFeatureCode,
                                      propertyList)

                        # 使用 get_device_parser 获取 parser 类
                        parser_class = get_device_parser(deviceTypeCode, deviceFeatureCode)
                        _LOGGER.debug("Static data for parser class %s: %s: %s", deviceTypeCode, deviceFeatureCode,
                                      parser_class)

                        # 手动实例化 parser
                        parser = parser_class()
                        _LOGGER.debug("Static data for parser instance %s: %s: %s", deviceTypeCode, deviceFeatureCode, parser)

                        if isinstance(parser, BaseBeanParser):
                            filtered_parser = self.create_filtered_parser(parser, propertyList)
                            self.parsers[device.device_id] =filtered_parser
                        elif isinstance(parser, SplitWater035699Parser):
                            if isinstance(parser, SplitWater035699Parser):
                                # 判断有没有温区2
                                if device.status.get("f_zone2_select") == "0":
                                    # 创建一个新的 parser 对象
                                    new_parser = SplitWater035699Parser()

                                    # 复制除了 f_zone2water_temp2 和 t_zone2water_settemp2 之外的所有字段
                                    for key, value in parser.attributes.items():
                                        if key not in ["f_zone2water_temp2", "t_zone2water_settemp2"]:
                                            new_parser.attributes[key] = value
                                    parser = new_parser

                            self.parsers[device.device_id] = parser
                            _LOGGER.debug("三联供设备解析字段 %s:%s",
                                          device.device_id,
                                          self.parsers.get(device.device_id).attributes)
                        elif isinstance(parser, Humidity007Parser):
                            filtered_parser = self.create_humidity_parser(parser, propertyList)
                            self.parsers[device.device_id] = filtered_parser
                        elif isinstance(parser, Split006299Parser):
                            self.parsers[device.device_id] = parser
                        else:
                            _LOGGER.error("Parser is not an instance of BaseBeanParser")
                            return


                        #判断是否有电量功能
                        has_power = False
                        property_keys = {prop.get('propertyKey') for prop in propertyList if 'propertyKey' in prop}
                        if deviceTypeCode == "009":#分体空调
                            if "99" not in deviceFeatureCode:
                                # _LOGGER.debug("009Ddevice feature code is :%s,and status = :%s", deviceFeatureCode,
                                #               property_keys)
                                target_keys = {'f_power_display', 'f_cool_qvalue', 'f_heat_qvalue'}
                                if target_keys & property_keys:
                                    has_power = True
                            else:
                                # _LOGGER.debug("009Ddevice feature code is :%s,and static_data = :%s",deviceFeatureCode,self.static_data[device.device_id])
                                if self.static_data[device.device_id].get("Power_function") == "1" or self.static_data.get("f_cool_or_heat_qvalue") == "1":
                                    has_power = True
                        elif deviceTypeCode in ['008','006']:#窗机 移动空调
                            if "99" not in deviceFeatureCode:
                                # _LOGGER.debug("008 006Ddevice feature code is :%s,and status = :%s", deviceFeatureCode,
                                #               property_keys)
                                if 'f_power_display' in property_keys:
                                    has_power = True
                            else:
                                # _LOGGER.debug("008 006Ddevice feature code is :%s,and static_data = :%s",deviceFeatureCode,self.static_data[device.device_id])
                                if self.static_data[device.device_id].get("Power_function") == "1" :
                                    has_power = True

                        elif deviceTypeCode == "007":#除湿机
                            if "99" not in deviceFeatureCode:
                                # _LOGGER.debug("007Ddevice feature code is :%s,and status = :%s", deviceFeatureCode,
                                #               property_keys)
                                if 'f_power_display' in property_keys:
                                    has_power = True
                            else:
                                # _LOGGER.debug("007Ddevice feature code is :%s,and static_data = :%s",deviceFeatureCode,self.static_data[device.device_id])
                                if self.static_data[device.device_id].get("Power_function") == "1" :
                                    has_power = True
                        else:
                            # _LOGGER.debug("Ddevice feature code is :%s,and status = :%s", deviceFeatureCode,
                            #               property_keys)
                            target_keys = {'f_power_display', 'f_cool_qvalue', 'f_heat_qvalue'}
                            if target_keys & property_keys:
                                has_power = True

                        # else:
                        #     if "99" not in deviceFeatureCode:
                        #         _LOGGER.debug("Ddevice feature code is :%s,and status = :%s and has_power:%s", deviceFeatureCode,
                        #                       device.status,"f_power_display" in device.status)
                        #         if "f_power_display" in device.status:
                        #             has_power = True
                        #     else:
                        #         _LOGGER.debug("Ddevice feature code is :%s,and static_data = :%s",deviceFeatureCode,self.static_data)
                        #         if self.static_data.get("Power_function") == 1 or self.static_data.get("Power_detection") == 1:
                        #             has_power = True

                        if has_power:
                            current_date = datetime.now().date().isoformat()
                            power_response = await self.async_get_hour_power(current_date, device.puid)
                            power = power_response.get("status")
                            current_time = datetime.now()
                            previous_hour = (current_time - timedelta(hours=1)).hour
                            previous_hour_str = str(previous_hour)
                            value = power.get(previous_hour_str)
                            _LOGGER.debug("Static data for power_response %s: %s ，当前时间：%s ，上个小时的时间：%s ，上个小时的电量：%s", deviceFeatureCode,
                                          power_response, current_time.hour,previous_hour_str, value)
                            _LOGGER.debug("Static data for device.status %s: %s", deviceFeatureCode,
                                          device.status)
                            device.status["f_power_consumption"] = value
                            _LOGGER.debug("Static data for f_power_consumption %s: %s", deviceFeatureCode,
                                          device.status)
                        else:
                            self.parsers[device.device_id].remove_attribute("f_power_consumption")
                        _LOGGER.debug("Static data for device.status %s: %s", deviceFeatureCode,
                                          device.status)
                        #填充故障列表
                        data = await self.async_api_self_check("1", device.puid)
                        failed_data = data.get("status", {}).get("selfCheckFailedList")
                        _LOGGER.debug(
                            "Static data for self_check %s: 完整自检数据 %s: 单纯故障数据 %s",
                            deviceFeatureCode,
                            data, failed_data)
                        if failed_data:
                            failed_list = [item.get("statusKey") for item in failed_data]
                            # self.failed_data[device.device_id] = failed_list
                            device.failed_data = failed_list
                            _LOGGER.debug(
                                "Static data for failed_list %s: 完整自检数据 %s: 单纯故障数据 %s: 取出所有的key %s",
                                deviceFeatureCode,
                                data, failed_data, failed_list)
                    else:
                        _LOGGER.warning(
                            "Skipping unsupported device type:\n%s",
                            device.debug_info()
                        )
                except Exception as device_err:
                    _LOGGER.error(
                        "Error processing device data: %s - %s",
                        device_data,
                        device_err
                    )

            return devices
            
        except Exception as err:
            _LOGGER.error("Failed to fetch devices: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}")

    @staticmethod
    def create_humidity_parser(base_parser: Humidity007Parser, propertyList: list) -> Humidity007Parser:
        # 获取Humidity007Parser的attributes字典
        original_attributes = base_parser.attributes

        # 确保 original_attributes 是一个字典
        if not isinstance(original_attributes, dict):
            _LOGGER.error("original_attributes is not a dictionary: %s", original_attributes)
            return Humidity007Parser()

        # 提取 propertyKey 形成一个新的列表
        property_keys = [prop.get('propertyKey') for prop in propertyList if
                         isinstance(prop, dict) and 'propertyKey' in prop]

        # 调试 property_keys 的内容
        _LOGGER.debug("property_keys content: %s", property_keys)

        # 确保 property_keys 是一个可迭代的可哈希类型
        if not isinstance(property_keys, (list, set)):
            _LOGGER.error("property_keys is not a list or set: %s", property_keys)
            return Humidity007Parser()

        # 确保 property_keys 中的元素是可哈希的类型
        if any(not isinstance(item, (str, int, float, tuple)) for item in property_keys):
            _LOGGER.error("property_keys contains unhashable types: %s", property_keys)
            return Humidity007Parser()

        # 创建一个新的attributes字典，只包含交集中的DeviceAttribute
        filtered_attributes = {}
        for key in property_keys:
            if key in original_attributes:
                attribute = original_attributes[key]
                # 更新 value_range
                for prop in propertyList:
                    if prop.get('propertyKey') == key:
                        property_value_list = prop.get('propertyValueList')
                        if property_value_list:
                            attribute.value_range = property_value_list
                            break

                # 过滤 value_map
                if attribute.value_map:
                    # 将 property_value_list_keys 转换为集合
                    property_value_list_keys = set(property_value_list.split(','))

                    # 确保 value_map_keys 是一个集合
                    value_map_keys = set(attribute.value_map.keys())

                    # 使用 intersection 方法计算交集
                    filtered_value_map = {k: attribute.value_map[k] for k in
                                          value_map_keys.intersection(property_value_list_keys)}
                    attribute.value_map = filtered_value_map

                filtered_attributes[key] = attribute

        _LOGGER.debug("除湿机filtered_attributes content: %s", filtered_attributes)
        # 创建一个新的Humidity007Parser对象，并将filtered_attributes赋值给它的attributes属性
        new_parser = Humidity007Parser()
        _LOGGER.debug("除湿机Static data for filtered_parser111111 %s",
                      new_parser.attributes)
        new_parser._attributes = filtered_attributes
        _LOGGER.debug("除湿机Static data for filtered_parser222222 %s",
                      new_parser.attributes)
        return new_parser

    @staticmethod
    def create_filtered_parser(base_parser: BaseDeviceParser, propertyList: list) -> BaseBeanParser:
        # 获取BaseBeanParser的attributes字典
        original_attributes = base_parser.attributes

        # 确保 original_attributes 是一个字典
        if not isinstance(original_attributes, dict):
            _LOGGER.error("original_attributes is not a dictionary: %s", original_attributes)
            return BaseBeanParser()

        # 提取 propertyKey 形成一个新的列表
        property_keys = [prop.get('propertyKey') for prop in propertyList if
                         isinstance(prop, dict) and 'propertyKey' in prop]

        # 调试 property_keys 的内容
        _LOGGER.debug("property_keys content: %s", property_keys)

        # 确保 property_keys 是一个可迭代的可哈希类型
        if not isinstance(property_keys, (list, set)):
            _LOGGER.error("property_keys is not a list or set: %s", property_keys)
            return BaseBeanParser()

        # 确保 property_keys 中的元素是可哈希的类型
        if any(not isinstance(item, (str, int, float, tuple)) for item in property_keys):
            _LOGGER.error("property_keys contains unhashable types: %s", property_keys)
            return BaseBeanParser()

        # 创建一个新的attributes字典，只包含交集中的DeviceAttribute
        filtered_attributes = {}
        for key in property_keys:
            if key in original_attributes:
                attribute = original_attributes[key]
                # 更新 value_range
                for prop in propertyList:
                    if prop.get('propertyKey') == key:
                        property_value_list = prop.get('propertyValueList')
                        if property_value_list:
                            attribute.value_range = property_value_list
                            break

                # 过滤 value_map
                if attribute.value_map:
                    # 将 property_value_list_keys 转换为集合
                    property_value_list_keys = set(property_value_list.split(','))

                    # 确保 value_map_keys 是一个集合
                    value_map_keys = set(attribute.value_map.keys())

                    # 使用 intersection 方法计算交集
                    filtered_value_map = {k: attribute.value_map[k] for k in
                                          value_map_keys.intersection(property_value_list_keys)}
                    attribute.value_map = filtered_value_map

                filtered_attributes[key] = attribute
                # 新增：强制添加f_power_consumption字段
                if "f_power_consumption" not in filtered_attributes:
                    # 创建DeviceAttribute实例
                    filtered_attributes["f_power_consumption"] = DeviceAttribute(
                        key="f_power_consumption",
                        name="电量累积消耗值",
                        attr_type="Number",
                        step=1,
                        read_write="R",
                    )
                    _LOGGER.debug("强制添加了f_power_consumption字段到解析器:%s")

        _LOGGER.debug("filtered_attributes content: %s", filtered_attributes)
        # 创建一个新的BaseBeanParser对象，并将filtered_attributes赋值给它的attributes属性
        new_parser = BaseBeanParser()
        _LOGGER.debug("Static data for filtered_parserqqqqqq %s",
                      new_parser.attributes)
        new_parser._attributes = filtered_attributes

        return new_parser

    async def async_setup_websocket(self) -> None:
        """Set up WebSocket connection."""
        if self._websocket is None:
            self._websocket = HisenseWebSocket(
                self.hass,
                self.oauth_session,
                self._handle_status_update,
            )
            await self._websocket.async_connect()

    async def async_cleanup(self) -> None:
        """Clean up resources."""
        if self._websocket is not None:
            await self._websocket.async_disconnect()
            self._websocket = None

    def register_status_callback(
        self,
        device_id: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """Register a callback for device status updates."""
        self._status_callbacks[device_id] = callback

    def _handle_status_update(self, device_id: str, properties: dict[str, Any]) -> None:
        """Handle status update from WebSocket."""
        if callback := self._status_callbacks.get(device_id):
            callback(properties)

    def _parse_device_status(self, device: DeviceInfo) -> dict[str, Any]:
        """Parse device status based on device type."""
        _LOGGER.debug(
            "Parsing status for device %s (type: %s-%s)",
            device.name, device.type_code, device.feature_code
        )
        try:
            parser = self.parsers.get(device.device_id)
            parsed_status = parser.parse_status(device.status)
            _LOGGER.info(
                "Device %s (%s-%s) status: %s",
                device.name,
                device.type_code,
                device.feature_code,
                parsed_status
            )
            return parsed_status
        except ValueError as err:
            _LOGGER.error(
                "Failed to parse status for device %s (%s-%s): %s",
                device.name,
                device.type_code,
                device.feature_code,
                err
            )
            return {}

    async def get_device_status(self, device_id: str) -> dict[str, Any]:
        """Get device status from cached device list."""
        device = self._devices.get(device_id)
        if not device:
            # If device not in cache, refresh the device list once
            devices = await self.async_get_devices
            device = devices.get(device_id)
            if not device:
                raise HisenseApiError(f"Device not found: {device_id}")
        
        return self._parse_device_status(device)

    async def async_control_device(
        self,
        puid: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        _LOGGER.debug("测试设备反应时间，下发指令 %s", property)
        """Control device by setting properties.
        
        Args:
            puid: Device ID to control
            properties: Properties to set, e.g. {"power": True, "mode": "cool"}
            
        Returns:
            Dict containing the response status and any returned properties
            
        Raises:
            HisenseApiError: If the API request fails
        """
        try:
            params = {
                "puid": puid,
                "properties": properties,
            }
            
            response = await self._api_request(
                "POST",
                API_DEVICE_CONTROL,
                data=params,
            )
            if response.get("resultCode") == 0:
                return {
                    "success": True,
                    "status": response.get("kvMap", {}),
                }
            else:
                error_msg = response.get("msg", "Unknown error")
                raise HisenseApiError(f"Control failed: {error_msg}")
                
        except Exception as err:
            raise HisenseApiError(f"Failed to control device: {err}") from err

    async def async_query_static_data(
            self,
            puid: str
    ) -> dict[str, Any]:
        try:
            params = {
                "puid": puid
            }

            response = await self._api_request(
                "POST",
                API_QUERY_STATIC_DATA,
                data=params,
            )
            _LOGGER.debug("async_query_static_data : %s", response)
            if response.get("resultCode") == 0:
                return {
                    "success": True,
                    "status": response.get("data"),
                }
            else:
                error_msg = response.get("msg", "Unknown error")
                raise HisenseApiError(f"Control failed: {error_msg}")

        except Exception as err:
            raise HisenseApiError(f"Failed to control device: {err}") from err

    async def async_get_property_list(
            self,
            deviceTypeCode: str,
            deviceFeatureCode: str,
    ) -> dict[str, Any]:
        try:
            params = {
                "deviceTypeCode": deviceTypeCode,
                "deviceFeatureCode": deviceFeatureCode,
            }

            response = await self._api_request(
                "GET",
                API_GET_PROPERTY_LTST,
                data=params,
            )
            _LOGGER.debug("async_get_property_list : %s", response)
            if response.get("resultCode") == 0:
                return {
                    "success": True,
                    "status": response.get("properties", {}),
                }
            else:
                error_msg = response.get("msg", "Unknown error")
                raise HisenseApiError(f"Control failed: {error_msg}")

        except Exception as err:
            raise HisenseApiError(f"Failed to control device: {err}") from err

    async def async_get_hour_power(
            self,
            date: str,
            puid: str,
    ) -> dict[str, Any]:
        try:
            params = {
                "date": date,
                "puid": puid,
            }

            response = await self._api_request(
                "POST",
                API_GET_HOUR_POWER,
                data=params,
            )
            _LOGGER.debug("async_get_hour_power  %s", response)
            if response.get("resultCode") == 0:
                return {
                    "success": True,
                    "status": response.get("powerConsumption", {}),
                }
            else:
                error_msg = response.get("msg", "Unknown error")
                raise HisenseApiError(f"Control failed: {error_msg}")

        except Exception as err:
            raise HisenseApiError(f"Failed to control device: {err}") from err

    async def async_api_self_check(
            self,
            noRecord: str,
            puid: str,
    ) -> dict[str, Any]:
        try:
            params = {
                "noRecord": noRecord,
                "puid": puid,
            }

            response = await self._api_request(
                "POST",
                API_SELF_CHECK,
                data=params,
            )
            _LOGGER.debug("async_api_self_check: %s", response)
            if response.get("resultCode") == 0:
                return {
                    "success": True,
                    "status": response.get("data", {}),
                }
            else:
                error_msg = response.get("msg", "Unknown error")
                raise HisenseApiError(f"Control failed: {error_msg}")

        except Exception as err:
            raise HisenseApiError(f"Failed to control device: {err}") from err