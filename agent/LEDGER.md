# HR-EXO-robot 问题台账（唯一问题状态源）

> - 用途：记录部署/开发/调试过程中遇到的**问题、根因、处置与验证证据**，供跨会话追溯。
>   任务/工单的动态状态仍以 GitHub Issues 为准（`agent/issue-tracker.md`）；
>   本台账只回答"这个问题出现过没有、怎么解决、怎么证明"。
> - 状态分类：`活跃`（未闭环）/ `已闭环`（有处置+验证，验证等级标注）/ `挂起`（donghai 裁定暂缓）。
> - 证据等级沿用 `agent/HANDOVER.md`：1 文档声称 / 2 源码静态 / 3 离线测试 / 4 目标机运行 / 5 真机验收。上一级不能代替下一级。
> - 已闭环条目**只增不改**；条目多了以后拆分 `LEDGER-ARCHIVE.md`（沿 Walker S2 实证库惯例）。
> - 最后更新：2026-11-05（FK/IK 配置部署日，P-001~P-014 首次落账）

---

## 活跃问题

### P-010 Link7=右 / Link7L=左 的物理左右对应未经实机验证
- 状态： 活跃（等真机）
- 优先级： 高（左右颠倒会让双臂互相跟错指令，属真机验收前必查项）
- 现象/背景： 配置按 URDF 定为右臂=Link7（Joint1..7）、左臂=Link7L（Joint1L..7L）。
  依据仅是 SolidWorks 导出 CSV 的组件名 R1..R7 / L1..L7 约定（证据等级 1），
  无人知道"模型左臂"对应操作者的物理左手还是右手。
- 处置： 真机 TF 树核对（RViz 中手动小角度动单臂，看哪边模型在动）。
- 关联： `docs/deployment/4：FK_和IK_的配置部署.md` §1/§9；`agent/HANDOVER.md`
- 更新： 2026-11-05

### P-011 preferred_joints/preferred_angles 拟人化角度未实测
- 状态： 活跃（等真机）
- 优先级： 中（留空=全零中立位，链路可用但姿态分支未必自然）
- 现象/背景： HR-UP URDF 由 SolidWorks 导出，关节轴向/正方向工程定义未核对，
  瞎填符号会引导错误姿态分支，故 2026-11-05 起刻意留空。
- 处置： 真机实测轴向/符号后按 `docs/deployment/4：FK_和IK_的配置部署.md` §6 填写
  （hr_up.yaml 与 hr_up_ik_retargeting.launch.py 两处同步）。
- 关联： `docs/deployment/4：FK_和IK_的配置部署.md` §6/§9
- 更新： 2026-11-05

### P-012 Puppetry 侧两件遗留（外骨骼程序）
- 状态： 活跃（等 donghai 决定/等真机）
- 优先级： 中
- 现象/背景： ① `standalone/bin/Puppetry/urdf_models/robot.urdf` 是厂商占位假人，
  未替换为 HR-UP URDF（替换与否 donghai 未拍板）；② Puppetry 闭源插件对
  14 关节双臂 URDF 的支持未知。
- 处置： ①等 donghai 决定是否拷贝/建 Issue；②真机联调时验证。
- 关联： `docs/deployment/2：messgabrige和puppertry的配置.md` 销号表
- 更新： 2026-11-05

### P-013 左臂 URDF 镜像正确性与实机零位待核对
- 状态： 活跃（等真机）
- 优先级： 中
- 现象/背景： SolidWorks 镜像导出的左臂关节原点/轴向与实机装配是否一致未知；
  零位（全关节 0）是否等于机械零位未知。零位 FK 参考值已留档：
  左 (-0.6764, 0, +0.344)、右 (-0.6764, 0, -0.344)，四元数 (±0.5, ±0.5, 0.5, 0.5)。
- 处置： 真机零位姿与 RViz 模型比对。
- 关联： `docs/deployment/4：FK_和IK_的配置部署.md` §1
- 更新： 2026-11-05

