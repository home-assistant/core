# 🔍 调试"用户代码无效"问题

## 📋 当前状态

✅ 没有 session 错误  
✅ 没有导入错误  
✅ 没有 API 初始化错误  
❓ 但提示：**"用户代码无效，请检查后重试"**

---

## 🐛 可能的原因

### 1. integrate 返回的数据格式不正确

#### 预期格式：
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "code": 200,
  "message": "success"
}
```

#### 可能的实际格式：
```json
{
  "data": {
    "token": "eyJ..."
  },
  "code": 200
}
```

或者：
```json
{
  "access_token": "eyJ...",  // 不是 "token"
  "code": 200
}
```

### 2. User Code 格式不正确

- User Code 可能需要特定格式
- 可能需要前缀或后缀
- 可能有长度限制

### 3. API 返回错误

```json
{
  "code": 400,
  "message": "Invalid code"
}
```

---

## 🔍 查看实际返回值

### 步骤 1：重启并查看日志

```
1. 按 Shift+F5 停止
2. 按 F5 重新启动
3. 选择：🔥 DayBetter Services (调试模式)
```

### 步骤 2：添加集成并输入 User Code

```
1. 打开 http://localhost:8123
2. 设置 → 设备与服务 → 添加集成
3. 搜索 DayBetter
4. 输入你的 User Code
5. 点击提交
```

### 步骤 3：查看日志

在终端中查找这些日志：

```bash
grep "Integrate result" config/home-assistant.log
grep "Invalid integrate result" config/home-assistant.log
```

或者在 VS Code 的调试控制台中查看输出。

---

## 🎯 根据日志调整

### 情况 1：token 在嵌套对象中

如果日志显示：
```
Integrate result: {"data": {"token": "eyJ..."}, "code": 200}
```

修改代码：
```python
# config_flow.py
if not integrate_result or "data" not in integrate_result:
    errors["base"] = "invalid_code"
else:
    data = integrate_result["data"]
    if "token" not in data:
        errors["base"] = "invalid_code"
    else:
        token = data["token"]
```

### 情况 2：token 字段名不同

如果日志显示：
```
Integrate result: {"access_token": "eyJ...", "code": 200}
```

修改代码：
```python
# config_flow.py
token = integrate_result.get("token") or integrate_result.get("access_token")
if not token:
    errors["base"] = "invalid_code"
```

### 情况 3：API 返回错误

如果日志显示：
```
Integrate result: {"code": 400, "message": "Invalid code"}
```

说明 User Code 确实无效，需要检查：
- User Code 是否正确
- 是否需要特定格式
- 是否已过期

---

## 🛠 添加断点调试

### 在 config_flow.py 添加断点

```python
async def async_step_user(self, user_input):
    if user_input is not None:
        user_code = user_input[CONF_USER_CODE]  # ← 断点1：查看输入
        
        api = DayBetterApi()
        integrate_result = await api.integrate(user_code)  # ← 断点2：查看返回
        
        _LOGGER.debug("Integrate result: %s", integrate_result)
        
        # 在这里添加断点，查看 integrate_result 的具体内容
        if not integrate_result or "token" not in integrate_result:  # ← 断点3
            errors["base"] = "invalid_code"
```

### 在 daybetter_api.py 添加断点

```python
async def integrate(self, user_code: str) -> dict[str, Any]:
    if self._client is None:
        raise RuntimeError("DayBetterClient not available")
    
    result = await self._client.integrate(hass_code=user_code)  # ← 断点：查看原始返回
    
    # 添加调试输出
    _LOGGER.debug("Raw integrate result: %s", result)
    
    return result
```

---

## 📊 检查清单

在调试时检查：

### 1. User Code 输入
- [ ] User Code 是否正确输入
- [ ] 是否有空格或特殊字符
- [ ] 长度是否符合要求

### 2. API 调用
- [ ] `integrate_result` 是否为 None
- [ ] `integrate_result` 是什么类型（dict/str/其他）
- [ ] 包含哪些字段

### 3. Token 字段
- [ ] Token 字段名是什么（token/access_token/其他）
- [ ] Token 在顶层还是嵌套对象中
- [ ] Token 值是否为空

---

## 🧪 快速测试

### 测试 API 直接调用

在 Python 控制台测试：

```python
from daybetter_python import DayBetterClient

# 使用你的 User Code
client = DayBetterClient(token="")
result = await client.integrate(hass_code="YOUR_USER_CODE")
print("Result:", result)
print("Type:", type(result))
print("Keys:", result.keys() if isinstance(result, dict) else "N/A")
```

---

## 📝 常见返回格式示例

### 格式 1：直接返回
```json
{
  "token": "eyJ...",
  "code": 200,
  "message": "success"
}
```
**处理**：`token = result["token"]` ✅ 当前代码支持

### 格式 2：嵌套 data
```json
{
  "data": {
    "token": "eyJ..."
  },
  "code": 200
}
```
**处理**：需要修改为 `token = result["data"]["token"]`

### 格式 3：不同字段名
```json
{
  "access_token": "eyJ...",
  "code": 200
}
```
**处理**：需要修改为 `token = result.get("access_token")`

### 格式 4：错误响应
```json
{
  "code": 400,
  "message": "Invalid hass_code"
}
```
**处理**：这是正常的错误响应，User Code 确实无效

---

## 🎯 下一步行动

1. **重启 Home Assistant**（已添加调试日志）
2. **尝试添加集成**
3. **查看终端日志**，找到 "Integrate result:" 这一行
4. **将日志内容告诉我**，我会帮你分析并修复

---

## 💡 临时解决方案

如果你知道正确的返回格式，可以临时修改代码测试：

```python
# config_flow.py
integrate_result = await api.integrate(user_code)

# 临时调试：打印所有信息
print("=" * 50)
print("Type:", type(integrate_result))
print("Content:", integrate_result)
if isinstance(integrate_result, dict):
    print("Keys:", list(integrate_result.keys()))
    for key, value in integrate_result.items():
        print(f"  {key}: {value}")
print("=" * 50)

# 尝试多种可能的格式
token = None
if isinstance(integrate_result, dict):
    # 尝试直接获取
    token = integrate_result.get("token")
    if not token:
        # 尝试从 data 中获取
        data = integrate_result.get("data")
        if isinstance(data, dict):
            token = data.get("token")
    if not token:
        # 尝试 access_token
        token = integrate_result.get("access_token")

if not token:
    errors["base"] = "invalid_code"
else:
    # 继续正常流程
    ...
```

---

## 🔥 关键提示

**请在重启后，再次尝试添加集成，并将终端中的这行日志发给我**：

```
DEBUG (MainThread) [custom_components.daybetter_services.config_flow] Integrate result: {...}
```

或者：

```
ERROR (MainThread) [custom_components.daybetter_services.config_flow] Invalid integrate result: {...}
```

我会根据实际的返回格式帮你修复代码！🚀

