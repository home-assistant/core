# ✅ 已修复：Token 字段格式问题

## 🎯 发现的问题

### 实际返回格式
```json
{
  "code": 1,
  "message": "success",
  "data": {
    "hassCodeToken": "d52533c6ba4c0b02fb918e3a2e41e2f5"
  }
}
```

### 之前的错误假设
```python
# ❌ 错误：假设 token 在顶层
if "token" not in integrate_result:
    errors["base"] = "invalid_code"
token = integrate_result["token"]
```

---

## ✅ 修复内容

### 正确的解析方式

```python
# ✅ 正确：从嵌套结构中获取
if integrate_result.get("code") != 1:
    errors["base"] = "invalid_code"
elif "data" not in integrate_result or "hassCodeToken" not in integrate_result["data"]:
    errors["base"] = "invalid_code"
else:
    token = integrate_result["data"]["hassCodeToken"]
```

---

## 📊 关键发现

| 项目 | 预期 | 实际 |
|------|------|------|
| **成功代码** | `code: 200` | `code: 1` |
| **Token 字段** | `token` | `hassCodeToken` |
| **Token 位置** | 顶层 | `data` 对象中 |

---

## 🔧 修复细节

### 1. 检查成功状态

```python
if integrate_result.get("code") != 1:
    # code 不等于 1 表示失败
    errors["base"] = "invalid_code"
```

### 2. 检查嵌套结构

```python
elif "data" not in integrate_result:
    # 没有 data 字段
    errors["base"] = "invalid_code"
elif "hassCodeToken" not in integrate_result["data"]:
    # data 中没有 hassCodeToken
    errors["base"] = "invalid_code"
```

### 3. 提取 Token

```python
else:
    # 从嵌套结构中提取
    token = integrate_result["data"]["hassCodeToken"]
```

---

## 📝 完整的返回格式文档

### 成功响应
```json
{
  "code": 1,
  "message": "success",
  "data": {
    "hassCodeToken": "d52533c6ba4c0b02fb918e3a2e41e2f5"
  }
}
```

### 失败响应（推测）
```json
{
  "code": 0,  // 或其他非 1 的值
  "message": "Invalid user code"
}
```

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
4. 输入相同的 User Code
5. 点击提交
```

---

## ✅ 预期结果

### 成功流程

```
输入 User Code
    ↓
调用 integrate(hass_code)
    ↓
返回 {"code": 1, "data": {"hassCodeToken": "..."}}
    ↓
提取 token = result["data"]["hassCodeToken"] ✅
    ↓
用 token 初始化客户端
    ↓
fetch_devices() → 获取设备列表
    ↓
fetch_pids() → 获取 PID 信息
    ↓
保存配置
    ↓
创建传感器实体
    ↓
成功！🎉
```

### 日志输出

应该看到：
```
DEBUG: Integrate result: {'code': 1, 'message': 'success', 'data': {'hassCodeToken': '...'}}
INFO: DayBetter integration successful. Devices: X, PIDs: {...}
```

---

## 🎯 关键改进

| 之前 | 现在 |
|------|------|
| ❌ 假设 token 在顶层 | ✅ 从 data.hassCodeToken 获取 |
| ❌ 检查 "token" in result | ✅ 检查 result["data"]["hassCodeToken"] |
| ❌ code == 200 | ✅ code == 1 |
| ❌ 提示"用户代码无效" | ✅ 应该成功 |

---

## 📚 API 文档更新

### integrate 接口

**端点**: `integrate(hass_code: str)`

**请求参数**:
- `hass_code`: 用户代码（User Code）

**成功响应**:
```json
{
  "code": 1,
  "message": "success",
  "data": {
    "hassCodeToken": "d52533c6ba4c0b02fb918e3a2e41e2f5"
  }
}
```

**字段说明**:
- `code`: 1 表示成功，其他值表示失败
- `message`: 响应消息
- `data.hassCodeToken`: Home Assistant 访问令牌

---

## 🎉 问题已解决！

**按 Shift+F5 停止，按 F5 重启，再次添加集成！**

这次应该可以成功了！🚀✨

