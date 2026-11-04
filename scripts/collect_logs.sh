#!/usr/bin/env bash
# ============================================================================
# 现场日志取证打包脚本（只读采集，不改系统任何状态）
#
# 用途：真机调试后，把当次(或最近几次) launch 运行日志 + 环境快照打包，
#       供离线分析/回传给开发侧定位问题。
# 用法：
#   bash scripts/collect_logs.sh                # 打包 ~/.ros/log 最新一次运行
#   bash scripts/collect_logs.sh 3              # 打包最近 3 次运行
#   bash scripts/collect_logs.sh 1 /tmp/out     # 指定输出目录(默认 /tmp)
# 产物：/tmp/hr-exo-logs-<时间戳>.tar.gz（内含 SHA256SUMS 清单）
# ============================================================================
set -euo pipefail

ROS_LOG_DIR="${HOME}/.ros/log"
KEEP_COUNT="${1:-1}"
OUT_DIR="${2:-/tmp}"

if [ ! -d "$ROS_LOG_DIR" ]; then
    echo "错误: 未找到 $ROS_LOG_DIR，本机可能没跑过 ros2 launch" >&2
    exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
SNAP="$WORK/snapshot"
mkdir -p "$SNAP/ros_log"

# 1. 取最近 N 次运行日志（按目录名时间戳排序，只读拷贝）
cd "$ROS_LOG_DIR"
LATEST=$(ls -1 | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}' | sort | tail -n "$KEEP_COUNT" || true)
if [ -z "$LATEST" ]; then
    echo "错误: $ROS_LOG_DIR 下没有运行日志目录" >&2
    exit 1
fi
for d in $LATEST; do
    cp -r "$d" "$SNAP/ros_log/"
done

# 2. 环境快照（只读命令）
{
    echo "=== 采集时间: $(date '+%F %T %Z') ==="
    echo "=== 主机/系统 ==="
    uname -a
    grep -E 'PRETTY_NAME|VERSION_ID' /etc/os-release || true
    echo "=== ROS/Python ==="
    echo "ROS_DISTRO=${ROS_DISTRO:-未source}"
    python3 --version 2>&1
    echo "=== 关键 Python 包(若已装) ==="
    python3 - <<'PYEOF' 2>&1 || true
try:
    import numpy; print('numpy', numpy.__version__)
except Exception as e: print('numpy 不可用:', e)
try:
    import pinocchio; print('pinocchio', pinocchio.__version__)
except Exception as e: print('pinocchio 不可用:', e)
try:
    import pink; print('pink', pink.__version__)
except Exception as e: print('pink 不可用:', e)
PYEOF
    echo "=== DDS/域 ==="
    echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-默认0}"
    echo "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-默认}"
    echo "=== 资源 ==="
    df -h ~ 2>/dev/null | tail -1
    free -h 2>/dev/null | head -2 || true
    echo "=== 采集时刻存活的 ROS 进程(可能已退出, 仅供参考) ==="
    ps aux | grep -E 'ros2|ik_node|joint_to_pose|robot_state_pub|dummy' | grep -v grep || echo "(无)"
} > "$SNAP/system_info.txt" 2>&1

# 3. 打包 + 清单
STAMP=$(date +%Y%m%d-%H%M%S)
OUT_TAR="${OUT_DIR%/}/hr-exo-logs-${STAMP}.tar.gz"
tar -czf "$OUT_TAR" -C "$WORK" snapshot
( cd "$OUT_DIR" && sha256sum "$(basename "$OUT_TAR")" > "${OUT_TAR}.sha256" )

echo "完成: $OUT_TAR"
echo "清单: ${OUT_TAR}.sha256"
echo "内容: ros_log/{${LATEST//$'\n'/,}} + system_info.txt"
echo "回传后校验方法: cd <产物所在目录> && sha256sum -c $(basename "${OUT_TAR}").sha256"
