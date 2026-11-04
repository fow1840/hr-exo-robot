# HR-EXO-robot 外骨骼遥操作框架

HR-UP 7-DOF 双臂 + DataMaster 外骨骼遥操作，colcon 工作区。
链路：外骨骼 → MessageBridge → `*_ee/target` → pink IK → `joint_commands` → 机械臂；
机械臂 `joint_states` → FK 正解 → `*_ee/state` → 反馈外骨骼。

## 结构

```
├── src/
│   ├── hr_up_7dof_fixed/      # HR-UP 双 7-DOF 臂 URDF 描述(meshes/rviz)
│   ├── robot_fk_adapter/      # FK 正解: joint_states → 末端位姿 state
│   ├── robot_ik_retargeting/  # pink IK 逆解: target 位姿 → joint_commands
│   └── hr_exo_teleop/         # 总控: launch + 参数(config/hr_up.yaml)
├── standalone/                # 厂商闭源程序(MessageBridge/Puppetry), 原样保留
└── requirements.txt           # Python 依赖(pinocchio/pink, 版本锁定)
```

## 机器人上编译

### 离线部署(推荐，无需真机联网)

依赖已提前下载在 `deps/`（wheel + deb，平台: x86_64 + Python 3.10 + Humble）：

```bash
./scripts/install_deps.sh           # 离线装依赖 + 导入自检
./scripts/install_deps.sh --build   # 或装完顺便编译
```

依赖变动后，在开发机上重跑 `./scripts/download_deps.sh` 刷新 `deps/`。详见 `deps/README.md`。

### 在线安装

```bash
pip3 install -r requirements.txt
cd HR-EXO-robot && colcon build --symlink-install
source install/setup.bash

# 仿真闭环(假体驱动, 无需硬件)
ros2 launch hr_exo_teleop teleop_sim.launch.py
# 真机(机械臂驱动 + MessageBridge 已运行)
ros2 launch hr_exo_teleop teleop_real.launch.py
```

## 参数

链路参数统一在 `src/hr_exo_teleop/config/hr_up.yaml`（基准系 `base`、
末端 `Link7`/`Link7L`、IK 拟人姿态等）。
厂商程序配置在 `standalone/bin/ROS_2/config/MessageBridge.yaml`
（外骨骼 IP；`frame_ids.base_frame` 需改为 `"base"` 与链路一致）。
