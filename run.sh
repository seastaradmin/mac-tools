#!/bin/bash

# Mac截图语音工具启动脚本

set -e

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查Python版本
python_version=$(python3 --version 2>&1)
if [[ $? -ne 0 ]]; then
    echo "错误: 未找到Python3，请先安装Python3"
    exit 1
fi
echo "Python版本: $python_version"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖（requirements 未变化时跳过，避免每次启动都等待 pip）
REQ_STAMP="venv/.requirements.sha256"
REQ_HASH=$(shasum -a 256 requirements.txt | awk '{print $1}')
if [ ! -f "$REQ_STAMP" ] || [ "$(cat "$REQ_STAMP")" != "$REQ_HASH" ]; then
    echo "检查并安装依赖..."
    python3 -m pip install -r requirements.txt -q
    echo "$REQ_HASH" > "$REQ_STAMP"
else
    echo "依赖已就绪，跳过安装"
fi

# 检查MIMO_API_KEY
if [ -z "$MIMO_API_KEY" ]; then
    echo "提示: 可在应用设置中配置 MiMo API Key；也可设置 MIMO_API_KEY 环境变量"
fi

# 运行程序
echo "启动Mac截图语音工具..."
python3 main.py
