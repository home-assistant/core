# DayBetter Services 集成本地调试指南

## 📋 前提条件

1. **Python 3.12 或更高版本**
2. **你的 PyPI 包已发布**: `daybetter-services-python==1.0.0`

## 🚀 快速开始

### 方法一：使用开发模式运行 Home Assistant

```bash
# 1. 进入 Home Assistant Core 目录
cd /home/cp/core

# 2. 安装你的 PyPI 包
python3.12 -m pip install daybetter-services-python==1.0.0

# 3. 安装 Home Assistant 开发依赖
python3.12 -m pip install -e .

# 4. 运行 Home Assistant（指定配置目录）
python3.12 -m homeassistant --config ./config
```

### 方法二：使用 custom_components 测试（推荐调试）

```bash
# 1. 复制集成到 custom_components
mkdir -p config/custom_components/daybetter_services
cp -r homeassistant/components/daybetter_services/* config/custom_components/daybetter_services/

# 2. 安装依赖
python3.12 -m pip install daybetter-services-python==1.0.0
python3.12 -m pip install -e .

# 3. 运行 Home Assistant
python3.12 -m homeassistant --config ./config
```

## 🔧 配置集成

### 通过 UI 配置（推荐）

1. 启动后访问: `http://localhost:8123`
2. 进入 **设置** → **设备与服务**
3. 点击 **添加集成**
4. 搜索 "DayBetter Services"
5. 输入必要的配置信息

### 通过配置文件（需要先创建 config_flow.py）

由于当前集成暂无 `config_flow.py`，建议先创建一个简单的配置入口，或通过代码直接测试：

```yaml
# config/configuration.yaml 添加
daybetter_services:
```

## 📝 查看日志

### 实时日志

```bash
# 在运行 Home Assistant 的终端中会看到实时日志
# 或者查看日志文件
tail -f config/home-assistant.log
```

### 日志级别配置

在 `config/configuration.yaml` 中已配置：

```yaml
logger:
  default: info
  logs:
    homeassistant.components.daybetter_services: debug
    custom_components.daybetter_services: debug
```

## 🧪 运行测试

```bash
# 运行集成的所有测试
pytest tests/components/daybetter_services/ -v

# 运行特定测试
pytest tests/components/daybetter_services/test_sensor.py -v

# 运行测试并显示打印输出
pytest tests/components/daybetter_services/ -v -s

# 运行测试并生成覆盖率报告
pytest tests/components/daybetter_services/ --cov=homeassistant.components.daybetter_services
```

## 🐛 调试技巧

### 1. 使用 Python 调试器

在代码中添加断点：

```python
# 在 sensor.py 或其他文件中
import pdb; pdb.set_trace()
```

### 2. 添加日志输出

```python
import logging
_LOGGER = logging.getLogger(__name__)

_LOGGER.debug("设备数据: %s", devices)
_LOGGER.info("温度传感器值: %s", temperature)
_LOGGER.warning("未找到设备")
_LOGGER.error("API 调用失败: %s", error)
```

### 3. 使用 VS Code 调试

创建 `.vscode/launch.json`：

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Home Assistant",
            "type": "python",
            "request": "launch",
            "module": "homeassistant",
            "args": [
                "--config",
                "./config",
                "--debug"
            ],
            "justMyCode": false,
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            }
        }
    ]
}
```

### 4. 模拟 API 响应

在 `daybetter_api.py` 中临时硬编码数据：

```python
async def fetch_devices(self) -> list[dict[str, Any]]:
    # 临时返回模拟数据用于测试
    return [
        {
            "deviceName": "test_device",
            "type": 5,
            "online": True,
            "temp": 235,  # 23.5°C
            "humi": 600,  # 60.0%
            "battery": 99
        }
    ]
```

## 📦 验证集成加载

启动后检查日志，应该看到：

```
INFO (MainThread) [homeassistant.setup] Setting up daybetter_services
INFO (MainThread) [homeassistant.setup] Setup of domain daybetter_services took 0.0 seconds
DEBUG (MainThread) [homeassistant.components.daybetter_services] Setting up sensors for X devices
```

## 🔍 常见问题

### 问题 1: 导入错误 "No module named 'daybetter_services_python'"

**解决方案**:
```bash
python3.12 -m pip install daybetter-services-python==1.0.0
```

### 问题 2: 集成未显示在 UI 中

**原因**: 缺少 `config_flow.py` 和 `strings.json`

**临时解决方案**: 使用 custom_components 方式，或创建配置流程

### 问题 3: 传感器未创建

**检查**:
1. API 是否返回 `type=5` 的设备
2. 日志中是否有错误信息
3. 使用调试器查看 `coordinator.data` 的值

### 问题 4: 数值不正确

**检查**:
- API 返回的 `temp` 和 `humi` 值
- 确认缩放逻辑（除以 10）是否正确
- 查看 `_scale()` 函数的日志输出

## 📊 开发工作流

```bash
# 1. 修改代码
vim homeassistant/components/daybetter_services/sensor.py

# 2. 运行测试
pytest tests/components/daybetter_services/ -v

# 3. 检查代码质量
ruff check homeassistant/components/daybetter_services/
mypy homeassistant/components/daybetter_services/

# 4. 本地运行验证
python3.12 -m homeassistant --config ./config

# 5. 提交代码
git add .
git commit -m "feat: update sensor logic"
```

## 🎯 下一步

1. **创建 config_flow.py** - 添加 UI 配置流程
2. **添加 strings.json** - 支持多语言
3. **创建 translations/** - 中文翻译
4. **添加更多测试** - 提高代码覆盖率
5. **优化错误处理** - 更好的用户体验

## 💡 提示

- 修改代码后需要重启 Home Assistant
- 如果使用 custom_components，记得同步更新
- 生产环境使用前，确保所有测试通过
- 考虑添加配置验证和错误恢复机制

## 📚 参考资源

- [Home Assistant 开发者文档](https://developers.home-assistant.io/)
- [集成开发指南](https://developers.home-assistant.io/docs/creating_component_index)
- [传感器平台文档](https://developers.home-assistant.io/docs/core/entity/sensor)

