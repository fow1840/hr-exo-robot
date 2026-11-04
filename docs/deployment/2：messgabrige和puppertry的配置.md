# 2：MessageBridge 与 Puppetry 配置（HR-UP 双臂适配）

> **证据等级声明**：本文 = 厂商文档（证据等级 1）+ 仓库静态配置核对（等级 2）。
> 所有"启动成功日志"均为厂商示例输出，**尚未在 HR-UP 真机验证**。
> 真机操作必须遵循 `agent/deployment.md` 门禁：无运动检查 → 单节点 → 单臂低速 → 双臂。

## 0. 本文档覆盖的链路段与参数真相

外骨骼遥操作整体信号链（见 `agent/HANDOVER.md`）：

```text
外骨骼 ──→ MessageBridge ──→ /target_robot/{left,right}_ee/target ──→ Pink IK ──→ /target_robot/joint_commands
                                                                    │
机械臂 joint_states ──→ FK ──→ /target_robot/{left,right}_ee/state ─┘(回传给 MessageBridge → 外骨骼反馈)
```

本文负责链路的**第一段和最后一段**（MessageBridge + Puppetry）；中间的 FK/IK 见 `4：FK_和IK_的配置部署.md`。

**同一参数出现在多个文件时的唯一真相来源**（改任何一处前先对照此表）：

| 参数 | 唯一真相来源 | 本项目取值 |
|------|-------------|-----------|
| 臂链参考系（base frame） | `src/hr_up_7dof_fixed/urdf/HR-UP-7DOF-3KG-R-B01382-URDF-1029.urdf` | `base` |
| FK/IK 帧名与话题 | `src/hr_exo_teleop/config/hr_up.yaml` | `base` / `Link7` / `Link7L` |
| MessageBridge 网络/话题/帧 | `standalone/bin/ROS_2/config/MessageBridge.yaml` | 见 §3 |
| Puppetry 通信/IK/URDF | `standalone/bin/Puppetry/config/Puppetry.yaml` | 见 §4 |

---

## 1. 前置条件

### 1.1 按键的使用方法（厂商原文）

