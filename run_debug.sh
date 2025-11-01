#!/bin/bash
# DayBetter Services 集成本地调试启动脚本

set -e

echo "🚀 DayBetter Services 本地调试环境启动"
echo "=========================================="

# 检查 Python 版本
PYTHON_CMD="python3.12"
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "❌ 错误: 未找到 python3.12"
    echo "请安装 Python 3.12 或更高版本"
    exit 1
fi

echo "✅ Python 版本: $($PYTHON_CMD --version)"

# 检查是否在正确的目录
if [ ! -f "pyproject.toml" ]; then
    echo "❌ 错误: 请在 Home Assistant Core 根目录运行此脚本"
    exit 1
fi

# 创建配置目录
echo ""
echo "📁 准备配置目录..."
mkdir -p config/custom_components/daybetter_services

# 复制集成到 custom_components
echo "📋 复制集成文件..."
cp -r homeassistant/components/daybetter_services/* config/custom_components/daybetter_services/

# 检查并安装依赖
echo ""
echo "📦 检查依赖..."

if ! $PYTHON_CMD -c "import daybetter_services_python" 2>/dev/null; then
    echo "⚠️  未找到 daybetter-services-python，正在安装..."
    $PYTHON_CMD -m pip install daybetter-services-python==1.0.0
else
    echo "✅ daybetter-services-python 已安装"
fi

# 安装 Home Assistant（开发模式）
if ! $PYTHON_CMD -c "import homeassistant" 2>/dev/null; then
    echo "⚠️  未找到 homeassistant，正在安装开发依赖..."
    $PYTHON_CMD -m pip install -e .
else
    echo "✅ homeassistant 已安装"
fi

# 显示帮助信息
echo ""
echo "=========================================="
echo "🎯 启动选项："
echo "=========================================="
echo ""
echo "1️⃣  使用 custom_components 调试（推荐）:"
echo "   $PYTHON_CMD -m homeassistant --config ./config --debug"
echo ""
echo "2️⃣  使用核心组件调试:"
echo "   $PYTHON_CMD -m homeassistant --config ./config"
echo ""
echo "3️⃣  运行测试:"
echo "   pytest tests/components/daybetter_services/ -v"
echo ""
echo "=========================================="
echo "📝 提示："
echo "=========================================="
echo "- 启动后访问: http://localhost:8123"
echo "- 日志位置: ./config/home-assistant.log"
echo "- 调试文档: ./DEBUG_GUIDE.md"
echo "- 按 Ctrl+C 停止服务"
echo ""

# 询问用户是否立即启动
read -p "❓ 是否立即启动 Home Assistant? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🎉 正在启动 Home Assistant..."
    echo "=========================================="
    $PYTHON_CMD -m homeassistant --config ./config --debug
else
    echo ""
    echo "👋 准备完成！使用上述命令手动启动。"
fi

