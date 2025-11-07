# Home Assistant Marstek 集成

[English](./README.md) | [简体中文](./doc/README_zh.md)

Marstek 集成是一个由 Marstek 官方提供的用于 Home Assistant 的集成组件，其可用于监控和控制 Marstek 设备。

## 系统要求

> Home Assistant 版本要求:
>
> - Core 版本：^2025.10.0
> - HAOS 版本：^15.0
>
> Marstek 设备和 Home Assistant 需要在同一局域网内
>
> 需要Marstek 设备打开OPEN API使能

## 安装

### 方法1: 通过git clone拉取

```bash
cd config
git clone https://github.com/MarstekEnergy/ha_marstek.git
```

### 方法2: 通过Samba或SSH手动安装

下载Marstek集成文件并将 `custom_components/Marstek 文件夹复制到 Home Assistant 的 `config/custom_components/` 目录下。

## 通信协议

### UDP 通信
- 默认端口：30000
- 发现超时：10秒
- 通信模式：
  - OEPN API
  - 双向 UDP 通信

- ES.SetMode请求重试机制：
  - 优先原则：ES.SetMode指令下发时将停止所有轮询请求
  - 加入指数规避


### 主要命令集

当前版本下, 设备支持以下主要命令(由OPEN API提供)：

- 设备发现：`Marstek.GetDevice`
- 电池状态：`Bat.GetStatus`
- 能量存储状态：`ES.GetStatus`
- 模式设置：`ES.SetMode`
- 光伏状态(部分设备有效)：`PV.GetStatus`


## 配置说明

1. 通过 Home Assistant UI 界面添加集成
2. 集成将自动搜索局域网内的 Marstek 设备: 通常显示"[设备名] [固件版本] ([wifi名称]) - [设备ip]"
3. 选择要添加的设备并提交确认, 设备将自动启用UDP轮询设备状态
4. 添加自动化: 目前提供charge, discharge, stop三种模式控制设备充放电

## 数据更新机制

- 使用本地推送机制 (UDP轮询) 接收设备状态更新
- 实时响应设备状态变化
- 保持与设备的持续连接

## 错误处理

集成实现了以下错误处理机制：

- 网络连接中断自动重连
- 设备响应超时处理
- 配置错误提示

## 注意事项

1. 使用集成前需确保设备开启OPEN API使能
2. 确保设备和 Home Assistant 在同一网段
3. UDP 端口 30000 需要保持开放
4. 首次配置时需要等待设备发现过程完成

## 技术支持

如有技术问题，请通过以下方式获取支持：

- 在 [Home Assistant 社区](https://community.home-assistant.io/) 交流
- 提交 GitHub Issue
- 联系设备厂商技术支持

## 更新日志

### v0.1.0 
- 初始版本发布
- 设备自动发现
- 支持基本设备状态监控功能和充放电指令控制

## 常见问题

1. 支持哪些设备?

   支持新版本固件下的Venus A, Venus D, Venus E3.0以及其他支持OPEN API通信的Marstek设备

2. 为什么我搜索不到设备?

   - 未开启OPEN API使能

   - 确保Marstek设备和Home Assistant连在同一个网段, 并且保持30000端口的开放
   - 集成通过UDP广播搜索设备, 可能存在网络波动影响设备和HA的通信, 建议重试

3. 何为OPEN API?

   OPEN API为Marstk设备固件提供的通信接口, 用于在局域网环境下查询设备状态, 以及部分指令控制。**注意, OPEN API目前不是默认开启, 需要官方MQTT协议开启。**或在未来新版本Marstek APP提供开启入口。
