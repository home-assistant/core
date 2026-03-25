"""Update coordinator for Heiman Home entities.

Enhanced coordinator with MQTT real-time updates and HTTP polling fallback.
"""

from __future__ import annotations

from datetime import timedelta
import json
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .refresh_optimizer import MultiLevelRefreshManager

_LOGGER = logging.getLogger(__name__)

# Store coordinators per entry
_coordinators: dict[str, HeimanCoordinator] = {}


def get_coordinator(hass: HomeAssistant, entry_id: str) -> HeimanCoordinator:
    """Get or create a coordinator for the entry."""
    if entry_id not in _coordinators:
        _coordinators[entry_id] = HeimanCoordinator(hass, entry_id)
    return _coordinators[entry_id]


def register_coordinator(entry_id: str, coordinator: HeimanCoordinator) -> None:
    """Register a coordinator."""
    _coordinators[entry_id] = coordinator
    _LOGGER.debug("Registered coordinator for entry %s", entry_id)


def unregister_coordinator(entry_id: str) -> None:
    """Unregister a coordinator."""
    if entry_id in _coordinators:
        del _coordinators[entry_id]
        _LOGGER.debug("Unregistered coordinator for entry %s", entry_id)


class HeimanCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Heiman Home devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        cloud_client=None,
        mqtt_client=None,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry_id}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self._entry_id = entry_id
        self._cloud_client = cloud_client
        self._mqtt_client = mqtt_client
        self._devices: dict[str, dict[str, Any]] = {}
        self._alarms: dict[str, list[dict]] = {}  # Cache for device alarms
        self._properties_cache: dict[
            str,
            dict[str, Any],
        ] = {}  # Cache for device properties: {device_id: {prop_name: value}}
        self._device_property_names: dict[
            str,
            list[str],
        ] = {}  # Cache for device property names: {device_id: [prop_names]}
        self._refresh_manager: MultiLevelRefreshManager | None = None
        self._last_notify_time = 0.0  # Track last notification time for debouncing
        self._min_notify_interval = (
            0.5  # Minimum seconds between notifications (debounce interval)
        )

        # Register MQTT callbacks if available
        if self._mqtt_client:
            self._mqtt_client.register_device_callback(self._on_device_update)

    def init_refresh_manager(self) -> None:
        """Initialize the refresh optimizer."""
        if not self._refresh_manager and self._cloud_client:
            self._refresh_manager = MultiLevelRefreshManager(
                hass=self.hass,
                entry_id=self._entry_id,
                cloud_client=self._cloud_client,
                mqtt_client=self._mqtt_client,
            )
            _LOGGER.debug("Refresh manager initialized")

    def set_mqtt_client(self, mqtt_client) -> None:
        """Set MQTT client and register callbacks."""
        self._mqtt_client = mqtt_client
        if mqtt_client:
            mqtt_client.register_device_callback(self._on_device_update)
            _LOGGER.debug("Registered device callback with MQTT client")

    def set_cloud_client(self, cloud_client) -> None:
        """Set cloud client."""
        self._cloud_client = cloud_client

    @property
    def mqtt_client(self):
        """Return the MQTT client."""
        return self._mqtt_client

    def _schedule_refresh(self) -> None:
        """Schedule a data refresh from non-async context.

        This method can be safely called from callbacks and non-async code.
        It directly notifies all entities to refresh from the cache.
        """
        if self.hass and self.hass.is_running:
            # Use call_soon_threadsafe to ensure thread-safe execution in the event loop
            # This is important because MQTT callbacks run in a separate thread
            self.hass.loop.call_soon_threadsafe(self._async_notify_entities)
        else:
            _LOGGER.debug("HASS not running, skipping refresh")

    def schedule_refresh(self) -> None:
        """Schedule a data refresh from external callers."""
        self._schedule_refresh()

    @callback
    def _async_notify_entities(self) -> None:
        """Notify all entities to refresh from cache.

        This is called when MQTT updates the cache, to trigger entity refresh.
        Must be called from the event loop thread.
        Includes debouncing to avoid excessive refreshes.
        """
        current_time = self.hass.loop.time() if self.hass else 0
        time_since_last_notify = current_time - self._last_notify_time

        # Debounce: skip notification if too soon since last one
        if time_since_last_notify < self._min_notify_interval:
            _LOGGER.debug(
                "Skipping refresh notification (debounce): %.3fs since last notify (%.3fs minimum)",
                time_since_last_notify,
                self._min_notify_interval,
            )
            return

        _LOGGER.info(
            "Notifying all entities to refresh from cache (properties: %s devices)",
            len(self._properties_cache),
        )
        # Update the coordinator data timestamp to indicate fresh data
        self.async_set_updated_data(
            {
                "timestamp": current_time,
                "devices": self._devices,
                "properties": self._properties_cache,
            },
        )
        self._last_notify_time = current_time

    def _on_device_update(self, device_id: str, event_data: dict) -> None:
        """Handle MQTT device update.

        This is called via device callbacks for property_report and events.
        Note: This may cause duplicate refresh notifications if called alongside
        update_device_properties(). The debouncing mechanism in _async_notify_entities
        will handle this by ignoring rapid successive refreshes.
        """
        _LOGGER.debug(
            "Device update received via MQTT: %s, event: %s",
            device_id,
            event_data,
        )

        # Update device data if event_data contains device info
        if event_data and isinstance(event_data, dict):
            self._devices[device_id] = event_data

        # Schedule a refresh to update entities (use non-blocking method)
        # Debouncing will prevent excessive refreshes if this is called multiple times
        self._schedule_refresh()

    def update_device_property(
        self,
        device_id: str,
        property_name: str,
        value: Any,
    ) -> None:
        """Update a single device property in cache.

        Args:
            device_id: 设备 ID
            property_name: 属性名称
            value: 属性值
        """
        if device_id not in self._properties_cache:
            self._properties_cache[device_id] = {}
        self._properties_cache[device_id][property_name] = value
        _LOGGER.debug(
            "Updated property cache for device %s: %s = %s",
            device_id,
            property_name,
            value,
        )
        # Notify entities to refresh (use non-blocking method)
        self._schedule_refresh()

    def update_device_properties(
        self,
        device_id: str,
        properties: dict[str, Any],
    ) -> None:
        """Update multiple device properties in cache.

        Args:
            device_id: 设备 ID
            properties: 属性字典 {property_name: value}
        """
        if device_id not in self._properties_cache:
            self._properties_cache[device_id] = {}

        # Track if any property was actually updated
        updated_count = 0
        for prop_name, prop_value in properties.items():
            # Only update if value changed or property didn't exist
            old_value = self._properties_cache[device_id].get(prop_name)
            if old_value != prop_value:
                self._properties_cache[device_id][prop_name] = prop_value
                updated_count += 1
                _LOGGER.debug(
                    "Updated property in cache for device %s: %s = %s (old: %s)",
                    device_id,
                    prop_name,
                    prop_value,
                    old_value,
                )

        # Only notify entities if something actually changed
        if updated_count > 0:
            _LOGGER.info(
                "Updated %s properties in cache for device %s: %s",
                updated_count,
                device_id,
                properties,
            )
            # Notify entities to refresh (use non-blocking method)
            self._schedule_refresh()
        else:
            _LOGGER.debug(
                "No property value changes for device %s, skipping refresh notification",
                device_id,
            )

    def register_device_properties(
        self,
        device_id: str,
        property_names: list[str],
    ) -> None:
        """注册设备的属性名称列表，用于批量获取。.

        Args:
            device_id: 设备 ID
            property_names: 属性名称列表
        """
        if device_id and property_names:
            self._device_property_names[device_id] = property_names
            _LOGGER.debug(
                "Registered %s properties for device %s: %s",
                len(property_names),
                device_id,
                property_names,
            )
        else:
            _LOGGER.warning(
                "Failed to register properties: device_id=%s, property_names=%s",
                device_id,
                property_names,
            )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the devices with batch property fetching."""
        try:
            _LOGGER.info(
                "Coordinator _async_update_data called: MQTT=%s, cloud_client=%s, property_names=%s devices",
                self._mqtt_client is not None and self._mqtt_client.connected
                if self._mqtt_client
                else False,
                self._cloud_client is not None,
                len(self._device_property_names),
            )

            # Always fetch device properties via HTTP to ensure data freshness
            # MQTT handles real-time push updates, but we still need initial data
            if self._cloud_client:
                _LOGGER.debug("Fetching data via HTTP with batch property fetching")

                # 1. 使用已存储的设备列表（包含所有选中家庭的设备）
                # 这些设备在 __init__.py 中已经加载并存储到 hass.data[DOMAIN]['devices'][entry_id]
                stored_devices = (
                    self.hass.data.get(DOMAIN, {})
                    .get("devices", {})
                    .get(self._entry_id, {})
                )

                if stored_devices:
                    self._devices = stored_devices
                    device_count = len(self._devices)
                    _LOGGER.info(
                        "Using %s stored devices from hass.data (all selected homes)",
                        device_count,
                    )
                else:
                    # Fallback: fetch from cloud if no stored devices
                    _LOGGER.warning("No stored devices found, fetching from cloud...")
                    self._devices = await self._cloud_client.async_get_devices()
                    device_count = len(self._devices)
                    _LOGGER.info(
                        "Fetched %s devices from cloud (fallback)",
                        device_count,
                    )

                # 2. 从设备列表的 deriveMetadata 中提取属性值填充缓存
                self._extract_properties_from_device_list()

                # 3. 逐个设备调用 detail API 获取属性（旧接口，保留兼容性）
                await self._fetch_device_properties_via_detail_api()

                # 4. 逐个设备调用 device-instance/detail API 获取 state 和 deviceType
                await self._fetch_device_instance_state_and_type()

                _LOGGER.info(
                    "Coordinator data update completed: %s devices total, %s properties cached",
                    device_count,
                    sum(len(props) for props in self._properties_cache.values()),
                )

                return {
                    "timestamp": self.hass.loop.time(),
                    "devices": self._devices,
                    "properties": self._properties_cache,
                }

            _LOGGER.warning("No cloud client available, returning cached data")
            return {
                "timestamp": self.hass.loop.time(),
                "devices": self._devices,
                "properties": self._properties_cache,
            }

        except Exception as err:
            _LOGGER.exception("Error updating coordinator")
            raise UpdateFailed(f"Error communicating with Heiman Cloud: {err}") from err

    async def _fetch_device_properties_via_detail_api(self) -> None:
        """通过调用 /api-saas/device/instance/app/11/{device_id}/detail 接口获取所有设备属性。.

        每个设备单独调用一次 API，返回包含 deriveMetadata 字段，解析其中的 properties。
        """
        _LOGGER.info("Starting device property fetch via detail API")

        if not self._cloud_client:
            _LOGGER.error("No cloud client available, skipping detail API fetch")
            return

        total_devices = len(self._devices)
        success_count = 0
        total_properties = 0

        _LOGGER.info("Fetching properties via detail API for %s devices", total_devices)

        for device_id in self._devices:
            try:
                # 调用 detail API
                result = await self._cloud_client.async_get_device_detail(device_id)

                if not result:
                    _LOGGER.debug("Empty response for device %s", device_id)
                    continue

                derive_metadata_str = result.get("deriveMetadata", "")
                if not derive_metadata_str:
                    _LOGGER.debug(
                        "No deriveMetadata in response for device %s",
                        device_id,
                    )
                    continue

                # 解析 deriveMetadata JSON 字符串
                try:
                    metadata_list = json.loads(derive_metadata_str)

                    # 将数组转换为字典格式：{property_name: value}
                    if isinstance(metadata_list, list):
                        properties_data = {}
                        for item in metadata_list:
                            if isinstance(item, dict):
                                prop_name = item.get("property")
                                prop_value = item.get("value")
                                if prop_name and prop_value is not None:
                                    # 尝试转换为数值类型
                                    try:
                                        prop_type = item.get("type", "")
                                        if prop_type in {"int", "double"}:
                                            number_value = item.get("numberValue")
                                            if number_value is not None:
                                                prop_value = (
                                                    float(number_value)
                                                    if "." in str(number_value)
                                                    else int(number_value)
                                                )
                                    except ValueError, TypeError:
                                        pass
                                    properties_data[prop_name] = prop_value

                        # 更新缓存
                        if properties_data:
                            if device_id not in self._properties_cache:
                                self._properties_cache[device_id] = {}

                            for prop_name, prop_value in properties_data.items():
                                # 跳过空值
                                if prop_value is None:
                                    continue

                                self._properties_cache[device_id][prop_name] = (
                                    prop_value
                                )
                                success_count += 1
                                total_properties += 1
                                _LOGGER.debug(
                                    "Updated property from detail API: %s.%s = %s",
                                    device_id,
                                    prop_name,
                                    prop_value,
                                )

                except json.JSONDecodeError as err:
                    _LOGGER.debug(
                        "Failed to parse deriveMetadata JSON for device %s: %s",
                        device_id,
                        err,
                    )
                    continue

            except Exception:
                _LOGGER.exception(
                    "Failed to fetch properties via detail API for device %s",
                    device_id,
                )

        _LOGGER.info(
            "Detail API fetch completed: %s/%s devices processed, %s properties fetched",
            success_count,
            total_devices,
            total_properties,
        )

    async def _fetch_device_instance_state_and_type(self) -> None:
        """通过调用 /api-saas/device-instance/{device_id}/detail 接口获取设备状态和类型。.

        从返回的 metadata 中提取 state（在线状态）和 deviceType（设备类型）字段。
        """
        _LOGGER.info("Starting device instance state/type fetch")

        if not self._cloud_client:
            _LOGGER.error("No cloud client available, skipping device instance fetch")
            return

        total_devices = len(self._devices)
        success_count = 0

        _LOGGER.info(
            "Fetching state and type via device-instance API for %s devices",
            total_devices,
        )

        # Check if the new method exists
        if not hasattr(self._cloud_client, "async_get_device_instance_detail"):
            _LOGGER.warning(
                "Cloud client doesn't have async_get_device_instance_detail method, skipping",
            )
            return

        for device_id in self._devices:
            try:
                # 调用 device-instance/detail API
                result = await self._cloud_client.async_get_device_instance_detail(
                    device_id,
                )

                if not result:
                    _LOGGER.debug("Empty response for device %s", device_id)
                    continue

                # Extract state field (online/offline)
                state_obj = result.get("state", {})
                if isinstance(state_obj, dict):
                    state_value = state_obj.get("value", "")
                    state_text = state_obj.get("text", "")

                    # Update cache with state value
                    if device_id not in self._properties_cache:
                        self._properties_cache[device_id] = {}

                    # Store both value and text representation
                    self._properties_cache[device_id]["state"] = state_value
                    self._properties_cache[device_id]["state_text"] = state_text
                    success_count += 1
                    _LOGGER.debug(
                        "Updated state for device %s: %s (%s)",
                        device_id,
                        state_value,
                        state_text,
                    )

                # Extract deviceType field
                device_type_obj = result.get("deviceType", {})
                if isinstance(device_type_obj, dict):
                    type_value = device_type_obj.get("value", "")
                    type_text = device_type_obj.get("text", "")

                    # Update cache with device type
                    if device_id not in self._properties_cache:
                        self._properties_cache[device_id] = {}

                    # Store both value and text representation
                    self._properties_cache[device_id]["deviceType"] = type_value
                    self._properties_cache[device_id]["deviceType_text"] = type_text
                    success_count += 1
                    _LOGGER.debug(
                        "Updated deviceType for device %s: %s (%s)",
                        device_id,
                        type_value,
                        type_text,
                    )

            except Exception:
                _LOGGER.exception(
                    "Failed to fetch state/type via device-instance API for device %s",
                    device_id,
                )

        _LOGGER.info(
            "Device instance state/type fetch completed: %s/%s devices processed",
            success_count,
            total_devices,
        )

    def _extract_properties_from_device_list(self) -> None:
        """从设备列表的 deriveMetadata 中提取属性值填充缓存。.

        设备列表接口返回的每个设备包含 deriveMetadata 字段，其中包含
        在 propertyIdentifiers 中指定的属性值。我们提前将这些值
        填充到缓存中，避免额外的 API 请求。

        注意：deriveMetadata 可能是 JSON 字符串或字典格式：
        - 字符串格式：'[{"property":"xxx","value":"yyy"}, ...]'
        - 字典格式：{'properties': {'prop1': value1, ...}}
        """
        extracted_count = 0
        total_devices = len(self._devices)
        processed_devices = 0

        _LOGGER.info(
            "Extracting properties from device list: %s devices",
            total_devices,
        )

        for device_id, device_info in self._devices.items():
            processed_devices += 1
            derive_metadata = device_info.get("deriveMetadata", {})

            # 处理 deriveMetadata 是 JSON 字符串的情况
            if isinstance(derive_metadata, str):
                try:
                    # 解析 JSON 字符串
                    metadata_list = json.loads(derive_metadata)

                    # 将数组转换为字典格式：{property_name: value}
                    if isinstance(metadata_list, list):
                        properties_data = {}
                        for item in metadata_list:
                            if isinstance(item, dict):
                                prop_name = item.get("property")
                                prop_value = item.get("value")
                                if prop_name and prop_value is not None:
                                    # 尝试转换为数值类型
                                    try:
                                        prop_type = item.get("type", "")
                                        if prop_type in {"int", "double"}:
                                            number_value = item.get("numberValue")
                                            if number_value is not None:
                                                prop_value = (
                                                    float(number_value)
                                                    if "." in str(number_value)
                                                    else int(number_value)
                                                )
                                    except ValueError, TypeError:
                                        pass
                                    properties_data[prop_name] = prop_value

                        derive_metadata = {"properties": properties_data}
                        if device_id == "1942869486798540800":
                            _LOGGER.info("  Parsed properties: %s", properties_data)
                    else:
                        _LOGGER.debug(
                            "Parsed metadata is not a list for device %s: %s",
                            device_id,
                            type(metadata_list),
                        )
                        continue

                except json.JSONDecodeError as err:
                    _LOGGER.debug(
                        "Failed to parse deriveMetadata JSON for device %s: %s",
                        device_id,
                        err,
                    )
                    continue

            # 确保 deriveMetadata 是字典类型
            if not isinstance(derive_metadata, dict):
                _LOGGER.debug(
                    "deriveMetadata is not a dict for device %s, skipping: %s",
                    device_id,
                    type(derive_metadata),
                )
                continue

            # 提取属性值
            properties_data = derive_metadata.get("properties", {})

            # 确保 properties 是字典类型
            if not isinstance(properties_data, dict):
                _LOGGER.debug(
                    "properties is not a dict for device %s, skipping: %s",
                    device_id,
                    type(properties_data),
                )
                continue

            # 初始化该设备的缓存
            if device_id not in self._properties_cache:
                self._properties_cache[device_id] = {}

            # 提取每个属性的值
            for prop_name, prop_value in properties_data.items():
                # 跳过空值
                if prop_value is None:
                    continue

                # 只有当缓存中没有该属性时才填充（保留 API 获取的最新值）
                if prop_name not in self._properties_cache[device_id]:
                    self._properties_cache[device_id][prop_name] = prop_value
                    extracted_count += 1
                    _LOGGER.debug(
                        "Extracted property from deriveMetadata: %s.%s = %s",
                        device_id,
                        prop_name,
                        prop_value,
                    )

        _LOGGER.info(
            "Extracted %s properties from %s/%s devices (some devices may have no deriveMetadata)",
            extracted_count,
            processed_devices,
            total_devices,
        )

    def get_device_property(self, device_id: str, property_name: str) -> Any:
        """从缓存中获取设备属性值。.

        Args:
            device_id: 设备 ID
            property_name: 属性名称

        Returns:
            属性值，如果未找到则返回 None
        """
        device_props = self._properties_cache.get(device_id, {})
        return device_props.get(property_name)

    def get_device_properties(self, device_id: str) -> dict[str, Any]:
        """获取设备的所有缓存属性。.

        Args:
            device_id: 设备 ID

        Returns:
            属性字典，如果未找到则返回空字典
        """
        return self._properties_cache.get(device_id, {}).copy()

    async def async_get_device_alarms(
        self,
        device_id: str,
        page_size: int = 20,
        page_number: int = 1,
        use_cache: bool = True,
    ) -> dict:
        """Get alarm logs for a specific device.

        Args:
            device_id: The device ID (iotId in API)
            page_size: Number of alarms per page
            page_number: Page number
            use_cache: Whether to use cached data if available

        Returns:
            Dict with keys: pageIndex, pageSize, total, data (list of alarm records)
        """
        cache_key = f"{device_id}_{page_size}_{page_number}"

        # Check cache if enabled
        if use_cache and cache_key in self._alarms:
            _LOGGER.info("Using cached alarms for device %s", device_id)
            return self._alarms[cache_key]

        # Fetch from cloud API
        if self._cloud_client:
            try:
                _LOGGER.info("Fetching alarms for device %s", device_id)
                result = await self._cloud_client.async_get_device_alarms(
                    device_id=device_id,
                    page_size=page_size,
                    page_number=page_number,
                )
                # Cache the result
                self._alarms[cache_key] = result
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Failed to get device alarms for %s: %s", device_id, err)
            else:
                return result

        return {}

    def clear_alarms_cache(self, device_id: str | None = None) -> None:
        """Clear alarms cache for a device or all devices."""
        if device_id:
            # Clear cache for specific device
            keys_to_remove = [k for k in self._alarms if k.startswith(f"{device_id}_")]
            for key in keys_to_remove:
                del self._alarms[key]
        else:
            # Clear all cache
            self._alarms.clear()

    async def async_sync_child_devices(self, gateway_device_id: str) -> bool:
        """Synchronize child devices for a gateway.

        This method queries the topology from the gateway and updates
        the device list with any new child devices.

        Args:
            gateway_device_id: The gateway device ID

        Returns:
            True if sync was successful, False otherwise
        """
        if not self._mqtt_client or not self._cloud_client:
            _LOGGER.error("MQTT or cloud client not available for device sync")
            return False

        try:
            # Get gateway device info
            gateway_info = self._devices.get(gateway_device_id)
            if not gateway_info:
                _LOGGER.error("Gateway device %s not found", gateway_device_id)
                return False

            product_id = gateway_info.get("productId", "")
            if not product_id:
                _LOGGER.error("Product ID not found for gateway %s", gateway_device_id)
                return False

            # Query topology via MQTT
            _LOGGER.info("Querying child devices for gateway %s", gateway_device_id)
            topology_result = await self._mqtt_client.async_query_topology(
                product_id=product_id,
                device_id=gateway_device_id,
            )

            if not topology_result:
                _LOGGER.warning(
                    "Topology query failed for gateway %s",
                    gateway_device_id,
                )
                return False

            child_devices = topology_result.get("devices", [])
            continue_flag = topology_result.get("continue", 0)

            _LOGGER.info(
                "Found %s child devices for gateway %s",
                len(child_devices),
                gateway_device_id,
            )

            # Handle pagination if there are more devices
            if continue_flag == 1:
                _LOGGER.info("More child devices available, additional queries needed")
                # TODO: Implement pagination logic if needed

            # Update device list with child devices
            updated = False
            for child_info in child_devices:
                child_device_id = child_info.get("deviceId")
                child_product_id = child_info.get("productId")
                child_device_name = child_info.get("deviceName")

                if not child_device_id:
                    continue

                # Add or update child device in local cache
                if child_device_id not in self._devices:
                    # New child device - create entry
                    self._devices[child_device_id] = {
                        "id": child_device_id,
                        "productId": child_product_id,
                        "deviceName": child_device_name,
                        "parentId": gateway_device_id,
                        "deviceType": {"value": "childrenDevice"},
                        "online": True,
                    }
                    updated = True
                    _LOGGER.info(
                        "Added new child device: %s (%s)",
                        child_device_id,
                        child_device_name,
                    )
                else:
                    # Existing device - update info
                    existing = self._devices[child_device_id]
                    if existing.get("parentId") != gateway_device_id:
                        existing["parentId"] = gateway_device_id
                        updated = True
                    if existing.get("online") is not True:
                        existing["online"] = True
                        updated = True

            # If devices were added/updated, schedule a full refresh
            if updated:
                _LOGGER.info(
                    "Child device sync completed: %s devices, changes detected",
                    len(child_devices),
                )
                # Store updated devices to hass.data
                self.hass.data.setdefault(DOMAIN, {}).setdefault("devices", {})[
                    self._entry_id
                ] = self._devices
                # Schedule refresh to update entities
                self._schedule_refresh()
                return True

        except Exception:
            _LOGGER.exception("Error syncing child devices")
            return False
        else:
            _LOGGER.info("Child device sync completed: no changes")
            return True


async def remove_coordinator(entry_id: str) -> None:
    """Remove a coordinator."""
    _coordinators.pop(entry_id, None)
