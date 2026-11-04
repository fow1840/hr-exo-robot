# 3：IK 的依赖配置（整理版 v2）

> 整理自厂商示例文档《3：IK的依赖得配置》与 Walker S2 真机实证流程
> （`/home/dm/文档/UBT-walker-s2`：外骨骼遥操作部署SOP.md §5、walker_s2_pink_teleop.sh、LEDGER P-016/P-047）。
> 证据等级：源码/静态 + 开发机构建验证 + Walker S2 真机实证；本仓库真机验收另按 `agent/deployment.md`。

## 1. 环境要求

- **操作系统**: Ubuntu 22.04
- **ROS 版本**: ROS 2 Humble
- **Python**: 3.10（wheel/deb 与其强绑定）
- **核心库**: `pinocchio`(ros-humble-pinocchio 4.0)、`pink`、`numpy<2`、`tf2_ros`

## 2. 两条已验证事实（决定安装方式）

### 2.1 launch 启动的节点固定用系统 Python（venv 激活无效）

实测（开发机）：

| 实验 | 结果 |
|------|------|
| `head -1 install/robot_ik_retargeting/lib/robot_ik_retargeting/ik_node` | `#!/usr/bin/python3`（绝对路径） |
| 激活 venv 后 `colcon build`（删除产物重建） | shebang 仍是 `#!/usr/bin/python3` |
| `head -1 /usr/bin/colcon` | `#!/usr/bin/python3`（colcon 自身固定系统 Python） |

结论：`ros2 launch`/`ros2 run` 的节点解释器是 `/usr/bin/python3`；
venv 里的包必须用 **`PYTHONPATH` 注入**才能被节点看到。
Walker S2 真机 launch 正是这么做的（实证佐证）：

```bash
source /opt/ros/humble/setup.bash && source pink_ws/install/setup.bash && \
export PYTHONPATH=/home/ubt/pink_venv/lib/python3.10/site-packages:${PYTHONPATH:-} && \
ros2 launch robot_ik_retargeting walker_s2_ik_per_arm.launch.py
```

### 2.2 pinocchio 由 apt 提供，pip 的 pin 会遮蔽它并导致 native 崩溃

- `ros-humble-pinocchio` 在 ROS 2 jammy 官方源中存在（本机实测已装 4.0.0-2jammy）。
- Walker S2 真机红线（P-016 M3 实证、LEDGER P-047）：**pip 的 `pin`(Pinocchio) 装进
  `--system-site-packages` venv 后会遮蔽 ROS 版，连续求解 native 崩溃**；
  `pin-pink` 必须用 `--no-deps` 安装，阻止 pip 自动拉入遮蔽版 pin。
- numpy 必须钉在 1.x（实证：本机 numpy 2.2.6 下 import apt pinocchio 直接段错误，
  NumPy 2.x ABI 不兼容）。

## 3. 安装流程（Walker S2 实证配方）

### 3.1 系统依赖（apt）

```bash
sudo apt-get update
sudo apt-get install -y python3.10-venv ros-humble-pinocchio
# rmw/消息类按需: ros-humble-rmw-cyclonedds-cpp
```

验证：

```bash
source /opt/ros/humble/setup.bash && python3 -c "import pinocchio; print(pinocchio.__version__)"
# 期望 4.0.0
```

### 3.2 Python 依赖（venv + PYTHONPATH 注入）

```bash
python3 -m venv --system-site-packages ~/pink_venv     # 已存在则核对 pyvenv.cfg
~/pink_venv/bin/pip install -i https://mirrors.aliyun.com/pypi/simple/ \
    numpy==1.26.4 scipy==1.15.3 qpsolvers==4.8.2 proxsuite==0.7.2 \
    osqp==1.0.5 loop-rate-limiters==1.2.0 jinja2==3.1.6
~/pink_venv/bin/pip install -i https://mirrors.aliyun.com/pypi/simple/ \
    pin-pink==3.5.0 --no-deps     # --no-deps 是命门
# 镜像失败可回退: -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3.3 编译

```bash
cd 项目根目录
colcon build --symlink-install
source install/setup.bash
```

## 4. 启动前自检（launch 同款环境）

```bash
bash -c 'source /opt/ros/humble/setup.bash && source install/setup.bash && \
 export PYTHONPATH=~/pink_venv/lib/python3.10/site-packages:${PYTHONPATH:-} && \
 python3 -c "import pinocchio, pink, numpy; print(pinocchio.__version__, pink.__version__, numpy.__version__)"'
# 期望: 4.0.0(ROS)  3.5.0  1.26.4(venv) —— 若 numpy 显示 2.x 说明遮蔽了,回 3.2 重装
```

QP 求解器自检（缺 jinja2 时节点在离合使能瞬间崩溃，Walker S2 事故）：

```bash
# 同上环境追加:
python3 -c "import numpy, qpsolvers; \
  assert 'osqp' in qpsolvers.available_solvers; \
  qpsolvers.solve_qp(numpy.eye(2), numpy.zeros(2), solver='osqp')"
```

## 5. venv 适用边界

| 场景 | venv 是否生效 | 做法 |
|------|--------------|------|
| `ros2 launch` / `ros2 run`（部署运行） | 仅当 `PYTHONPATH` 注入 | 见 2.1/4 |
| 手动 `python xxx.py` 调试 | 激活即可 | `source ~/pink_venv/bin/activate` |

`--system-site-packages` 是必需的（否则 venv 内看不到 rclpy/colcon）。
venv 目录名自定时，加入 `.gitignore`（`/pink/`、`.venv/` 已收录）。

## 6. requirements.txt 已切换到实证配方（2026-11-05 执行）

| 项 | 旧（pip 路线） | 现（实证配方） |
|----|---------------|---------------|
| pinocchio 来源 | pip `pin==2.7.0` | apt `ros-humble-pinocchio` 4.0.0（`deps/apt/` 已含，配套 `coal`/`eigenpy`） |
| pin-pink 安装 | 普通依赖（会拉 pin） | `install_deps.sh` 用 `--no-deps` 单独先装 |
| numpy | `>=1.26.4` | `==1.26.4`（自检断言 1.x） |
| eigenpy | pip 3.5.1 | 随 apt pinocchio 依赖（3.13） |
| jinja2 | 未显式 | `==3.1.6` 显式（osqp 运行依赖） |

`deps/` 已按新配方重新生成：`deps/pip` 118MB→58MB（pin/cmeel 系/eigenpy wheel 移除），
`deps/apt` 2.5MB→13MB（+pinocchio 组、python3-venv）。
