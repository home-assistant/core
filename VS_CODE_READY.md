# ✅ VS Code 调试环境已配置完成！

## 🎉 现在你可以直接在 VS Code 中调试了！

---

## 🚀 一键启动（3 步）

### 1️⃣ 安装依赖（首次）

按 `Ctrl+Shift+P`，输入 `Tasks`，选择：
```
🚀 DayBetter: 安装依赖
```

### 2️⃣ 启动调试

按 **F5**，在下拉菜单选择：
```
🔥 DayBetter Services (调试模式)
```

### 3️⃣ 打开浏览器

访问：**http://localhost:8123**

---

## 🎯 可用的调试配置

按 **F5** 后可以选择：

| 配置名称 | 用途 |
|---------|------|
| 🔥 **DayBetter Services (调试模式)** | 启动完整的 Home Assistant（推荐） |
| 🧪 **DayBetter Services Tests** | 运行所有集成测试 |
| **Home Assistant: Debug Current Test File** | 调试当前打开的测试文件 |

---

## 📋 可用的任务

按 `Ctrl+Shift+P` → `Tasks: Run Task`：

- 🚀 **DayBetter: 安装依赖** - 一键安装 PyPI 包
- 🧪 **DayBetter: 运行测试** - 运行所有测试
- 📋 **DayBetter: 复制到 custom_components** - 复制代码到调试目录

---

## 💡 快速上手

### 添加断点

在代码行号左侧点击，出现红点：

```python
# homeassistant/components/daybetter_services/sensor.py
async def async_setup_entry(...):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    devices = coordinator.data or []  # ← 点这里加断点
```

### 启动调试

1. 按 **F5**
2. 选择 **🔥 DayBetter Services (调试模式)**
3. 代码会在断点处暂停

### 查看变量

断点暂停时：
- 左侧 **变量** 面板查看所有变量
- 鼠标悬停在代码上查看值
- 在 **调试控制台** 输入变量名

### 单步执行

| 快捷键 | 功能 |
|--------|------|
| **F5** | 继续执行 |
| **F10** | 单步跳过 |
| **F11** | 单步进入函数 |
| **Shift+F11** | 跳出函数 |
| **Shift+F5** | 停止调试 |

---

## 📚 详细文档

| 文档 | 说明 |
|------|------|
| [VSCODE_DEBUG_GUIDE.md](VSCODE_DEBUG_GUIDE.md) | **VS Code 完整调试指南** ⭐ |
| [DEBUG_GUIDE.md](DEBUG_GUIDE.md) | 命令行调试指南 |
| [QUICK_START.md](QUICK_START.md) | 快速参考 |
| [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md) | 集成功能说明 |

---

## 🎯 常见使用场景

### 场景 1：调试为什么传感器没创建

1. 在 `sensor.py` 的 `async_setup_entry` 添加断点
2. 按 **F5** 启动
3. 查看 `devices` 变量内容
4. 检查 `device.get("type")` 是否为 5

### 场景 2：调试 API 数据格式

1. 在 `daybetter_api.py` 的 `fetch_devices` 添加断点
2. 按 **F5** 启动
3. 查看 `statuses` 原始数据
4. 单步执行看数据如何转换

### 场景 3：运行测试

1. 按 **F5**
2. 选择 **🧪 DayBetter Services Tests**
3. 查看终端中的测试结果

---

## 🔍 实用技巧

### 技巧 1：条件断点

右键断点 → **编辑断点** → 添加条件：
```python
device.get("type") == 5
```

### 技巧 2：监视变量

**调试面板** → **监视** → 添加：
```python
len(devices)
coordinator.data
```

### 技巧 3：查看日志

启动后在终端运行：
```bash
tail -f config/home-assistant.log | grep daybetter
```

---

## ⚡ 现在开始！

**按 F5 键** → 选择 **🔥 DayBetter Services (调试模式)** → 开始调试！

---

## 📞 需要帮助？

- 查看 [VSCODE_DEBUG_GUIDE.md](VSCODE_DEBUG_GUIDE.md) 获取详细说明
- 所有文档都在项目根目录

**祝调试愉快！** 🎉

