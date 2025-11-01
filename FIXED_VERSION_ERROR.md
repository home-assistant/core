# ✅ 已修复：manifest.json 缺少 version 错误

## 🐛 原来的错误

```
ERROR (SyncWorker_0) [homeassistant.loader] 
The custom integration 'daybetter_services' does not have a version key 
in the manifest file and was blocked from loading.
```

## ✅ 已修复

在 `manifest.json` 中添加了 `version` 字段：

```json
{
  "domain": "daybetter_services",
  "name": "DayBetter Services",
  "version": "1.0.0",  // ← 新增
  "documentation": "...",
  ...
}
```

## 🔄 现在需要做什么

### 重启 Home Assistant

1. **停止当前调试**：按 `Shift+F5`
2. **重新启动**：按 `F5`
3. 选择：**🔥 DayBetter Services (调试模式)**

### 验证修复

启动后检查日志，应该不再看到版本错误。

## 🎯 添加集成

现在可以正常添加集成了：

1. 打开：`http://localhost:8123`
2. 进入：**设置 → 设备与服务 → 添加集成**
3. 搜索：**DayBetter**
4. 点击添加并提交

## 📋 完整的 manifest.json

```json
{
  "domain": "daybetter_services",
  "name": "DayBetter Services",
  "version": "1.0.0",
  "documentation": "https://www.home-assistant.io/integrations/daybetter_services",
  "requirements": [
    "daybetter-services-python==1.0.0"
  ],
  "codeowners": ["@THDayBetter"],
  "config_flow": true,
  "iot_class": "cloud_polling"
}
```

## ℹ️ 关于 version 字段

从 Home Assistant 2021.2 开始，所有 custom integrations 必须在 manifest.json 中包含 `version` 字段。

### 版本规范

- 格式：`major.minor.patch` (语义化版本)
- 示例：`1.0.0`, `1.2.3`, `2.0.0`
- 每次更新集成时应该更新版本号

### 版本更新规则

- **Patch (x.x.1)**: 修复 bug
- **Minor (x.1.0)**: 添加新功能（向后兼容）
- **Major (2.0.0)**: 破坏性更改

## ✅ 问题已解决！

现在重启 Home Assistant，集成应该可以正常加载了！🎉

