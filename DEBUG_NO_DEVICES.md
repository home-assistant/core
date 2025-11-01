# 🔍 调试：UI中看不到温湿度设备

## 🚨 问题现象

- ✅ 集成添加成功
- ❌ `Total devices: 0, Sensor devices: 0, PIDs: {}`
- ❌ UI中看不到温湿度设备

## 🔍 可能原因

### 1. **Token 问题**
- `integrate` 成功获取 token
- 但后续 API 调用时 token 可能无效

### 2. **API 调用失败**
- `fetch_devices()` 返回空数据
- `fetch_pids()` 返回空数据

### 3. **网络问题**
- API 服务器不可达
- 请求超时

## 🛠️ 调试步骤

### 步骤 1：重启并查看详细日志

```bash
# 停止当前进程
Shift+F5

# 重新启动
F5
# 选择：🔥 DayBetter Services (调试模式)
```

### 步骤 2：重新添加集成

1. 打开 http://localhost:8123
2. 设置 → 设备与服务 → 添加集成
3. 搜索 DayBetter
4. 输入 User Code
5. 点击提交

### 步骤 3：查看日志输出

**应该看到的新日志**：

```
DEBUG: fetch_devices raw result: {...}
INFO: Successfully fetched X devices
DEBUG: fetch_pids raw result: {...}
INFO: Successfully fetched PIDs: {...}
```

**如果看到错误**：

```
ERROR: DayBetter client not available for fetch_devices
ERROR: fetch_devices failed: {...}
ERROR: Exception in fetch_devices: ...
```

## 🔧 可能的问题和解决方案

### 问题 1：Token 无效

**现象**：
```
ERROR: fetch_devices failed: {"code": 401, "message": "Unauthorized"}
```

**解决**：
- 检查 token 是否正确传递
- 重新获取 token

### 问题 2：API 返回格式错误

**现象**：
```
DEBUG: fetch_devices raw result: {"code": 0, "message": "error"}
```

**解决**：
- 检查 API 文档
- 确认请求参数

### 问题 3：网络连接问题

**现象**：
```
ERROR: Exception in fetch_devices: aiohttp.ClientConnectorError
```

**解决**：
- 检查网络连接
- 确认 API 服务器地址

## 📊 预期的正确日志

### 成功情况：

```
DEBUG: Integrate result: {'code': 1, 'message': 'success', 'data': {'hassCodeToken': '...'}}
DEBUG: fetch_devices raw result: {'code': 1, 'data': [{'deviceId': 3734, ...}]}
INFO: Successfully fetched 7 devices
DEBUG: fetch_pids raw result: {'code': 1, 'data': {'sensor': 'P075', ...}}
INFO: Successfully fetched PIDs: {'sensor': 'P075', 'light': '...', 'switch': '...'}
INFO: DayBetter integration successful. Total devices: 7, Sensor devices: 1, PIDs: {...}
INFO: Setting up sensors for 1 sensor device(s)
INFO: Created temperature sensor for device0E24D2E62710
INFO: Created humidity sensor for device0E24D2E62710
INFO: Created battery sensor for device0E24D2E62710
```

### 失败情况：

```
ERROR: fetch_devices failed: {"code": 401, "message": "Invalid token"}
ERROR: Exception in fetch_devices: aiohttp.ClientTimeout
ERROR: DayBetter client not available for fetch_devices
```

## 🎯 下一步行动

1. **重启并测试** - 查看新的详细日志
2. **分析日志** - 确定具体失败原因
3. **修复问题** - 根据错误信息调整代码
4. **验证修复** - 重新测试集成添加

## 📝 如果仍然失败

请提供完整的日志输出，包括：

1. `integrate` 的结果
2. `fetch_devices` 的原始返回
3. `fetch_pids` 的原始返回
4. 任何异常信息

这样我可以准确定位问题并提供解决方案。

---

## 🚀 立即测试

**现在重启并重新添加集成，查看详细日志！**
