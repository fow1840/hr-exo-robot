# HR-EXO-robot 外骨骼遥操作框架搭建计划

## Context

`/home/dm/下载/HR-EXO-robot` 目前有两块资产，结构松散：
- `standalone/`：厂商闭源程序（`bin/ROS_2/MessageBridge` 外骨骼→ROS2 话题桥、`bin/Puppetry` 遥操作主程序）
- `dmdatamaster_retargeting_example-main/`：官方示例工程（zip 解压名），内含 3 个 ROS2 包

目标：重组为**单一标准 colcon 工作区**，新增自研总控包 `hr_exo_teleop`（集成 launch + 参数配置），配启动脚本和文档，形成清晰链路：

```
外骨骼(人) → MessageBridge → Puppetry → /target_robot/{L,R}_ee/target → pink IK → /joint_commands → 机械臂
机械臂 /client_robot/joint_states → FK 正解 → /target_robot/{L,R}_ee/state → 反馈给 Puppetry 闭环
```

环境：ROS2 Humble 已装；pinocchio/pink 未装（requirements.txt 已固定版本）。

## 最终目录结构

```
HR-EXO-robot/                       # colcon 工作区根
├── README.md                       # 新建：架构图 + 快速开始
├── requirements.txt                # 移自示例工程（pin-pink==3.5.0, pin==2.7.0 等）
├── .gitignore                      # 新建：build/ install/ log/ __pycache__/
├── src/
│   ├── hr_up_7dof_fixed/           # URDF 描述包（移入 + 由长目录名重命名，包名不变）
│   ├── robot_fk_adapter/           # 官方 FK 正解包（移入，清理 __pycache__）
│   ├── robot_ik_retargeting/       # 官方 pink IK 包（移入）
│   └── hr_exo_teleop/              # ★ 新建：遥操作总控包
│       ├── package.xml / setup.py / setup.cfg / resource/
│       ├── config/hr_up.yaml       # HR-UP 双臂参数（ee link=Link7/Link7L, base=base）
│       ├── launch/teleop_sim.launch.py    # 仿真闭环：FK+IK+dummy_driver+rviz
│       └── launch/teleop_real.launch.py   # 真机：FK+IK（驱动由外部提供）
├── standalone/                     # 厂商程序原样保留
├── scripts/                        # 编号启动脚本
│   ├── env.sh                      # source ROS Humble + 工作区
│   ├── 00_install_deps.sh          # pip 安装 requirements.txt
│   ├── 10_build.sh                 # colcon build
│   ├── 20_run_messagebridge.sh     # cd standalone/bin/ROS_2 && ./MessageBridge
│   ├── 21_run_puppetry.sh          # cd standalone/bin/Puppetry && ./Puppetry
│   └── 30_run_teleop.sh            # ros2 launch hr_exo_teleop (sim|real)
└── docs/
    ├── architecture.md             # 数据流图 + 组件职责
    └── topics.md                   # 全部话题协议表
```

## 实施步骤

1. **目录重组**：`dmdatamaster_retargeting_example-main/src/` 下 3 包移入顶层 `src/`；URDF 包目录重命名 `hr_up_7dof_fixed`；删除空壳目录和 `__pycache__`；`requirements.txt` 提升到顶层。检查 URDF 包的 CMakeLists/launch 是否引用旧目录名（按 package.xml 包名 `hr_up_7dof_fixed` 安装，重命名目录不影响安装路径）。
2. **修复官方包问题**：`robot_ik_retargeting/setup.py` 删除不存在的 `ik_node_tracik` entry point（setup.py 引用了但文件不存在）。
3. **新建 `hr_exo_teleop` 包**（ament_python）：
   - `teleop_sim.launch.py`：robot_state_publisher（HR-UP URDF，重映射 `/joint_states`→`/client_robot/joint_states`）+ `joint_to_pose_adapter`（base_frame=`base`，left/right_ee_frame=`Link7L`/`Link7`）+ `ik_node`（urdf 用 `FindPackageShare('hr_up_7dof_fixed')`，ref_link=`base`，target_link_names=`[Link7, Link7L]`）+ `dummy_robot_driver`（500Hz）+ rviz（复用 `hr_up_fixed.rviz`）
   - `teleop_real.launch.py`：同上去掉 dummy_driver 和 rviz 可选
4. **启动脚本**：厂商程序必须 `cd` 到各自 bin 目录再启动（它们依赖相对路径 `config/`、`./urdf_models`）；脚本加 `chmod +x`。
5. **文档**：README（架构 + 启动顺序：装依赖→build→MessageBridge→Puppetry→teleop）、docs/architecture.md、docs/topics.md（含 MessageBridge 的 `/joints` `/ee_poses` `/exoskeleton/joint_states` `/tact_force` 等 + 遥操作链路话题，标注消息类型；特别说明 IK 节点需 `/clutch/left|right` 置 true 才使能）。
6. **git init** + `.gitignore` + 首次提交（整洁结构作为首版）。

## 复用清单（不重写）

- FK 正解：`src/robot_fk_adapter/robot_fk_adapter/joint_to_pose_adapter.py`（TF 查询式 FK）
- pink IK：`src/robot_ik_retargeting/robot_ik_retargeting/ik_node.py`（含 One Euro 滤波、clutch、软启动、限速）
- 仿真驱动：`src/robot_fk_adapter/robot_fk_adapter/dummy_robot_driver.py`
- URDF 双臂模型：`src/hr_up_7dof_fixed/urdf/HR-UP-7DOF-3KG-R-B01382-URDF-1029.urdf`（Joint1-7 右臂→Link7，Joint1L-7L 左臂→Link7L）

## 验证

1. `bash scripts/00_install_deps.sh` → `python3 -c "import pinocchio, pink"` 成功
2. `bash scripts/10_build.sh` → 4 个包编译通过
3. `ros2 launch hr_exo_teleop teleop_sim.launch.py` 后另开终端：
   - `ros2 topic hz /target_robot/joint_states`（dummy 500Hz）
   - `ros2 topic echo /target_robot/left_ee/state`（FK 输出随动）
   - `ros2 topic pub /clutch/right std_msgs/msg/Bool '{data: true}' --once` + 手动 pub 一个 `/target_robot/right_ee/target` PoseStamped → `/target_robot/joint_commands` 出现非零速度，rviz 中右臂跟随 → 链路闭环验证