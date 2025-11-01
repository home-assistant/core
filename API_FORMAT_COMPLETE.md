# 📋 DayBetter API 完整格式文档

## ✅ 已实现的功能

### 1. 正确解析所有 API 返回格式
### 2. 基于 PID 过滤传感器设备  
### 3. 合并设备信息和状态

---

## 📊 API 返回格式

### 1. integrate(hass_code)

**返回**：
```json
{
  "code": 1,
  "message": "success",
  "data": {
    "hassCodeToken": "d52533c6ba4c0b02fb918e3a2e41e2f5"
  }
}
```

**提取 Token**：
```python
token = result["data"]["hassCodeToken"]
```

---

### 2. fetch_devices()

**返回**：
```json
{
  "code": 1,
  "message": "success",
  "data": [
    {
      "deviceId": 3734,
      "deviceName": "device0E24D2E62710",
      "deviceGroupName": "75",
      "deviceClass": "WIFIQC2",
      "deviceState": 1,
      "deviceMac": "08:3a:8d:55:19:be",
      "deviceWlanMac": "08:3a:8d:55:19:bc",
      "deviceAndroidName": "P03A_19BE",
      "deviceSupportLan": 0,
      "deviceType": 45,
      "deviceSubclass": 43,
      "deviceMoldPid": "P075",        // ← 重要！用于判断设备类型
      "deviceFeatures": [5, 6, 7]
    }
  ]
}
```

**提取设备列表**：
```python
devices = result["data"]  # 数组
```

---

### 3. fetch_pids()

**返回**：
```json
{
  "code": 1,
  "message": "success",
  "data": {
    "light": "P01E,P021,P024,...",
    "sensor": "P075",               // ← 传感器 PID 列表
    "switch": "P02D,P033,..."
  }
}
```

**提取 PID 信息**：
```python
pids = result["data"]  # 字典
sensor_pids = pids["sensor"]  # "P075"
```

---

### 4. fetch_device_statuses()

**返回**：
```json
{
  "code": 1,
  "message": "success",
  "data": [
    {
      "deviceName": "device0E24D2E62710",
      "online": true,
      "type": 666,
      "brightness": 14,
      "rgb": "ff007d",
      "on": true
    }
  ]
}
```

**提取状态列表**：
```python
statuses = result["data"]  # 数组
```

---

## 🎯 传感器设备判断逻辑

### 步骤 1：获取传感器 PID 列表

```python
pids = await api.fetch_pids()
# pids = {"light": "...", "sensor": "P075", "switch": "..."}

sensor_pids_str = pids.get("sensor", "")  # "P075"
sensor_pids = set(sensor_pids_str.split(","))  # {"P075"}
```

### 步骤 2：过滤设备

```python
devices = await api.fetch_devices()

sensor_devices = []
for device in devices:
    device_pid = device.get("deviceMoldPid")  # "P075"
    if device_pid in sensor_pids:
        sensor_devices.append(device)  # ✅ 是传感器设备
```

### 示例

根据你的数据：
- **PID 列表**：`sensor: "P075"`
- **设备列表**：
  - ❌ `device06068838ADDE` (PID: P04F) - 不是传感器
  - ❌ `deviceAB0F79G0LHLD` (PID: P052) - 不是传感器  
  - ✅ `device0E24D2E62710` (PID: **P075**) - **是传感器！**
  - ✅ `device812200XQA1CC` (PID: **P03A**) - 如果 P03A 在 sensor 列表中

---

## 📊 数据合并逻辑

### 合并设备信息和状态

```python
# 设备列表
devices = [
  {"deviceId": 3734, "deviceName": "device0E24D2E62710", "deviceMoldPid": "P075", ...}
]

# 状态列表
statuses = [
  {"deviceName": "device0E24D2E62710", "online": true, "temp": 235, "humi": 600}
]

# 合并结果
merged = [
  {
    "deviceId": 3734,
    "deviceName": "device0E24D2E62710",
    "deviceMoldPid": "P075",
    "online": true,       // ← 来自状态
    "temp": 235,          // ← 来自状态
    "humi": 600,          // ← 来自状态
    ...
  }
]
```

---

## 🔧 已实现的方法

### DayBetterApi 类

| 方法 | 说明 | 返回 |
|------|------|------|
| `integrate(user_code)` | 创建集成获取 token | `dict` |
| `fetch_devices()` | 获取设备列表 | `list[dict]` |
| `fetch_pids()` | 获取 PID 信息 | `dict` |
| `fetch_device_statuses()` | 获取设备状态 | `list[dict]` |
| `filter_sensor_devices(devices, pids)` | 过滤传感器设备 | `list[dict]` |
| `merge_device_status(devices, statuses)` | 合并设备和状态 | `list[dict]` |
| `close()` | 关闭客户端 | `None` |

---

## 🚀 现在重启测试

### 步骤 1：重启

```
1. 按 Shift+F5 停止
2. 按 F5 重新启动
3. 选择：🔥 DayBetter Services (调试模式)
```

### 步骤 2：添加集成

```
1. 打开 http://localhost:8123
2. 设置 → 设备与服务 → 添加集成
3. 搜索 DayBetter
4. 输入 User Code
5. 点击提交
```

---

## ✅ 预期结果

### 配置流程

```
输入 User Code
    ↓
integrate → {"code": 1, "data": {"hassCodeToken": "..."}} ✅
    ↓
提取 token ✅
    ↓
fetch_devices() → {"code": 1, "data": [...]} ✅
    ↓
fetch_pids() → {"code": 1, "data": {"sensor": "P075"}} ✅
    ↓
过滤传感器设备 (PID in sensor list) ✅
    ↓
保存配置 ✅
    ↓
集成添加成功！🎉
```

### 日志输出

应该看到：
```
DEBUG: Integrate result: {'code': 1, 'message': 'success', 'data': {'hassCodeToken': '...'}}
INFO: DayBetter integration successful. Total devices: 7, Sensor devices: X, PIDs: {'light': '...', 'sensor': 'P075', 'switch': '...'}
```

---

## 📝 下一步工作

### ⚠️ 注意

根据你提供的数据，**设备状态中目前没有温湿度字段**（temp/humi）。

需要确认：

1. **真实的温湿度传感器设备**返回的状态格式是什么？
2. 是否需要特定的 API 调用来获取温湿度？
3. 温湿度数据是在 `fetch_device_statuses` 中返回，还是其他接口？

### 等待真实传感器数据

一旦有了真实的温湿度传感器（PID: P075）的状态数据，我们就可以：

1. 更新 `sensor.py` 创建温湿度实体
2. 实现数据解析和缩放
3. 完善实体属性

---

## 🎉 当前进度

✅ API 格式正确解析  
✅ Token 正确提取  
✅ 设备列表正确获取  
✅ PID 信息正确获取  
✅ 传感器设备正确过滤  
⏳ 等待真实温湿度数据格式  

---

**按 Shift+F5 停止，按 F5 重启，添加集成！**

集成应该可以成功添加了！🚀

