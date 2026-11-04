# 编写 HR-UP 外骨骼遥操作部署 SOP

## Context

项目框架已搭好（4 个 ROS2 包 + standalone 厂商程序）。用户给出部署流程口述（上机→MessageBridge/Puppetry→venv 装 IK→对齐→离合遥操作），要求结合 Walker S2 pink 部署经验整理成 SOP 文档。Walker S2 参考文档已找到并研读：`/home/dm/文档/walker-s2-teleoperation-delivery/docs/DEPLOY.md`（含预检 4a-4d、jinja2/osqp 坑、末端帧 90° 坑、首动验收顺序）。

已确认：机器人主机 ROS2 Humble；关节映射未知→SOP 留检查模板；暂不写手套控制流程。

## 交付物

1. **新建 `docs/deployment_sop.md`**（唯一新文件），结构如下：

   - **开头**：一图流拓扑（外骨骼背包 ↔ 机器人主机[部署目标] ↔ 运控板[不部署]）+ URDF 作用 3 句话速览（用户问过，写进文档方便团队）
   - **阶段一：项目上机 + MessageBridge/Puppetry**
     - 打包上传（tar 排除 build/install/log → scp → 解压）
     - 同网段检查（已知默认 IP `192.168.2.240` 来自 Puppetry.yaml/MessageBridge.yaml）
     - MessageBridge.yaml 必改 2 处：`network.monitoring_ip`=背包实际 IP、`frame_ids.base_frame`→`"base"`（默认 base_link 与 HR-UP 不符）
     - **Puppetry 必换 URDF**：`urdf_models/robot.urdf` 当前是通用 `dual_arm_robot` 模型，需替换为 HR-UP URDF（复制自 `src/hr_up_7dof_fixed/urdf/`），注意 Puppetry 关节名（left_shoulder_joint 等）与 HR-UP（Joint1~7L）命名完全不同，需验证 Puppetry 对 URDF 关节名的兼容性——此处留现场验证点
     - 启动验证：cd 到 bin 目录启动（相对路径依赖）+ `ros2 topic` 检查表
   - **阶段二：IK 部署（venv 隔离，不污染本体环境）**
     - `python3 -m venv ~/pink_venv` + `pip install -r requirements.txt`
     - **jinja2 显式安装**（Walker S2 血泪：osqp 硬依赖，缺则离合瞬间崩 `found solvers: []`）
     - source 顺序：ros humble → venv → workspace；colcon build
     - 预检四件套（借鉴 Walker S2 4a-4d 改写）：pinocchio/pink import、`qpsolvers.available_solvers==['osqp']`、URDF 可加载且末端 frame 名（Link7/Link7L）正确、sim 闭环验证（teleop_sim 不接真机先跑通）
   - **阶段三：状态对齐（URDF ↔ 实机，核心）**
     - 关节映射检查表模板：URDF 关节名 | 驱动实际名 | 单位 | 方向符号 | 零位偏移（现场填写）
     - 映射不一致时的 3 种处理选项（驱动侧重映射 / 独立 bridge 节点 / 改 URDF）
     - 姿态对齐：摆 2~3 个已知姿态对比 RViz
     - 末端位姿对齐：FK 输出 `/target_robot/*_ee/state` 与实机实测对比，**重点防末端帧旋转差**（Walker S2 4b 教训：90° rpy 差）
     - ik_node 对齐机制说明（`q_commanded←q_measured` 初始化 + clutch 接管瞬间同步，防猛动）
   - **阶段四：离合遥操作闭环与验收**
     - 启动前安全确认 4 条（clutch=false、急停、无人、唯一命令源）
     - 启动顺序 + 离合流程（踏板→`/clutch/*`→ik_node 使能）
     - 首动验收（照搬 Walker S2 顺序）：单臂低速→啮合瞬间保持不动→平滑跟随→另一臂→双臂
     - 话题自检表（话题/频率/预期值）
     - 停止顺序
   - **附录**：故障排查表（jinja2、TF 时间戳、关节名不匹配、网段不通、base_frame 不一致、命令源冲突）

2. **修改 `README.md`**：加一行指向 `docs/deployment_sop.md` 的链接

3. **git 提交**（复用已批准的 git 授权）

## 内容来源（全部已核实，不臆造）

- 话题名/IP/配置项：`standalone/bin/ROS_2/config/MessageBridge.yaml`、`README_CONFIG.md`、`Puppetry/config/Puppetry.yaml`
- URDF 关节/末端：`src/hr_up_7dof_fixed/urdf/`（已解析）
- Walker S2 经验：`docs/DEPLOY.md` 第 53 行 jinja2 坑、169-172 行首动验收、53 行外预检、219-223 行换机注意事项
- 本项目 launch/参数：`src/hr_exo_teleop/`（我编写，内容已核）

## 验证

- 文档中所有命令在本机可干跑核对（路径、话题名与实际文件一致）
- 对照 MessageBridge.yaml/Puppetry.yaml 逐项确认"必改项"清单无遗漏
- git commit 完成