### P-014 真机现场日志取证能力（2026-11-05 donghai 新增需求）
- 状态： 活跃（离线验证完成，待真机实战检验）
- 优先级： 高（donghai 直接下达）
- 需求： 真机调试过程中记录关键节点日志，方便事后定位问题。
- 处置（已完成部分，证据等级 3 离线仿真）：
  1. `joint_to_pose_adapter.py`：启动配置速查、TF 查询失败告警（原为静默吞掉，
     节流 5s，含 frame 对与排查提示）、5s 统计心跳（收帧频率/发布数/失败数）；
  2. `ik_node.py`：启动配置速查（urdf/关节数/帧/max_dof/preferred 数）、
     离合断开边沿日志（与使能配对）、单次求解超周期告警（节流 5s）、
     5s 统计心跳（指令频率/求解次数与均值最差耗时/循环超时计数）；
  3. 三个 launch 的 fk/ik 节点 `output='both'`：屏幕可见 + 自动写入
     `~/.ros/log/<当次运行>/launch.log`（实测 Humble 行为：screen 不落盘、both 落盘）；
  4. `scripts/collect_logs.sh`：只读打包最近 N 次运行日志 + 系统环境快照，
     产物带 SHA256 清单。
- 未验证： 真机上长时间运行的日志量与心跳可读性（预计每节点每 5s 一条，量可控）。
- 关联： `docs/deployment/4：FK_和IK_的配置部署.md` §9 日志速查表；`scripts/collect_logs.sh`
- 更新： 2026-11-05

---

## 已闭环（2026-11-05，FK/IK 配置部署日）

### P-001 FK launch 引用不存在的包 HU_D04_description
- 现象： `ros2 launch robot_fk_adapter robot_fk_adapter.launch.py` 首启即挂，
  找不到 `HU_D04_description` 包与其 `urdf/HU_D04_01.urdf`。
- 根因： 厂商 G1/HU_D04 样例 launch 未随 HR-UP 适配。
- 处置： 改用 `hr_up_7dof_fixed` 包 + `HR-UP-7DOF-3KG-R-B01382-URDF-1029.urdf`。
- 验证： colcon 4 包过 + use_sim 仿真启动，节点/话题齐全（等级 3）。
- 关联： `docs/deployment/4：FK_和IK_的配置部署.md` §4.1

### P-002 launch 帧名与 HR-UP URDF 不匹配（base_link / wrist_roll_link 不存在）
- 现象： 即使包路径修好，FK 的 TF 查询也会永远失败且（修复前）无任何报错。
- 根因： HR-UP URDF 里没有 `base_link`、没有 `left/right_wrist_roll_link`；
  双臂挂在 `base` 上，末端是 `Link7`/`Link7L`。
- 处置： 三处帧契约统一为 `base`（MessageBridge.yaml == fk_adapter.base_frame
  == ik_retargeting.ref_link_name）；末端 Link7L（左）/Link7（右）。
- 验证： `tf2_echo base Link7L` 与 FK 输出一致；闭环仿真 20mm 收敛（等级 3）。
- 关联： `docs/deployment/4：FK_和IK_的配置部署.md` §2；`agent/HANDOVER.md`

### P-003 robot_description 参数未包 ParameterValue，Humble 下任何 URDF 都起不来
- 现象： launch 报 `Unable to parse the value of parameter robot_description as yaml`。
- 根因： Humble 的 launch_ros 对参数值做 YAML 解析推断类型，URDF 是 XML 必炸；
  这是厂商原写法（`Command(['cat ', urdf])` 裸用）的通病，teleop 两个整链 launch 同样中招。
- 处置： 3 个 launch 统一改为 `ParameterValue(Command(['cat ', urdf]), value_type=str)`。
- 验证： 修复后 FK/IK/teleop 全部能启动（等级 3）。
- 关联： `docs/deployment/4：FK_和IK_的配置部署.md` §7.1

### P-004 空 Python 列表参数在 Humble launch 无法定型 + declare(None) 缺省即抛
- 现象： ① launch 报 `Expected 'value' to be one of [...], but got '()'`；
  ② 改用 `ParameterValue(..., value_type=List[float])` 包空列表仍报
  `Got a list of '<class 'str''>, expected a list of '<class 'float'>'`；
  ③ `ParameterValue` 的 `value_type` 传 `rcl_interfaces` 枚举报
  `Unrecognized data type: 9`（只认 Python 类型）；
  ④ 参数完全不给时节点抛 `ParameterUninitializedException` 起不来。
- 根因： Humble launch 靠元素类型推断数组参数，空列表推不出来；
  `ik_node.py` 的 `declare_parameter(value=None, 描述符带类型)` 不允许"未提供"。
