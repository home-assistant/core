# Xthings Cloud for Home Assistant

Xthings Cloud 是一个 Home Assistant 自定义集成组件，通过 Xthings Cloud API 将云端智能设备接入 Home Assistant，支持实时状态推送和远程控制。

## 支持的设备

| 设备类型 | HA 平台 | 功能 |
|---------|---------|------|
| 智能插座 (Switch) | switch / light | 开关控制，带亮度调节的自动注册为灯光 |
| 智能插头 (Plug) | switch / light | 开关控制，带亮度调节的自动注册为灯光 |
| 智能灯 (Light) | light | 开关、亮度、HS 颜色、色温调节 |
| 智能锁 (Lock) | lock + sensor | 锁定/解锁、卡住检测、电池电量 |
| 摄像头 (Camera) | camera | WebRTC 实时视频流、快照推送 |

## 核心功能

- **实时状态推送**：通过 WebSocket 长连接接收设备状态变更，无需等待轮询
- **设备上下线通知**：实时感知设备在线/离线状态
- **摄像头实时视频**：基于 AWS KVS WebRTC 的低延迟 P2P 视频流
- **摄像头快照推送**：云端推送最新截图，自动更新预览
- **Token 自动刷新**：access_token 过期时自动用 refresh_token 刷新，失败触发重新登录
- **两步验证 (2FA)**：支持邮箱验证码和手机验证码两种方式
- **远程访问**：内置 FRP 反向代理，一键开启外网访问，自动分配域名
- **30 分钟轮询兜底**：WebSocket 为主，定时轮询为辅，确保数据一致性
- **多语言支持**：英文 + 简体中文

## 安装方式

### 方式一：ZIP 包离线安装

1. 从发布页面下载最新版本的 ZIP 包
2. 解压后将 `xthings_cloud` 文件夹复制到 HA 配置目录下的 `custom_components/` 目录：
   ```
   <HA配置目录>/
   └── custom_components/
       └── xthings_cloud/
           ├── __init__.py
           ├── manifest.json
           ├── config_flow.py
           ├── ...
   ```
3. 重启 Home Assistant
4. 进入 **设置 → 设备与服务 → 添加集成**，搜索 `Xthings Cloud`

> 如果 `custom_components` 目录不存在，请手动创建。

### 方式二：HACS 安装（推荐）

1. 确保已安装 [HACS](https://hacs.xyz/)
2. 在 HACS 中点击右上角 **⋮ → 自定义存储库**
3. 输入仓库地址，类别选择 **集成**，点击添加
4. 在 HACS 集成列表中找到 `Xthings Cloud`，点击 **下载**
5. 重启 Home Assistant
6. 进入 **设置 → 设备与服务 → 添加集成**，搜索 `Xthings Cloud`

## 配置步骤

### 1. 添加集成

进入 **设置 → 设备与服务 → 添加集成**，搜索并选择 **Xthings Cloud**。

### 2. 登录账户

输入您的 Xthings Cloud 账户邮箱和密码。

### 3. 两步验证（如需要）

如果您的账户开启了两步验证，系统会自动发送 6 位数字验证码：
- **邮箱验证**：验证码发送到您的注册邮箱
- **手机验证**：验证码发送到您的绑定手机

输入验证码后即可完成登录。

### 4. 完成

登录成功后，HA 会自动发现您账户下的所有设备并创建对应的实体。

## 集成选项

在 **设置 → 设备与服务 → Xthings Cloud → 配置** 中可以调整以下选项：

### 启用远程访问

开启后，组件会自动：
1. 向 Xthings Cloud 申请一个专属子域名
2. 生成 FRP 客户端配置文件（`frpc.toml`）
3. 启动内置 FRP 客户端建立反向代理隧道
4. 自动配置 HA 的 HTTP 反向代理信任设置

开启后即可通过 `https://<subdomain>.gw.xthings.com` 从外网访问您的 Home Assistant。

关闭后会自动停止 FRP 客户端并清理配置文件。

> 远程访问基于 FRP 反向代理实现，支持 macOS (ARM64) 和 Linux (ARM64) 平台。

## 使用说明

### 设备控制

所有设备在添加后会自动出现在 HA 的概览页面：

- **开关/插头**：点击切换开关状态
- **灯光**：支持开关、亮度滑块、颜色选择器、色温调节
- **智能锁**：点击锁定/解锁，查看电池电量
- **摄像头**：查看实时视频流和最新截图

### 设备状态

- 设备在线时显示为可用状态，离线时显示为不可用
- 状态通过 WebSocket 实时更新，通常在设备操作后 1-2 秒内反映到 HA

### 自动化示例

```yaml
# 当智能锁解锁时发送通知
automation:
  - alias: "锁解锁通知"
    trigger:
      - platform: state
        entity_id: lock.back_door
        to: "unlocked"
    action:
      - service: notify.mobile_app
        data:
          message: "后门智能锁已解锁"

# 当摄像头检测到新截图时保存
automation:
  - alias: "保存摄像头截图"
    trigger:
      - platform: state
        entity_id: camera.front_door
    action:
      - service: camera.snapshot
        target:
          entity_id: camera.front_door
        data:
          filename: "/config/snapshots/front_door_{{ now().strftime('%Y%m%d_%H%M%S') }}.jpg"
```

## 故障排除

### 无法连接

- 确认网络可以访问 `api.cloud.xthings.com`
- 检查邮箱和密码是否正确
- 如果使用代理，确保 HA 的网络配置正确

### 设备不显示

- 确认设备已在 Xthings Cloud App 中绑定并在线
- 尝试在 **设置 → 设备与服务 → Xthings Cloud → ⋮ → 重新加载** 刷新

### 摄像头无视频

- 确认摄像头在线且固件为最新版本
- WebRTC 需要浏览器支持，建议使用 Chrome
- 检查 HA 日志中是否有 KVS 相关错误

### 远程访问无法连接

- 确认已在集成选项中开启「启用远程访问」
- 检查日志中是否有 `frpc` 启动错误
- 确认当前平台受支持（macOS ARM64 或 Linux ARM64）
- 如果提示反向代理错误，检查 `configuration.yaml` 中是否有 HTTP 信任代理配置（组件会自动添加）
- 重启 HA 使 HTTP 配置生效

### 查看日志

在 **设置 → 系统 → 日志** 中筛选 `custom_components.xthings_cloud` 查看集成日志。

也可以在 `configuration.yaml` 中启用调试日志：

```yaml
logger:
  logs:
    custom_components.xthings_cloud: debug
```

## 技术规格

| 项目 | 说明 |
|------|------|
| 最低 HA 版本 | 2025.6+ |
| Python 版本 | 3.13+ |
| 通信协议 | REST API + WebSocket + WebRTC |
| API 基础地址 | `https://api.cloud.xthings.com/ha` |
| WebSocket 地址 | `wss://api.cloud.xthings.com/api/ws` |
| 远程访问 | FRP 反向代理（KCP 协议） |
| 远程访问域名 | `https://<subdomain>.gw.xthings.com` |
| 支持平台 | macOS ARM64, Linux ARM64 |
| 轮询间隔 | 30 分钟（WebSocket 为主） |
| 心跳间隔 | 55 秒 |

## 许可证

本项目为 Xthings 公司内部开发，版权所有。
