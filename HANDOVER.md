# HR-EXO-robot 技术交接

> 本文档保存稳定的架构与接手信息。动态任务、负责人、进度和验收结论以 GitHub Issues 为准。

## 项目目标

HR-UP 7-DOF 双臂与 DataMaster 外骨骼的 ROS 2 遥操框架，最终需要形成可校验的离线部署包，迁移到真机后分阶段验收。

## 已知信号链

```text
外骨骼 → MessageBridge → *_ee/target → Pink IK
       → joint_commands → 机械臂控制接口

机械臂 joint_states → FK → *_ee/state → 外骨骼反馈
```

这只是当前仓库的设计意图，不是真机已验证事实。

## 代码导航

- `src/hr_up_7dof_fixed/`：HR-UP 双 7-DOF 手臂描述。
- `src/robot_fk_adapter/`：关节状态到末端位姿。
- `src/robot_ik_retargeting/`：目标位姿到关节命令。
- `src/hr_exo_teleop/`：总控 launch 与参数。
- `standalone/`：厂商闭源程序和配置，修改前必须与实机版本核对。
- `deps/`：x86_64、Python 3.10、ROS 2 Humble 的离线依赖候选集。

## 真机前待确认

- 目标机 CPU 架构、Ubuntu/ROS/Python 版本及安装方式。
- 左右臂关节名称、顺序、单位、符号、零位、软/硬限位。
- 真实状态和命令接口、控制模式、心跳、超时及会话门控。
- `base`、`Link7`、`Link7L` 的真实坐标系契约。
- 急停、使能、离合和唯一命令发布者的责任归属。
- 无运动、仿真、单臂低速、双臂及中断/恢复验收数据。

## 证据等级

1. 文档或配置声称。
2. 源码和静态检查。
3. 离线测试/仿真。
4. 目标机编译和无运动运行。
5. donghai 确认的真机验收。

上一级不能代替下一级。