- 处置： launch 侧空列表不传参（填了才传）；`ik_node.py` 两个 preferred 参数
  声明加 `dynamic_typing=True`。yaml 参数文件里的空列表 `[]` 不受影响（实测可用）。
- 验证： 独立 IK launch 留空启动成功；yaml 路径（teleop_sim）留空启动成功（等级 3）。
- 关联： `docs/deployment/4：FK_和IK_的配置部署.md` §7.2

### P-005 numpy 2.x 与 apt pinocchio ABI 不兼容（再证）
- 现象： 开发机 numpy 2.2.6 下 `import pinocchio` 报 `_ARRAY_API not found`（段错误前兆）。
- 根因： NumPy 2.x ABI 不兼容，Walker S2 真机已实证的红线（P-016 M3 同款）。
- 处置： venv 钉 numpy==1.26.4（离线 wheel 来自 `deps/pip/`），PYTHONPATH 注入。
- 验证： 自检输出 pin 4.0.0 / pink 3.5.0 / numpy 1.26.4，osqp 求解 OK（等级 3）。
- 关联： `docs/deployment/3：IK的依赖得配置.md` §2.2

### P-006 ~/pink venv 为空壳，IK 无法本机验证
- 现象： venv 只有 pip/setuptools，import pink 失败。
- 处置： `python3 -m venv --system-site-packages ~/pink` 补标志位，
  用仓库 `deps/pip/` 14 个 wheel `--no-index` 离线装齐（pin-pink 单独 --no-deps）。
- 验证： 离线自检通过 + IK 闭环仿真（等级 3）。
- 关联： `docs/deployment/3：IK的依赖得配置.md` §3

### P-007 三类诊断噪音/假象（判断标准）
- ① scipy UserWarning（`A NumPy version >=1.17.3 and <1.25.0 is required`）：
  apt scipy 对 numpy 1.26.4 的区间提示，**良性忽略**；
- ② Ctrl-C 停 launch 时 `process has died ... exit code -2` + KeyboardInterrupt 回溯：
  SIGINT 正常关停噪音，**不是故障**；
- ③ `ros2 topic hz` / `tf2_echo` 接管道/重定向时输出被缓冲，被 timeout 杀掉前
  看似无输出（"已终止"假象）：用 `stdbuf -oL` 或结束后看重定向文件。
- 关联： `docs/deployment/4：FK_和IK_的配置部署.md` §7.3

### P-008 check_urdf（liburdfdom-tools）不在离线依赖
- 处置： 流程规避——URDF 语法检查在开发机打包前完成（实测本机
  `/opt/ros/humble/bin/check_urdf` 解析 HR-UP URDF 成功），离线真机跳过。
- 关联： `docs/deployment/4：FK依赖配置 (1).md` §7

### P-009 base 系几何认知陷阱（防误判左右）
- 现象： 直觉认为双臂挂载点在 base 系沿 y 轴左右分开，实测沿 **z** 轴分开（±0.194）。
- 根因： `base_mount → base` 有固定旋转（rpy = -90°,-90°,0），把挂载偏移转到了 z 轴。
- 处置： 已在文档 §1 记录零位参考值与该陷阱；物理左右判断不依赖几何符号，
  走 P-010 真机核对。
- 验证： FK 零位实测 z=±0.344 对称（等级 3）。
- 关联： `docs/deployment/4：FK_和IK_的配置部署.md` §1

---

## 交付留痕

- 2026-11-05（会话 1，FK/IK 配置部署）：修 `robot_fk_adapter.launch.py`、新增
  `hr_up_ik_retargeting.launch.py`、`ik_node.py` 参数声明修复与调试日志、
  teleop 两 launch ParameterValue 修复；重写 `docs/deployment/4：FK_和IK_的配置部署.md`、
  同步《4：FK依赖配置 (1)》与 `agent/HANDOVER.md`。验证等级 3（开发机离线仿真）。
  Commit：`4b9ccf5`（代码）。
- 2026-11-05（会话 2，本台账 + 日志取证）：FK/IK 节点调试日志（P-014）、
  launch `output='both'` 落盘、`scripts/collect_logs.sh`、`agent/LEDGER.md` 建账。
  验证等级 3。Commit：并入 `4b9ccf5` 与本笔（文档/台账/脚本）。
- 2026-11-05（上批会话遗留）：MessageBridge base_frame=base + 部署文档 2，
  Commit：`e5c27f1`。
