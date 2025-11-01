# 🎉 DayBetter Services 完整配置指南

## ✅ 已实现的功能

### 配置流程
1. ✅ 用户在 UI 中输入 **User Code**
2. ✅ 调用 `integrate(code)` 创建集成并获取 token
3. ✅ 调用 `fetch_devices()` 获取设备列表
4. ✅ 调用 `fetch_pids()` 获取 PID 信息
5. ✅ 定时调用 `fetch_device_statuses()` 同步温湿度状态（30秒轮询）

### API 函数使用
| 函数 | 调用时机 | 说明 |
|------|---------|------|
| `integrate(code)` | 配置时 | 创建集成，获取 token |
| `fetch_devices()` | 配置验证时 | 获取设备列表验证连接 |
| `fetch_pids()` | 配置验证时 | 获取 PID 信息 |
| `fetch_device_statuses()` | 定时轮询 | 每30秒获取温湿度状态 |

---

## 🚀 开始使用

### 步骤 1：安装新版本依赖

**方式 1：使用 VS Code 任务**
```
Ctrl+Shift+P → Tasks: Run Task → 🚀 DayBetter: 安装依赖
```

**方式 2：手动安装**
```bash
python3.12 -m pip install daybetter-services-python==1.0.1
```

### 步骤 2：启动调试

```
1. 按 F5
2. 选择：🔥 DayBetter Services (调试模式)
3. 等待启动完成
```

### 步骤 3：添加集成

1. 打开浏览器：`http://localhost:8123`

2. 进入：**设置 → 设备与服务 → 添加集成**

3. 搜索：**DayBetter**

4. 输入你的 **User Code**

5. 点击 **提交**

---

## 📋 配置流程详解

### 1. 用户输入 User Code

UI 表单：
```
┌────────────────────────────────────────┐
│ 设置 DayBetter Services                │
│                                        │
│ 请输入您的 DayBetter 用户代码以创建    │
│ 集成。                                 │
│                                        │
│ 集成将自动：                           │
│ 1. 创建连接并获取访问令牌              │
│ 2. 获取您的设备列表                    │
│ 3. 获取设备类型信息 (PIDs)             │
│ 4. 定时同步温湿度传感器状态            │
│                                        │
│ 用户代码: [___________________]        │
│                                        │
│           [提交]    [取消]             │
└────────────────────────────────────────┘
```

### 2. 调用 integrate 接口

代码流程：
```python
# config_flow.py
user_code = user_input[CONF_USER_CODE]
api = DayBetterApi(user_code=user_code)
integrate_result = await api.integrate(user_code)

if integrate_result and "token" in integrate_result:
    token = integrate_result["token"]
    # 继续下一步
```

### 3. 验证并获取设备/PIDs

```python
api_with_token = DayBetterApi(token=token)
devices = await api_with_token.fetch_devices()
pids = await api_with_token.fetch_pids()

# 记录日志
_LOGGER.info(
    "DayBetter integration successful. Devices: %d, PIDs: %s",
    len(devices),
    list(pids.keys())
)
```

### 4. 保存配置

```python
return self.async_create_entry(
    title="DayBetter Services",
    data={
        CONF_USER_CODE: user_code,
        CONF_TOKEN: token,
    },
)
```

### 5. 定时同步状态

协调器每 30 秒调用一次：
```python
# coordinator.py
async def _async_update_data(self):
    return await self._api.fetch_device_statuses()
```

---

## 🔍 数据流程

```
用户输入 User Code
    ↓
调用 integrate(code)
    ↓
获取 token
    ↓
调用 fetch_devices() 验证
    ↓
调用 fetch_pids() 获取类型信息
    ↓
创建配置条目（保存 token）
    ↓
初始化协调器
    ↓
每 30 秒调用 fetch_device_statuses()
    ↓
过滤 type=5 设备
    ↓
缩放温湿度数值（÷10）
    ↓
更新传感器实体
```

---

## 📊 API 数据格式

