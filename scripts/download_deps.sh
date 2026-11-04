#!/usr/bin/env bash
# download_deps.sh — 在【有网络】的机器上运行，把项目全部依赖下载到 deps/ 供真机离线安装
#
# 目标平台: Ubuntu 22.04 (jammy) + ROS 2 Humble + Python 3.10 + x86_64
# 产物:
#   deps/pip/  — requirements.txt 及其全部传递依赖的 wheel 包
#   deps/apt/  — ROS 2 Humble 相关 .deb 包(真机已装 ros-humble-desktop 时补缺/修复用)
#
# 用法: ./scripts/download_deps.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIP_DIR="$ROOT/deps/pip"
APT_DIR="$ROOT/deps/apt"
mkdir -p "$PIP_DIR" "$APT_DIR"

echo "==> [1/3] 下载 Python wheel 包(requirements.txt 及其传递依赖)..."
# --only-binary=:all: 只收 wheel、拒绝源码包，保证真机无需编译器即可安装。
# 本脚本必须在 Python 3.10 + Linux x86_64 环境下运行，wheel 才能与真机匹配。
# 额外约束 setuptools<80: osqp 无版本号地依赖 setuptools, 若放任 pip 取最新版(>=80)
# 会与 colcon-core 要求的 setuptools<80 冲突, 破坏真机上 ament_python 包的编译。
python3 -m pip download --only-binary=:all: -r "$ROOT/requirements.txt" "setuptools<80" -d "$PIP_DIR"

echo "==> [2/3] 下载 ROS 2 Humble 相关 .deb 包..."
# 与 src/*/package.xml 中 exec_depend/buildtool/test 对应的 apt 包名。
# 真机已有 ros-humble-desktop，这里下载的是"确保在"的清单，覆盖补装与离线修复。
APT_PKGS=(
    ros-humble-rclpy
    ros-humble-launch
    ros-humble-launch-ros
    ros-humble-robot-state-publisher
    ros-humble-joint-state-publisher
    ros-humble-rviz2
    ros-humble-tf2-ros
    ros-humble-geometry-msgs
    ros-humble-sensor-msgs
    ros-humble-std-msgs
    ros-humble-urdf
    ros-humble-ament-cmake
    python3-colcon-common-extensions
    python3-rosdep
    python3-setuptools
    python3-wheel
    python3-pytest
)
(cd "$APT_DIR" && apt-get download "${APT_PKGS[@]}")

echo "==> [3/3] 下载完成，清单如下:"
echo "--- deps/pip/ ---"
du -sh "$PIP_DIR"; ls -1 "$PIP_DIR" | sed 's/^/  /'
echo "--- deps/apt/ ---"
du -sh "$APT_DIR"; ls -1 "$APT_DIR" | sed 's/^/  /'
echo
echo "把整个项目目录(含 deps/)拷贝到真机后，运行: ./scripts/install_deps.sh"
