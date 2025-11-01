# ✅ 已修复：API 初始化错误

## 🐛 原始错误

```
TypeError: DayBetterClient.__init__() got an unexpected keyword argument 'user_code'
```

## 🔍 问题原因

之前的代码错误地尝试在初始化时传入 `user_code`：

```python
# ❌ 错误的方式
api = DayBetterApi(user_code=user_code)
client = DayBetterClient(user_code=user_code)  # 不支持这个参数
```

## ✅ 正确的 API 使用方式

根据 `daybetter-services-python` 包的实际 API：

### DayBetterClient 初始化

```python
DayBetterClient(token: str, base_url: str = '...')
```

**参数**：
- `token`: 必需，访问令牌
- `base_url`: 可选，API 基础 URL

### integrate 方法

```python
await client.integrate(hass_code: str) -> Dict[str, Any]
```

**参数**：
- `hass_code`: 用户代码（就是我们说的 User Code）

---

## 🔧 修复内容

### 1. 更新 daybetter_api.py

**之前**：
```python
def __init__(self, user_code: str | None = None, token: str | None = None):
    if user_code:
        self._client = DayBetterClient(user_code=user_code)  # ❌ 错误
```

**现在**：
```python
def __init__(self, token: str | None = None):
    if token:
        self._client = DayBetterClient(token=token)  # ✅ 正确
    else:
        self._client = DayBetterClient(token="")  # 临时空 token
```

### 2. 更新 integrate 方法

```python
async def integrate(self, user_code: str) -> dict[str, Any]:
    # 调用 integrate 方法，参数名是 hass_code
    result = await self._client.integrate(hass_code=user_code)
    
    if result and "token" in result:
        self._token = result["token"]
        # 使用新 token 重新初始化客户端
        self._client = DayBetterClient(token=self._token)
    
    return result
```

### 3. 更新 config_flow.py

**之前**：
```python
api = DayBetterApi(user_code=user_code)  # ❌ 错误
```

**现在**：
```python
api = DayBetterApi()  # ✅ 正确，无需传入 user_code
integrate_result = await api.integrate(user_code)
```

---

## 📊 完整流程

```
1. 用户输入 User Code
    ↓
2. 创建 API: api = DayBetterApi()
    ↓
3. 调用 integrate: result = await api.integrate(user_code)
    ↓
4. API 内部调用: await client.integrate(hass_code=user_code)
    ↓
5. 获取 token
    ↓
6. 用 token 重新初始化客户端
    ↓
7. 验证连接：fetch_devices()、fetch_pids()
    ↓
8. 保存配置
```

---

## ✅ 已修复的文件

- ✅ `homeassistant/components/daybetter_services/daybetter_api.py`
- ✅ `homeassistant/components/daybetter_services/config_flow.py`
- ✅ `config/custom_components/daybetter_services/daybetter_api.py`
- ✅ `config/custom_components/daybetter_services/config_flow.py`

---

## 🚀 现在重启测试

### 步骤 1：重启 Home Assistant

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

## 🎯 预期结果

### 成功的流程

```
输入 User Code
    ↓
调用 integrate(hass_code) ✅
    ↓
返回 {"token": "eyJ...", "code": 200}
    ↓
用 token 初始化客户端
    ↓
调用 fetch_devices() ✅
    ↓
调用 fetch_pids() ✅
    ↓
保存配置
    ↓
创建传感器实体
```

### 日志输出

成功时应该看到：
```
INFO: DayBetter integration successful. Devices: X, PIDs: {...}
```

---

## 🐛 调试技巧

如果还有问题，在 `daybetter_api.py` 添加断点：

```python
async def integrate(self, user_code: str):
    result = await self._client.integrate(hass_code=user_code)  # ← 断点
    print(f"Integrate result: {result}")  # 查看返回值
    return result
```

---

## 📚 API 参考

### DayBetterClient 所有方法

| 方法 | 参数 | 返回 |
|------|------|------|
| `__init__` | `token: str` | - |
| `integrate` | `hass_code: str` | `Dict[str, Any]` |
| `fetch_devices` | - | `List[Dict[str, Any]]` |
| `fetch_pids` | - | `Dict[str, Any]` |
| `fetch_device_statuses` | - | `List[Dict[str, Any]]` |
| `control_device` | 多个参数 | `Dict[str, Any]` |
| `fetch_mqtt_config` | - | `Dict[str, Any]` |

---

## 🎉 问题已解决！

**按 Shift+F5 停止，按 F5 重启，然后添加集成！**

现在应该可以正常工作了！🚀