### integrate() 返回
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "code": 200,
  "message": "success"
}
```

### fetch_devices() 返回
```json
[
  {
    "id": "device_123",
    "deviceName": "Living Room Sensor",
    "deviceGroupName": "Living Room",
    "type": 5,
    ...
  }
]
```

### fetch_pids() 返回
```json
{
  "5": {
    "name": "Temperature/Humidity Sensor",
    "properties": [...]
  },
  ...
}
```

### fetch_device_statuses() 返回
```json
[
  {
    "deviceName": "device06068838ADDE",
    "type": 5,
    "online": true,
    "temp": 235,    // 23.5°C
    "humi": 600,    // 60.0%
    "bettery": 99
  }
]
```

---

## 🐛 错误处理

### 错误类型

| 错误 | 原因 | 用户看到 |
|------|------|----------|
| `invalid_code` | User Code 无效 | "用户代码无效，请检查后重试" |
| `cannot_connect` | 网络或 API 问题 | "无法连接到 DayBetter 服务，请检查网络连接" |
| `unknown` | 其他错误 | "未知错误，请查看日志" |

### 调试错误

在 `config_flow.py` 添加断点：

```python
async def async_step_user(self, user_input: dict[str, Any] | None = None):
    if user_input is not None:
        user_code = user_input[CONF_USER_CODE]  # ← 断点1：查看输入
        
        api = DayBetterApi(user_code=user_code)
        integrate_result = await api.integrate(user_code)  # ← 断点2：查看结果
        
        if not integrate_result or "token" not in integrate_result:
            errors["base"] = "invalid_code"  # ← 断点3：检查错误
```

---

## 🎯 实体命名

### 自动创建的传感器

对于每个 type=5 的设备：

```
sensor.<设备组名小写>_temperature
sensor.<设备组名小写>_humidity
```

示例：
- 设备组名：`Living Room`
- 温度传感器：`sensor.living_room_temperature`
- 湿度传感器：`sensor.living_room_humidity`

### 实体属性

**温度传感器**：
- State: 23.5
- Unit: °C
- Device Class: temperature
- State Class: measurement

**湿度传感器**：
- State: 60.0
- Unit: %
- Device Class: humidity
- State Class: measurement

---

## 🔧 配置存储

### 保存的数据

```yaml
# .storage/core.config_entries
{
  "entry_id": "abc123...",
  "domain": "daybetter_services",
  "title": "DayBetter Services",
  "data": {
    "user_code": "your_user_code",
    "token": "eyJhbGciOiJIUzI1NiIs..."
  },
  "version": 1
}
```

### 使用 token

初始化时从配置读取：
```python
# __init__.py
token = entry.data.get(CONF_TOKEN)
api = DayBetterApi(token=token)
```

---

## 📝 文件清单

### 核心文件

| 文件 | 说明 |
|------|------|
| `config_flow.py` | UI 配置流程，调用 integrate |
| `daybetter_api.py` | API 包装，包含6个函数 |
| `coordinator.py` | 定时协调器，调用 fetch_device_statuses |
| `__init__.py` | 集成入口，使用 token 初始化 |
| `const.py` | 常量定义 |
| `sensor.py` | 传感器平台 |
| `manifest.json` | 集成元数据 |

### 翻译文件

| 文件 | 说明 |
|------|------|
| `strings.json` | 默认文本 |
| `translations/zh-Hans.json` | 中文翻译 |
| `translations/en.json` | 英文翻译 |

---

## ✅ 测试清单

### 功能测试

- [ ] 输入 User Code 能成功创建集成
- [ ] 成功获取并保存 token
- [ ] 能正确调用 fetch_devices()
- [ ] 能正确调用 fetch_pids()
- [ ] 协调器能定时调用 fetch_device_statuses()
- [ ] Type=5 设备被正确过滤
- [ ] 温湿度数值正确缩放（÷10）
- [ ] 传感器实体正确创建
- [ ] 传感器状态正确更新

### 错误测试

- [ ] 无效 User Code 显示正确错误
- [ ] 网络错误显示正确提示
- [ ] 不能重复添加集成

---

## 🎉 完成！

现在你可以：

1. ✅ 通过 UI 输入 User Code
2. ✅ 自动创建集成并获取 token
3. ✅ 自动获取设备和 PID
4. ✅ 定时同步温湿度状态
5. ✅ 在仪表板查看传感器

**按 F5 启动，添加集成，开始使用！** 🚀

