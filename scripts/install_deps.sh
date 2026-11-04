#!/usr/bin/env bash
# install_deps.sh — 在【真机/目标机】上运行，从 deps/ 离线安装全部依赖(可选连编译)
#
# 前提: Ubuntu 22.04 + 已装 ROS 2 Humble + Python 3.10 + x86_64
# 用法:
#   ./scripts/install_deps.sh           # 只装依赖(pip wheel + apt deb)并自检
#   ./scripts/install_deps.sh --build   # 装完依赖后接着 colcon build --symlink-install
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIP_DIR="$ROOT/deps/pip"
APT_DIR="$ROOT/deps/apt"

# ---------- 0) 环境自检(不匹配只警告，硬性不兼容才退出) ----------
ARCH="$(uname -m)"
if [[ "$ARCH" != "x86_64" ]]; then
    echo "错误: 本机架构 $ARCH 与 deps/ 中的 x86_64 包不匹配，无法安装。" >&2
    exit 1
fi
PYVER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [[ "$PYVER" != "3.10" ]]; then
    echo "错误: 需要 Python 3.10(Ubuntu 22.04 默认)，当前为 $PYVER。" >&2
    exit 1
fi
if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    if [[ "${VERSION_ID:-}" != "22.04" ]]; then
        echo "警告: 检测到 Ubuntu ${VERSION_ID:-未知}(非 22.04)，deb/wheel 版本可能不匹配。" >&2
    fi
fi
if [[ ! -d "$PIP_DIR" || -z "$(ls -A "$PIP_DIR" 2>/dev/null)" ]]; then
    echo "错误: $PIP_DIR 为空，请先在有网络的机器上运行 scripts/download_deps.sh。" >&2
    exit 1
fi
if [[ -z "$(ls -A "$APT_DIR" 2>/dev/null)" ]]; then
    echo "错误: $APT_DIR 为空，请先在有网络的机器上运行 scripts/download_deps.sh。" >&2
    exit 1
fi

SUDO="sudo"
[[ "$(id -u)" -eq 0 ]] && SUDO=""

# ---------- 1) 离线安装 ROS 2 apt 包(已装的同名包会被 apt 自动保持/覆盖，无害) ----------
echo "==> [1/3] 离线安装 ROS 2 相关 .deb 包..."
if ! $SUDO apt-get install -y --no-download "$APT_DIR"/*.deb; then
    echo "apt 离线安装失败(常见原因: 缺更深层的系统依赖或 apt 列表过旧)。" >&2
    echo "可尝试:  $SUDO dpkg -i $APT_DIR/*.deb && $SUDO apt-get install -y -f" >&2
    exit 1
fi

# ---------- 2) 离线安装 Python wheel(requirements.txt + pin-pink --no-deps) ----------
echo "==> [2/3] 离线安装 Python wheel 包..."
# 命门: 先 --no-deps 装 pin-pink, 阻止 pip 拉入遮蔽版 pin(P-016 M3 红线)。
# pinocchio 不由 pip 提供, 走上面第 1 步的 ros-humble-pinocchio deb。
if ! ls "$PIP_DIR"/pin_pink-*.whl >/dev/null 2>&1; then
    echo "错误: $PIP_DIR 缺 pin_pink wheel, 请重跑 scripts/download_deps.sh。" >&2
    exit 1
fi
python3 -m pip install --no-index --find-links="$PIP_DIR" --no-deps "$PIP_DIR"/pin_pink-*.whl
# 再装其余依赖(requirements.txt 刻意不含 pin/pin-pink)
# --no-index: 完全不访问 PyPI; 权限不足时 pip 会自动降级为 --user 安装
python3 -m pip install --no-index --find-links="$PIP_DIR" -r "$ROOT/requirements.txt"

# ---------- 3) 导入自检 ----------
echo "==> [3/3] 导入自检..."
# pinocchio 由 apt 的 ros-humble-pinocchio 提供, 必须 source ROS 后才能导入
if [[ -f /opt/ros/humble/setup.bash ]]; then
    # shellcheck disable=SC1091
    source /opt/ros/humble/setup.bash
else
    echo "警告: 未找到 /opt/ros/humble/setup.bash, pinocchio 导入自检将失败。" >&2
fi
python3 - <<'EOF'
import sys
mods = ["numpy", "scipy", "pinocchio", "pink", "qpsolvers",
        "proxsuite", "osqp", "loop_rate_limiters"]
failed = []
for m in mods:
    try:
        mod = __import__(m)
        print(f"  OK  {m} {getattr(mod, '__version__', '?')}")
    except Exception as e:
        failed.append(m)
        print(f"  FAIL {m}: {e}", file=sys.stderr)
# 红线: numpy 必须 1.x(2.x 与 apt pinocchio ABI 不兼容, import 段错误, 本机实证)
try:
    import numpy
    assert numpy.__version__.startswith("1."), f"numpy {numpy.__version__} 不是 1.x, 会段错误"
except Exception as e:
    failed.append("numpy-1.x-check")
    print(f"  FAIL numpy-1.x-check: {e}", file=sys.stderr)
sys.exit(1 if failed else 0)
EOF
echo "依赖安装完成。"

# ---------- 4) 可选: 接着编译 ----------
if [[ "${1:-}" == "--build" ]]; then
    echo "==> 开始编译 colcon 工作区..."
    source /opt/ros/humble/setup.bash
    cd "$ROOT"
    colcon build --symlink-install
    echo
    echo "编译完成。使用前先: source $ROOT/install/setup.bash"
fi
