# 🚀 DayBetter Services - 快速开始

## 一键启动调试

```bash
cd /home/cp/core
./run_debug.sh
```

访问: `http://localhost:8123`

---

## 常用命令

### 开发调试
```bash
# 启动 Home Assistant（调试模式）
python3.12 -m homeassistant --config ./config --debug

# 查看实时日志
tail -f config/home-assistant.log
```

### 运行测试
```bash
# 运行所有测试
pytest tests/components/daybetter_services/ -v

# 运行特定测试
pytest tests/components/daybetter_services/test_sensor.py::test_sensor_setup -v
```

### 代码检查
```bash
# 检查代码风格
ruff check homeassistant/components/daybetter_services/

# 类型检查
mypy homeassistant/components/daybetter_services/
```

---

## 目录结构

```
/home/cp/core/
├── homeassistant/components/daybetter_services/  # 集成源码
│   ├── __init__.py
│   ├── manifest.json
│   ├── const.py
│   ├── coordinator.py
│   ├── daybetter_api.py
│   └── sensor.py
│
├── tests/components/daybetter_services/          # 测试代码
│   ├── __init__.py
│   └── test_sensor.py
│
├── config/                                       # 调试配置
│   ├── configuration.yaml
│   └── custom_components/                        # 开发时使用
│
├── DEBUG_GUIDE.md                                # 详细调试文档
├── INTEGRATION_SUMMARY.md                        # 开发总结
└── run_debug.sh                                  # 启动脚本
```

---

## API 数据示例

### 输入（HTTP API）
```json
[{
    "deviceName": "device06068838ADDE",
    "type": 5,
    "temp": 235,
    "humi": 600
}]
```

### 输出（Home Assistant 实体）
- `sensor.device06068838adde_temperature` = 23.5°C
- `sensor.device06068838adde_humidity` = 60.0%

---

## 故障排查

### 问题：集成未加载
```bash
# 检查日志
grep -i "daybetter" config/home-assistant.log

# 验证 manifest
cat homeassistant/components/daybetter_services/manifest.json
```

### 问题：传感器未创建
```bash
# 检查设备数据
# 在 daybetter_api.py 中添加:
_LOGGER.debug("Device data: %s", statuses)
```

### 问题：数值不正确
```python
# 验证缩放逻辑
# temp: 235 → 23.5 (除以10)
# humi: 600 → 60.0 (除以10)
```

---

## 下一步

1. ✅ 代码已完成
2. 📝 运行测试验证
3. 🐛 本地调试测试
4. 📦 准备提交 PR

---

## 需要帮助？

查看详细文档:
- `DEBUG_GUIDE.md` - 完整调试指南
- `INTEGRATION_SUMMARY.md` - 功能说明
- [Home Assistant 开发者文档](https://developers.home-assistant.io/)

