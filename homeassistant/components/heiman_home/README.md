# Heiman Home Assistant Integration

海曼智能家居 Home Assistant 集成组件，支持通过 OAuth 2.0 认证连接海曼云端 API，实现对海曼智能设备的控制和管理。

## 功能特性

- ✅ OAuth 2.0 认证（安全、标准）
- ✅ 自动发现设备
- ✅ 实时状态同步
- ✅ 支持多种设备类型：
  - 烟雾报警器
  - 一氧化碳报警器
  - 水浸探测器
  - 门磁探测器
  - 红外探测器（人体感应）
  - 温湿度传感器
  - 智能插座/开关
  - 安防警戒模式控制
- ✅ 固件版本显示（升级功能待 API 支持）
- ✅ 多语言支持（中文/英文）

## 安装方法

### 方法一：手动安装

1. 将此目录复制到 Home Assistant 的 `custom_components` 文件夹：
   ```bash
   cp -r custom_components/heiman_home /config/custom_components/heiman_home
   ```

2. 确保已安装 heiman-connect 库：
   ```bash
   pip install heiman-connect==1.0.1
   ```

3. 重启 Home Assistant

### 方法二：使用 HACS（推荐）

待添加到此仓库后，可通过 HACS 安装。

## 配置步骤

1. 在 Home Assistant UI 中，进入 **设置** > **设备与服务**
2. 点击右下角 **添加集成**
3. 搜索 "Heiman" 或 "海曼"
4. 点击 **提交**
5. 系统会打开浏览器跳转到海曼授权页面
6. 使用您的海曼账号登录并授权
7. 授权成功后会自动跳转回 Home Assistant
8. 完成配置，设备将自动添加到系统中

## OAuth 2.0 配置

### 获取客户端凭证

在使用此集成之前，您需要从海曼开发者平台获取 OAuth 2.0 客户端 ID 和密钥：

1. 访问海曼开发者平台
2. 创建新的应用程序
3. 记录 Client ID 和 Client Secret
4. 在 Home Assistant 的 `configuration.yaml` 中添加：

```yaml
application_credentials:
  - domain: heiman_home
    client_id: YOUR_CLIENT_ID
    client_secret: YOUR_CLIENT_SECRET
```

或者通过 UI 配置：
**设置** > **设备与服务** > **应用凭证** > **添加凭证**

## 支持的实体类型

### Binary Sensor（二进制传感器）
- 烟雾报警状态
- 一氧化碳报警状态
- 水浸检测状态
- 门窗开关状态
- 人体移动检测

### Sensor（传感器）
- 温度
- 湿度
- 电池电量
- 电压
- 功率
- 电量
- 信号强度

### Select（选择器）
- 警戒模式（撤防/在家布防/外出布防/睡眠布防）

### Switch（开关）
- 智能插座
- 灯光控制
- 继电器开关

### Update（更新）
- 固件版本显示
- 固件升级（待 API 支持）

## 故障排除

### 认证失败

如果认证失败，请检查：
1. OAuth 凭证是否正确配置
2. 海曼账号密码是否正确
3. 网络连接是否正常
4. 查看 Home Assistant 日志获取详细错误信息

### Token 过期

当 Token 过期时，系统会自动提示重新认证：
1. 进入 **设置** > **设备与服务**
2. 找到 Heiman 集成
3. 点击 **重新配置**
4. 按照提示完成重新认证

### 设备未显示

如果某些设备未显示，请检查：
1. 设备是否已正确连接到海曼网关
2. 设备是否在线
3. 等待数据协调器刷新（默认 60 秒）
4. 尝试重新加载集成

## 高级配置

### 自定义更新间隔

在 `configuration.yaml` 中修改（未来版本支持）：

```yaml
heiman_home:
  update_interval: 30  # 秒，默认 60 秒
```

## 开发调试

### 启用调试日志

```yaml
logger:
  default: warning
  logs:
    custom_components.heiman_home: debug
    heimanconnect: debug
```

### 查看日志

```bash
tail -f /config/home-assistant.log | grep heiman
```

## 技术架构

- **认证方式**: OAuth 2.0
- **通信协议**: HTTPS + MQTT（未来支持）
- **数据更新**: 轮询（60 秒间隔）
- **依赖库**: heiman-connect==1.0.1
- **Home Assistant 版本要求**: 2024.1+
- **Python 版本要求**: 3.11+

## 文件结构

```
custom_components/heiman_home/
├── __init__.py                 # 组件入口
├── manifest.json               # 组件清单
├── const.py                    # 常量定义
├── config_flow.py              # 配置流程
├── application_credentials.py  # OAuth 凭证管理
├── api.py                      # API 封装
├── coordinator.py              # 数据协调器
├── sensor.py                   # 传感器平台
├── binary_sensor.py            # 二进制传感器平台
├── select.py                   # 选择器平台
├── switch.py                   # 开关平台
├── update.py                   # 更新器平台
├── strings.json                # 本地化字符串
└── translations/
    ├── en.json                 # 英文翻译
    └── zh-Hans.json            # 简体中文翻译
```

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 联系方式

- 作者：@haiman
- Email: support@heiman.com
- 官网：https://www.heiman.com

## 致谢

感谢 SmartThings 集成提供的优秀代码参考！
