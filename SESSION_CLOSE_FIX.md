# Unclosed Client Session 错误修复

## 问题分析

### 错误信息
```
ERROR: Unclosed client session (None)
ERROR: Unclosed connector (None)
```

### 错误堆栈
```
File "config_flow.py", line 40, in async_step_user
    integrate_result = await api.integrate(user_code)
File "daybetter_python/client.py", line 45, in _get_session
    self._session = aiohttp.ClientSession()
```

### 根本原因
在 `config_flow.py` 的 `finally` 块中：
```python
finally:
    await api_with_token.close()  # ❌ 当 api_with_token 为 None 时会出错
finally:
    await api.close()  # ❌ 虽然 api 不应该为 None，但最好也检查
```

当以下情况发生时，`api_with_token` 会是 `None`：
1. Token 验证失败
2. `integrate_result` 格式错误
3. 在创建 `api_with_token` 之前就抛出异常

## 修复方案

### 修复后的代码
```python
finally:
    if api_with_token is not None:
        await api_with_token.close()
finally:
    if api is not None:
        await api.close()
```

### 修复的文件
- `config/custom_components/daybetter_services/config_flow.py`

## 验证结果

### ✅ 功能正常
从日志中可以看到：
```
Line 416: Registered new sensor.daybetter_services entity: sensor.75_temperature
Line 417: Registered new sensor.daybetter_services entity: sensor.75_humidity
Line 418: Registered new sensor.daybetter_services entity: sensor.75_battery
```

**说明**：
- ✅ 集成已成功添加
- ✅ 传感器已成功创建
- ✅ 数据每 30 秒更新一次

### ✅ 会话管理
修复后应该不再出现 `Unclosed client session` 错误。

## 下一步

**重启测试**以验证错误是否完全消失：
1. 删除现有的集成
2. 按 `Shift+F5` 停止 Home Assistant
3. 按 `F5` 重新启动
4. 重新添加集成
5. 查看是否还有 `Unclosed client session` 错误

**预期结果**：
- ✅ 不再出现 `Unclosed client session` 错误
- ✅ 不再出现 `Unclosed connector` 错误
- ✅ 传感器正常显示和更新

## 传感器状态

从日志中看到集成已经在正常工作：
- 数据每 30 秒更新一次（Line 414, 419, 420, 421, 422, 423...）
- 更新时间约 0.4 秒（success: True）

**现在可以在 Home Assistant UI 中查看传感器的实时数据了！** 🎉

