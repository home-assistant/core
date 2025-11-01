#!/bin/bash
# 快速验证集成的代码质量和格式
# 使用方法: ./validate_integration.sh daybetter_services

set -e

INTEGRATION_NAME="${1:-daybetter_services}"
INTEGRATION_PATH="homeassistant/components/${INTEGRATION_NAME}"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo ""
echo -e "${BOLD}=========================================="
echo "  验证集成: ${INTEGRATION_NAME}"
echo -e "==========================================${NC}"
echo ""

# 检查集成目录
if [ ! -d "${INTEGRATION_PATH}" ]; then
    echo -e "${RED}✗ 错误: 找不到集成目录 ${INTEGRATION_PATH}${NC}"
    exit 1
fi

# 激活虚拟环境（如果存在）
if [ -d "venv" ]; then
    source venv/bin/activate
fi

ERROR_COUNT=0

# 1. Ruff Format 检查
echo -e "${BLUE}1. 代码格式检查 (Ruff Format)${NC}"
if ruff format --check "${INTEGRATION_PATH}" >/dev/null 2>&1; then
    echo -e "${GREEN}   ✓ 代码格式正确${NC}"
else
    echo -e "${YELLOW}   ⚠ 需要格式化，正在自动修复...${NC}"
    ruff format "${INTEGRATION_PATH}"
    echo -e "${GREEN}   ✓ 格式化完成${NC}"
fi
echo ""

# 2. Ruff Check
echo -e "${BLUE}2. 代码质量检查 (Ruff Check)${NC}"
if ruff check "${INTEGRATION_PATH}"; then
    echo -e "${GREEN}   ✓ 代码质量检查通过${NC}"
else
    echo -e "${RED}   ✗ 发现代码质量问题${NC}"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi
echo ""

# 3. Pylint 检查（只检查错误）
echo -e "${BLUE}3. 代码错误检查 (Pylint)${NC}"
if pylint "${INTEGRATION_PATH}"/*.py --disable=all --enable=F,E --score=no 2>/dev/null; then
    echo -e "${GREEN}   ✓ 未发现致命错误${NC}"
else
    echo -e "${RED}   ✗ 发现致命错误${NC}"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi
echo ""

# 4. JSON 文件验证
echo -e "${BLUE}4. JSON 文件验证${NC}"
JSON_ERROR=0
for json_file in "${INTEGRATION_PATH}"/*.json "${INTEGRATION_PATH}"/translations/*.json; do
    if [ -f "$json_file" ]; then
        if python3 -c "import json; json.load(open('$json_file'))" 2>/dev/null; then
            echo -e "${GREEN}   ✓ $(basename $json_file)${NC}"
        else
            echo -e "${RED}   ✗ $(basename $json_file) - 格式错误${NC}"
            JSON_ERROR=1
        fi
    fi
done
if [ $JSON_ERROR -eq 1 ]; then
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi
echo ""

# 5. 模块导入测试
echo -e "${BLUE}5. 模块导入测试${NC}"
IMPORT_CMD="import sys; sys.path.insert(0, '.'); "
for py_file in "${INTEGRATION_PATH}"/*.py; do
    if [ -f "$py_file" ] && [ "$(basename $py_file)" != "__init__.py" ]; then
        module_name=$(basename "$py_file" .py)
        IMPORT_CMD+="from homeassistant.components.${INTEGRATION_NAME} import ${module_name}; "
    fi
done

if python3 -c "$IMPORT_CMD" 2>/dev/null; then
    echo -e "${GREEN}   ✓ 所有模块导入成功${NC}"
else
    echo -e "${RED}   ✗ 模块导入失败${NC}"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi
echo ""

# 6. 文件列表
echo -e "${BLUE}6. 集成文件列表${NC}"
find "${INTEGRATION_PATH}" -type f \( -name "*.py" -o -name "*.json" \) | sort | while read file; do
    echo "   - ${file#${INTEGRATION_PATH}/}"
done
echo ""

# 总结
echo -e "${BOLD}=========================================="
if [ $ERROR_COUNT -eq 0 ]; then
    echo -e "${GREEN}✓ 所有检查通过！${NC}"
    echo -e "${BOLD}==========================================${NC}"
    echo ""
    echo -e "${GREEN}✓ 集成已准备好提交到官方仓库${NC}"
    echo ""
    echo "下一步操作："
    echo "  1. 确保已复制到官方目录: homeassistant/components/${INTEGRATION_NAME}/"
    echo "  2. 创建测试文件: tests/components/${INTEGRATION_NAME}/"
    echo "  3. 提交 PR 到 Home Assistant 官方仓库"
    exit 0
else
    echo -e "${RED}✗ 发现 $ERROR_COUNT 个问题${NC}"
    echo -e "${BOLD}==========================================${NC}"
    echo ""
    echo "请修复上述问题后重新运行验证"
    exit 1
fi