![](https://wdcdn.qpic.cn/MTY4ODg1NDkzNjg3MzY4Mw_793662_8VYmvE8NZ94Ycczn_1785206230?w=1558&h=1149)

### 1.2 IP 规划

| 设备 | IP | 说明 |
|------|-----|------|
| 遥操作数采设备（外骨骼） | `192.168.2.240` | 设备底部有线网口，**固定 IP 不可改** |
| 目标机（跑 MessageBridge/Puppetry/FK/IK） | `192.168.2.xxx`（如 `192.168.2.100`） | 需手动配置目标机网口 |

- 网段必须一致（`docs/deployment/5：部署注意事情.md` 第 1 条）。
- MessageBridge 和 Puppetry **必须放在同一环境（同一台机器）**（doc 5 第 3 条）；FK/IK 可以放别的机器，只要 ROS 2 域互通。

---

## 2. 网络配置与连通性验证（真机第一步，无风险）

### 步骤 2.1 配置目标机网口 IP

网线直连外骨骼设备与目标机，将目标机该网口设为 `192.168.2.xxx`（避开 `.240`）。

```bash
# 查看网卡名（假设为 enp3s0）
ip -br link

# 临时生效（重启丢失，适合先验证）
sudo ip addr add 192.168.2.100/24 dev enp3s0

# 永久生效（Netplan，Ubuntu 22.04 示例）
sudo nano /etc/netplan/01-exo.yaml
# network:
#   version: 2
#   ethernets:
#     enp3s0:
#       addresses: [192.168.2.100/24]
sudo netplan apply
```

**IP 修改原则（厂商原文）**：若机器人的 IP 固定就修改外骨骼的 IP；若机器人的 IP 可以修改就修改机器人的 IP。本项目中外骨骼数采设备固定为 `192.168.2.240`，所以改目标机侧。

### 步骤 2.2 验证连通

```bash
ping -c 4 192.168.2.240
```

预期：4 个 reply、0% packet loss。不通时依次检查：网线/网口指示灯 → 目标机 IP 是否 `192.168.2.x` 段 → 目标机防火墙。

> ⚠️ 此步骤必须在真机执行并留存输出（`agent/deployment.md` 门禁阶段 1 盘点项）。

---

## 3. MessageBridge 配置

### 3.1 文件位置

| 位置 | 路径 | 说明 |
|------|------|------|
| 本仓库镜像（已适配） | `standalone/bin/ROS_2/config/MessageBridge.yaml` | 与实机版本核对后修改 |
| 真机安装目录 | `Install/install_ros2/bin/ROS_2/config/MessageBridge.yaml` | 厂商部署包位置 |

配置优先级（厂商 `README_CONFIG.md`）：**命令行参数 > YAML 配置 > 代码默认值**。改完 YAML 需重启程序生效。

### 3.2 网络段（network）

```yaml
network:
  monitoring_ip: "192.168.2.240"    # 外骨骼数采设备固定 IP，不改
  advertise_ip: ""                  # 留空=自动检测本机 IP；Docker 无网络挂载时需手动填宿主机 IP
  bridge_pub_port: 9900             # ZMQ 发布服务端口，与 Puppetry 的 messagebridge_port 对应，不改
```

关键参数（厂商原文）：

- **monitoring_ip**：设置为遥操作数采设备（外骨骼）IP 地址 → 本项目固定 `192.168.2.240`。
- **advertise_ip**：程序自动检测，一般留空；仅在无网络的 Docker 环境手动传入。
- **bridge_pub_port**：默认 9900。

### 3.3 话题段（ros_topics）与本项目的话题契约

当前仓库版 `MessageBridge.yaml` 的话题名**已经与 `hr_up.yaml` 链路对齐，无需改动**。契约表如下（方向以 MessageBridge 视角）：

| 话题 | 方向 | 对接的本项目节点 |
|------|------|----------------|
| `/target_robot/left_ee/target` | **发布** → | `ik_retargeting` 订阅，作为左臂 IK 目标 |
| `/target_robot/right_ee/target` | **发布** → | `ik_retargeting` 订阅，作为右臂 IK 目标 |
| `/target_robot/left_ee/state` | ← **订阅** | `fk_adapter` 发布（左臂 FK 结果回传外骨骼） |
| `/target_robot/right_ee/state` | ← **订阅** | `fk_adapter` 发布（右臂 FK 结果回传外骨骼） |
| `/joints`、`/ee_poses`、`/exoskeleton/joint_states` | 发布 | 外骨骼原始数据（调试/记录用） |
| `/clutch/left`、`/clutch/right` | 发布 | 左右臂离合使能信号 |
| `/trigger_positions`、`/tact_force` | 发布 | 扳机（左手第 1 元素/右手第 2 元素，0-1）、双向触觉力 |
| `/custom/*`、`/statemachine/*`、`/*_glove_pos*` | 发布 | 自定义/状态机/数据手套话题 |

> 改话题名的唯一合法方式：同步改 `MessageBridge.yaml` + 对接节点参数，并更新上表。**不要单边改。**

### 3.4 帧段（frame_ids）—— 本项目唯一必改处 ✅

**2026-11-05 已修改**（原值为 `base_link`，与 URDF 不符）：

```yaml
frame_ids:
  base_frame: "base"              # ← 原 "base_link"，已改为 "base"
  left_ee_frame: "exo_left_ee_frame"    # 保持不变（外骨骼侧可视化帧）
  right_ee_frame: "exo_right_ee_frame"  # 保持不变（外骨骼侧可视化帧）
```

修改依据：

1. HR-UP URDF 中根连杆是 `base_mount`，经 fixed 关节 `base_mount_to_base` 连到 `base`；双臂 `Joint1`/`Joint1L` 直接挂在 **`base`** 上 → 臂链参考系是 `base`。
2. `hr_up.yaml` 中 `fk_adapter.base_frame: "base"`、`ik_retargeting.ref_link_name: "base"`；IK 节点会校验收到消息的 `header.frame_id`，不一致直接告警丢帧。
3. **三处必须严格一致**：`MessageBridge.yaml.base_frame` == `fk_adapter.base_frame` == `ik_retargeting.ref_link_name` == `"base"`。

参数含义（厂商原文）：

- **base_frame**：使用增量控制插件时，填写左右手正/逆运动学的参考坐标系（会写入增量话题与 `*_ee/target` 消息的 `header.frame_id`）。**必须与目标机器人 base frame 同名。**
- **left/right_ee_frame**：仅用于 TF 可视化广播（`base_frame → exo_*_ee_frame`），不影响控制流。**保持 `exo_` 前缀**，不要改成 `Link7`/`Link7L`（那是 HR-UP 机械臂自己的末端 link，会撞 TF 树）。

---

## 4. Puppetry 配置

### 4.1 文件位置

| 位置 | 路径 |
|------|------|
| 本仓库镜像 | `standalone/bin/Puppetry/config/Puppetry.yaml` |
| 真机安装目录 | `Install/install_ros2/bin/Puppetry/config/Puppetry.yaml` |

### 4.2 逐段参数说明

```yaml
Puppetry:
  communication:
    puppeteer_monitoring_ip: "192.168.2.240"   # ← 必须为外骨骼设备 IP，与 §3.2 monitoring_ip 相同
    puppeteer_port: 9899                       # 外骨骼侧端口，不改
    use_ipc: true                              # 本机进程间通信，MessageBridge 与 Puppetry 同机时保持 true
    messagebridge_ipc_path: "ipc:///tmp/messagebridge_pub.ipc"
    puppetry_ipc_path: "ipc:///tmp/puppetry_pub.ipc"
    messagebridge_tcp_ip: "127.0.0.1"          # 同机回环，不改
    messagebridge_port: 9900                   # == MessageBridge.yaml 的 bridge_pub_port
  urdf:
    directory: "./urdf_models"                 # URDF 搜索目录（相对 Puppetry 可执行文件所在目录）
    default_file: "robot.urdf"                 # ← 见 §4.3，必须换成 HR-UP 的 URDF
  kinematics:
    enable_ik_solver: true                     # Puppetry 内置 IK（增量控制用）
    solver_type: "pinocchio"
    max_iterations: 1000
    tolerance: 1.0e-6
    use_joint_limits: true
    collision_check: false                     # 关闭（URDF 无可直接加载的碰撞网格）
  logging:
    level: "info"                              # trace/debug/info/warn/error/critical
  mirroring:
    enable_mirroring: false                    # 镜像操控模式，默认关；需单臂带双臂时再开
  run:
    interval_ms: 2                             # 运行周期 1~1000ms（1kHz~1Hz）；外骨骼原始反馈约 1000Hz
```

需配置的关键参数（厂商原文）：`puppeteer_monitoring_ip`（遥操作数采设备 IP）、`enable_mirroring`（镜像模式）、`interval_ms`（控制频率，直接影响增量话题频率）。

### 4.3 Puppetry 的 URDF 替换（⚠️ 新发现的必做项，待真机验证）

**问题**：`standalone/bin/Puppetry/urdf_models/robot.urdf` 是厂商**占位示例**（`dual_arm_robot`，肩/肘/腕三关节圆柱假人），与 HR-UP 完全不符。Puppetry 内置 pinocchio IK 按这个假模型算关节角，直接上真机会得到错误解。

**替换步骤**（部署包制作阶段完成，属静态修改）：

```bash
cd /home/dm/下载/hr-exo-robot
cp src/hr_up_7dof_fixed/urdf/HR-UP-7DOF-3KG-R-B01382-URDF-1029.urdf \
   standalone/bin/Puppetry/urdf_models/robot.urdf
```

注意事项：

1. HR-UP URDF 的 mesh 用 `package://hr_up_7dof_fixed/meshes/*.STL` 引用，Puppetry 目录下没有 ament 环境可能解析失败。`collision_check: false` 时 pinocchio 通常只建运动学模型、不加载 mesh；**若启动报 mesh 加载错误**，去掉 URDF 中 `<visual>`/`<collision>` 段（pinocchio 只需 `<inertial>` 与关节链）再试。
2. HR-UP 是**双臂 14 关节**模型（右 `Joint1..7` → `Link7`，左 `Joint1L..7L` → `Link7L`），Puppetry 需能按左/右末端分别求解；**插件是否支持 14 关节双臂模型待真机验证**，若不支持需拆成单臂 URDF 分别配置。
3. 左臂关节定义在 `hr_up_7dof_fixed` 修复版中已按镜像重写（URDF 头部注释第 4、5 条），与厂商原始导出零位不同 —— **接真机前必须按实机重新核对左臂定义**（URDF 注释已声明）。

> 此项为本次梳理时新发现，建议单独建 Issue 跟踪真机验证结果。

---

## 5. 启动顺序与成功判据（真机门禁阶段 6：无运动启动）

**启动顺序**：先 MessageBridge，后 Puppetry（两者同机同环境，见 doc 5 第 3 条）。

### 5.1 启动消息桥接器（MessageBridge）

```bash
cd Install/install_ros2/bin/ROS_2    # 仓库镜像对应 standalone/bin/ROS_2
./MessageBridge                       # 或 ./Bridge.sh
```

厂商示例成功输出：

```text
./MessageBridge
[INFO] [1770704408.330312411] []: 命令行参数: monitoring_ip=127.0.0.1, advertise_ip=, bridge_port=9900, service_name=bridge_down_pub, wait_master_ms=0, show_raw=false
...
[INFO] [1770704408.753845198] []: ServiceRegistrar RegisterService: Service bridge_down_pub registered.
[INFO] [1770704408.753867633] []: Sent REGISTER request of service-bridge_down_pub done
[INFO] [1770704408.753910588] []: Service 'bridge_down_pub' registered to Hub at tcp://192.168.2.240:5555 (advertise_ip='192.168.2.100', port=9900)
[INFO] [1770704408.753916235] []: MessageBridge Node 'message_bridge' in namespace '/' started
```

**判据**：最后一行出现 `MessageBridge Node 'message_bridge' in namespace '/' started` 即成功。

> ⚠️ 厂商注：如在自检未完成时启动，会出现 `service registration fail` 等标记，此时**力反馈功能无法正常使用**，仅单向遥操作可用。遇到时：等外骨骼自检完成后重启 MessageBridge。

### 5.2 启动控制插件（Puppetry）

```bash
cd Install/install_ros2/bin/Puppetry/
./Puppetry
```

厂商示例成功输出：

```text
./Puppetry
=====================================================================================
Application information:
Name: Puppetry
Version: 0.0.1
...
[1770704441.135959][tid 3174399][I][Puppetry.Initialize 179] Puppetry initialized, task ID: 0, interval: 2ms
[1770704441.135960][tid 3174399][I][main 64] Puppetry initialized. Press Ctrl+C to stop.
```

**判据**：最后一行出现 `Puppetry initialized. Press Ctrl+C to stop.` 即成功。

### 5.3 无运动验证清单（启动后、接机械臂前）

```bash
# 1. 话题存在性
ros2 topic list | grep -E "target_robot|clutch|joints|ee_poses"

# 2. 频率（Puppetry interval_ms=2 → target 话题应约 500Hz）
ros2 topic hz /target_robot/left_ee/target
ros2 topic hz /target_robot/right_ee/target

# 3. 内容抽检：frame_id 必须是 "base"（§3.4 契约）
ros2 topic echo /target_robot/left_ee/target --once | grep frame_id

# 4. FK 回环（fk_adapter 启动后）
ros2 topic echo /target_robot/left_ee/state --once
```

全部通过且**机械臂无任何运动**，才允许进入 `4：FK_和IK_的配置部署.md` 的 IK/FK 联调与后续单臂低速验收。

---

## 6. 未验证项与风险（真机前必须逐条销号）

| # | 事项 | 类型 | 销号方式 |
|---|------|------|---------|
| 1 | `base_frame: "base"` 与实机 FK/IK 帧名一致 | 本文档推断（等级 2） | 真机 `ros2 topic echo` 抽检 §5.3-3 |
| 2 | Puppetry `robot.urdf` 占位模型 → 替换为 HR-UP URDF | 静态修改，未运行验证 | §4.3 替换后真机启动看日志 |
| 3 | Puppetry 内置 IK 对 14 关节双臂模型的支持 | 未知（闭源） | 真机启动 + 单臂低速验证 |
| 4 | HR-UP 左臂 URDF 镜像修正与实机零位/符号一致性 | URDF 注释已声明需核对 | 对照实机关节角（Issue #1 关节约定卡） |
| 5 | `advertise_ip` 留空时自动检测在目标机是否正确 | 厂商行为 | 看 MessageBridge 启动日志中的 advertise_ip 值 |
| 6 | 力反馈需外骨骼自检完成后启动 MessageBridge | 厂商文档 | 按厂商注操作 |

**回滚**：修改任何厂商配置前先备份（`cp MessageBridge.yaml MessageBridge.yaml.bak-$(date +%F)`），真机异常时恢复备份重启即可；仓库内改动用 git revert。
