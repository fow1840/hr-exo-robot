#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import numpy as np
import pinocchio as pin
import pink
from pink import solve_ik
from pink.tasks import FrameTask, PostureTask, DampingTask
from pink.limits import VelocityLimit, ConfigurationLimit
import tf2_ros
from sensor_msgs.msg import JointState
from geometry_msgs.msg import PoseStamped, TransformStamped
from std_msgs.msg import Bool
import math
import time
from rcl_interfaces.msg import ParameterDescriptor, ParameterType

# ==================================================================================
#  One Euro Filter Implementation (1€ 滤波器)
# ==================================================================================
class LowPassFilter:
    def __init__(self, alpha):
        self.__setAlpha(alpha)
        self.y = None
        self.s = None

    def __setAlpha(self, alpha):
        alpha = float(alpha)
        if alpha <= 0 or alpha > 1.0:
            raise ValueError("alpha (%s) should be in (0.0, 1.0]" % alpha)
        self.alpha = alpha

    def filter(self, value, timestamp=None, alpha=None):
        if alpha is not None:
            self.__setAlpha(alpha)
        if self.y is None:
            s = value
        else:
            s = self.alpha * value + (1.0 - self.alpha) * self.s
        self.y = value
        self.s = s
        return s

    def lastValue(self):
        return self.y

class OneEuroFilter:
    def __init__(self, freq, mincutoff=1.0, beta=0.0, dcutoff=1.0):
        if freq <= 0:
            raise ValueError("freq should be >0")
        if mincutoff <= 0:
            raise ValueError("mincutoff should be >0")
        if dcutoff <= 0:
            raise ValueError("dcutoff should be >0")
        self.__freq = float(freq)
        self.__mincutoff = float(mincutoff)
        self.__beta = float(beta)
        self.__dcutoff = float(dcutoff)
        self.__x = LowPassFilter(self.__alpha(self.__mincutoff))
        self.__dx = LowPassFilter(self.__alpha(self.__dcutoff))
        self.__last_time = None

    def __alpha(self, cutoff):
        te = 1.0 / self.__freq
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / te)

    def filter(self, x, timestamp=None):
        if self.__last_time and timestamp:
            rate = 1.0 / (timestamp - self.__last_time)
        else:
            rate = self.__freq
        self.__last_time = timestamp

        if self.__x.lastValue() is None:
            dx = 0.0 * x 
        else:
            dx = (x - self.__x.lastValue()) * rate
            
        edx = self.__dx.filter(dx, timestamp, alpha=self.__alpha(self.__dcutoff))
        cutoff = self.__mincutoff + self.__beta * np.linalg.norm(edx)
        return self.__x.filter(x, timestamp, alpha=self.__alpha(cutoff))

class PoseFilter:
    def __init__(self, freq=500.0, mincutoff=1.0, beta=0.05, dcutoff=1.0):
        self.pos_filter = OneEuroFilter(freq, mincutoff, beta, dcutoff)
        self.quat_filter = OneEuroFilter(freq, mincutoff, beta, dcutoff)
        
    def process(self, pos, quat, timestamp=None):
        filtered_pos = self.pos_filter.filter(pos, timestamp)
        filtered_quat_raw = self.quat_filter.filter(quat, timestamp)
        norm = np.linalg.norm(filtered_quat_raw)
        if norm > 1e-6:
            filtered_quat = filtered_quat_raw / norm
        else:
            filtered_quat = quat 
        return filtered_pos, filtered_quat

# ==================================================================================

class UniversalHumanIK(Node):
    def __init__(self):
        super().__init__('ik_retargeting')

        self.declare_parameter('urdf_path', '')
        self.declare_parameter('root_link_name', 'base_link') 
        self.declare_parameter('ref_link_name', '') 
        self.declare_parameter('target_link_names', ['right_wrist_roll_link', 'left_wrist_roll_link'])
        self.declare_parameter('max_dof', 7)  # 最大追溯的自由度数，默认 7
        
        string_array_desc = ParameterDescriptor(type=ParameterType.PARAMETER_STRING_ARRAY)
        double_array_desc = ParameterDescriptor(type=ParameterType.PARAMETER_DOUBLE_ARRAY)
        self.declare_parameter('preferred_joints', value=None, descriptor=string_array_desc)
        self.declare_parameter('preferred_angles', value=None, descriptor=double_array_desc)

        # 2. 参数获取
        urdf_path = self.get_parameter('urdf_path').value
        self.root_link = self.get_parameter('root_link_name').value
        self.max_dof = self.get_parameter('max_dof').value  # 获取最大追溯自由度数
        
        # 智能参考系处理
        user_ref = self.get_parameter('ref_link_name').value
        if not user_ref:
            self.ref_link = self.root_link
        else:
            self.ref_link = user_ref

        target_links = self.get_parameter('target_link_names').value
        self.ee_frames = {'right': target_links[0], 'left': target_links[1]}
        
        try:
            pref_joints = self.get_parameter('preferred_joints').value
        except Exception:
            pref_joints = None
        try:
            pref_angles = self.get_parameter('preferred_angles').value
        except Exception:
            pref_angles = None
        if pref_joints is None: pref_joints = []
        if pref_angles is None: pref_angles = []

        self.ik_freq = 250.0
        self.dt = 1.0 / self.ik_freq  

        # 3. 初始化滤波器 (500Hz 输入)
        input_freq = 500.0
        self.filters = {
            'left': PoseFilter(freq=input_freq, mincutoff=2.5, beta=0.05),
            'right': PoseFilter(freq=input_freq, mincutoff=2.5, beta=0.05)
        }

        self.last_loop_time = None
        self.max_allowed_dt = 0.01 
        self.max_joint_velocity = 2.0  # rad/s，可根据实际机器人调整
        
        # 4. 模型初始化
        base_model = pin.buildModelFromUrdf(urdf_path)
        
        # 检查参考系
        if base_model.existFrame(self.ref_link):
            self.get_logger().info(f"Reference Frame '{self.ref_link}' active.")
        else:
            self.get_logger().warn(f"Reference Frame '{self.ref_link}' NOT FOUND! Fallback to '{self.root_link}'.")
            self.ref_link = self.root_link
        
        # 日志：输出坐标系配置，帮助调试
        self.get_logger().info(f"IK Node坐标系配置：root_link='{self.root_link}', ref_link='{self.ref_link}'")
        # 存储 ref_id 供 control_loop 使用
        self.ref_id_map = {'left': base_model.getFrameId(self.ref_link), 
                           'right': base_model.getFrameId(self.ref_link)}

        self.models = {'left': base_model.copy(), 'right': base_model.copy()}
        self.datas = {side: m.createData() for side, m in self.models.items()}
        # [保持通用性] 动态获取关节名称，不硬编码
        self.joint_names = [str(n) for n in base_model.names[1:]]

        self.configs = {
            side: pink.Configuration(self.models[side], self.datas[side], pin.neutral(self.models[side])) 
            for side in ['left', 'right']
        }

        # 5. 拟人姿态构建
        self.q_natural = {'left': pin.neutral(base_model), 'right': pin.neutral(base_model)}
        for side in ['left', 'right']:
            if len(pref_joints) > 0:
                for j_name, angle in zip(pref_joints, pref_angles):
                    if self.models[side].existJointName(j_name):
                        jid = self.models[side].getJointId(j_name)
                        idx_q = self.models[side].joints[jid].idx_q
                        self.q_natural[side][idx_q] = angle

        # 6. 任务栈
        self.tasks = {}
        for side in ['left', 'right']:
            self.tasks[side] = {
                "ee": FrameTask(self.ee_frames[side], position_cost=300.0, orientation_cost=30.0),
                "posture": PostureTask(cost=1.0),
                "damping": DampingTask(cost=20.0) 
            }
            self.tasks[side]["posture"].set_target(self.q_natural[side])

        self.limits = [ConfigurationLimit(base_model), VelocityLimit(base_model)]

        # 7. 状态变量
        self.q_measured = pin.neutral(base_model)

        self.q_commanded = None 
        
        self.is_initialized = False
        self.clutch = {'left': False, 'right': False}
        self.prev_clutch = {'left': False, 'right': False}
        self.last_velocity = np.zeros(base_model.nv)
        
        self.latest_target_in_ref = {'left': None, 'right': None}
        self.anchor_pose_in_ref = {'left': pin.SE3.Identity(), 'right': pin.SE3.Identity()}
        self.soft_start_timer = {'left': 0.0, 'right': 0.0}
        self.soft_start_duration = 0.5

        # 8. 通信
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)
        self.create_subscription(JointState, "/client_robot/joint_states", self.state_cb, 1)
        self.create_subscription(PoseStamped, "/target_robot/left_ee/target", lambda m: self.target_cb(m, 'left'), 1)
        self.create_subscription(PoseStamped, "/target_robot/right_ee/target", lambda m: self.target_cb(m, 'right'), 1)
        self.create_subscription(Bool, "/clutch/left", lambda m: self.clutch_cb(m, 'left'), 1)
        self.create_subscription(Bool, "/clutch/right", lambda m: self.clutch_cb(m, 'right'), 1)
        self.pub_cmd = self.create_publisher(JointState, "/target_robot/joint_commands", 1)
        
        self.timer = self.create_timer(self.dt, self.control_loop)

    def state_cb(self, msg):
        # [改进1: 严格的初始化检查]
        # 只有确实读到了模型内有效关节的数据，才允许初始化
        received_valid_joints = False
        
        for name, pos in zip(msg.name, msg.position):
            if self.models['right'].existJointName(name):
                idx = self.models['right'].joints[self.models['right'].getJointId(name)].idx_q
                self.q_measured[idx] = pos
                received_valid_joints = True
        
        # 严谨的初始化检查：只有确实读到了模型内有效关节的数据，才允许初始化
        if not self.is_initialized and received_valid_joints:
            self.q_commanded = self.q_measured.copy()
            self.get_logger().info("✅ IK Node 成功接入有效关节数据，q_commanded 已对齐到真机状态，准许输出控制指令！")
            self.is_initialized = True

    def clutch_cb(self, msg, side): self.clutch[side] = msg.data

    def target_cb(self, msg, side):
        """
        接收来自 FK adapter 的末端位姿。
        
        重要：FK adapter 发布的 PoseStamped 的 header.frame_id 应该是 ref_link
        位姿值是末端执行器相对于 ref_link 的。
        
        如果 header.frame_id 与 ref_link 不一致，需要发出警告。
        """
        raw_pos = np.array([msg.pose.position.x, msg.pose.position.y, msg.pose.position.z])
        raw_quat = np.array([msg.pose.orientation.x, msg.pose.orientation.y, msg.pose.orientation.z, msg.pose.orientation.w])
        
        # 检查坐标系是否一致
        expected_frame = self.ref_link
        actual_frame = msg.header.frame_id
        if actual_frame != expected_frame:
            # 只在第一次不一致时警告，避免刷屏
            if not hasattr(self, '_frame_warned'):
                self._frame_warned = set()
            if side not in self._frame_warned:
                self.get_logger().warn(
                    f"Frame mismatch for {side}: expected '{expected_frame}', got '{actual_frame}'.\n"
                    f"Make sure FK adapter's base_frame parameter matches IK node's ref_link_name."
                )
                self._frame_warned.add(side)
        
        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        filt_pos, filt_quat = self.filters[side].process(raw_pos, raw_quat, timestamp)
        
        q_obj = pin.Quaternion(filt_quat[3], filt_quat[0], filt_quat[1], filt_quat[2]) # w, x, y, z
        self.latest_target_in_ref[side] = pin.SE3(q_obj.toRotationMatrix(), filt_pos)

    def control_loop(self):
        # [改进1: 等待有效数据]
        # 如果还没成功接收到真实的关节角度，拒绝执行后续所有的 IK 计算和指令发布
        if not self.is_initialized: 
            if not hasattr(self, '_wait_log_cnt'):
                self._wait_log_cnt = 0
            if self._wait_log_cnt % 250 == 0:  # 每 1 秒打印一次等待提示 (频率 250Hz)
                self.get_logger().info("⏳ IK Node 正在等待有效且完整的 /client_robot/joint_states 数据...")
            self._wait_log_cnt += 1
            return
        
        current_time = self.get_clock().now().nanoseconds * 1e-9
        
        if self.last_loop_time is None:
            self.last_loop_time = current_time
            return
        
        actual_dt = current_time - self.last_loop_time
        self.last_loop_time = current_time
        
        if actual_dt > self.max_allowed_dt:
            self.get_logger().warn(f"Loop skipped, dt={actual_dt*1000:.1f}ms > {self.max_allowed_dt*1000:.1f}ms (system lag)")
            return
        
        # 初始化全零速度
        combined_velocity = np.zeros(self.models['right'].nv)

        # ==============================================================================
        # [改进2: Clutch 开启瞬间的状态同步]
        # 完全同步 q_commanded 到 q_measured，消除 FK 初始位置误差
        # 同时重置速度历史，防止微分项突变
        # ==============================================================================
        for side in ['left', 'right']:
            if self.clutch[side] and not self.prev_clutch[side]:
                # 1. 位置同步：完全同步到真实编码器位置
                sync_jump = 0.0
                # 找到该侧手臂对应的关节（通过运动学链）
                chain_indices = self.get_chain_velocity_indices(self.models[side], self.ee_frames[side], self.max_dof)
                # 从速度索引反推配置索引
                for idx_v in chain_indices:
                    # 获取该关节的配置索引范围
                    joint_id = self._find_joint_by_velocity_idx(self.models[side], idx_v)
                    if joint_id >= 0:
                        idx_q = self.models[side].joints[joint_id].idx_q
                        nq = self.models[side].joints[joint_id].nq
                        for i in range(nq):
                            jump = self.q_measured[idx_q + i] - self.q_commanded[idx_q + i]
                            sync_jump += abs(jump)
                            self.q_commanded[idx_q + i] = self.q_measured[idx_q + i]
                
                # 2. 速度重置：清除该侧的速度历史，防止微分项突变
                for idx_v in chain_indices:
                    self.last_velocity[idx_v] = 0.0
                
                if sync_jump > 0.001:  # 只在有明显跳变时打印
                    self.get_logger().info(f"[{side.upper()}] 使能接管，位置同步跳变 {sync_jump:.4f} rad，速度历史已重置")
                else:
                    self.get_logger().info(f"[{side.upper()}] 使能接管，位置无跳变，速度历史已重置")
        # ==============================================================================

        for side in ['left', 'right']:
            # ==============================================================================
            # [改进3: 纯指令流前向运动学计算]
            # 用 self.q_commanded 彻底代替 self.q_measured 进行 FK 计算，切断积分漂移反馈环
            # ==============================================================================
            self.configs[side].update(self.q_commanded)
            pin.forwardKinematics(self.models[side], self.datas[side], self.q_commanded)
            pin.updateFramePlacements(self.models[side], self.datas[side])
            
            # --- 坐标系准备 ---
            T_world_ee = self.configs[side].get_transform_frame_to_world(self.tasks[side]["ee"].frame)
            
            ref_id = self.models[side].getFrameId(self.ref_link)
            if ref_id >= len(self.datas[side].oMf): ref_id = 0 

            T_world_ref = self.datas[side].oMf[ref_id]
            
            # 计算末端相对于 ref_link 的位姿
            T_ref_ee = T_world_ref.inverse() * T_world_ee
            T_current_in_ref = T_ref_ee

            T_display_in_ref = None

            if self.clutch[side]:
                # ================= [ON: 计算 IK] =================
                if not self.prev_clutch[side]:
                    self.anchor_pose_in_ref[side] = T_current_in_ref
                    self.soft_start_timer[side] = 0.0
                    self.last_velocity.fill(0.0)
                
                T_target = self.latest_target_in_ref[side]
                if T_target is None: T_target = T_current_in_ref
                
                # ============ [改进4: 诊断日志] ============
                if not hasattr(self, '_log_cnt'):
                    self._log_cnt = 0
                
                if self._log_cnt % 100 == 0:
                    if T_target is not None:
                        pos_diff = np.linalg.norm(T_current_in_ref.translation - T_target.translation)
                        rot_diff_matrix = T_current_in_ref.rotation.T @ T_target.rotation
                        rot_diff_rad = np.arccos(np.clip((np.trace(rot_diff_matrix) - 1) / 2, -1, 1))
                        rot_diff_deg = np.degrees(rot_diff_rad)
                        
                        self.get_logger().info(
                            f"[{side.upper()}] 位姿对比 |\n"
                            f"位置差：{pos_diff*1000:.2f}mm |\n"
                            f"旋转差：{rot_diff_deg:.2f}° |\n"
                            f"T_current: [{T_current_in_ref.translation[0]:.3f}, {T_current_in_ref.translation[1]:.3f}, {T_current_in_ref.translation[2]:.3f}], "
                            f"T_target: [{T_target.translation[0]:.3f}, {T_target.translation[1]:.3f}, {T_target.translation[2]:.3f}]"
                        )
                    else:
                        self.get_logger().warn(f"[{side.upper()}] T_target 为 None，未收到目标位姿")
                    
                    if self._log_cnt % 500 == 0:
                        self.get_logger().info(f"q_measured[:7]: {np.round(self.q_measured[:7], 3)}")
                        self.get_logger().info(f"q_commanded[:7]: {np.round(self.q_commanded[:7], 3)}")
                        self.get_logger().info(f"clutch: {self.clutch}")
                    
                    self._log_cnt += 1
                # ============ 诊断日志结束 ============
                
                # [改进5: 软启动阻尼渐变策略]
                # 软启动期间使用渐变阻尼，从高到低平滑过渡
                if self.soft_start_timer[side] < self.soft_start_duration:
                    self.soft_start_timer[side] += self.dt
                    alpha = self.soft_start_timer[side] / self.soft_start_duration
                    T_display_in_ref = pin.SE3.Interpolate(self.anchor_pose_in_ref[side], T_target, alpha)
                    # 软启动期间使用高阻尼，抑制速度突变，渐变到正常值
                    self.tasks[side]["damping"].cost = 200.0 * (1.0 - alpha) + 20.0 * alpha
                else:
                    T_display_in_ref = T_target
                    self.tasks[side]["damping"].cost = 20.0

                T_ik_target_world = T_world_ref * T_display_in_ref
                self.tasks[side]["ee"].set_target(T_ik_target_world)
                
                # 只有在使能时，才运行 IK 并更新速度
                v_side = solve_ik(self.configs[side], self.tasks[side].values(), actual_dt, solver="osqp", safety_break=False)
                chain_indices = self.get_chain_velocity_indices(self.models[side], self.ee_frames[side], self.max_dof)
                for idx_v in chain_indices: combined_velocity[idx_v] = v_side[idx_v]

            else:
                # 目标显示为当前位置
                T_display_in_ref = T_current_in_ref
                self.soft_start_timer[side] = 0.0
                
            self.broadcast_tf(T_display_in_ref, f"ik_target_{side}", self.ref_link)
            self.prev_clutch[side] = self.clutch[side]

        # ==================== 速度滤波 ====================
        filter_alpha = 0.5 
        filtered_velocity = filter_alpha * combined_velocity + (1 - filter_alpha) * self.last_velocity
        self.last_velocity = filtered_velocity

        velocity_limited = np.clip(filtered_velocity, -self.max_joint_velocity, self.max_joint_velocity)
        
        # ==================== [改进5补充: 使能瞬间速度限制] ====================
        # 检测使能瞬间，进一步限制速度，防止突变
        for side in ['left', 'right']:
            if self.clutch[side] and not self.prev_clutch[side]:
                # 使能后的前 3 个周期，限制速度为正常值的 30%
                if self.soft_start_timer[side] < 3.0 * self.dt:
                    chain_indices = self.get_chain_velocity_indices(self.models[side], self.ee_frames[side], self.max_dof)
                    for idx_v in chain_indices:
                        velocity_limited[idx_v] *= 0.3
        
        if any(self.clutch.values()):
            self.q_commanded = pin.integrate(self.models['right'], self.q_commanded, velocity_limited * actual_dt)
            
            # [改进6: 关节限位保护]
            # 积分后检查并限制到关节限位内，防止累积误差导致越界
            for i in range(len(self.q_commanded)):
                q_min = self.models['right'].lowerPositionLimit[i]
                q_max = self.models['right'].upperPositionLimit[i]
                if self.q_commanded[i] < q_min:
                    self.q_commanded[i] = q_min
                elif self.q_commanded[i] > q_max:
                    self.q_commanded[i] = q_max
            
            q_next = self.q_commanded
        else:
            # 全关状态下，指令保持不变，绝对静止
            q_next = self.q_commanded 
        
        # ==================== [改进7: 发布关节指令（包含位置和速度）] ====================
        cmd = JointState()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.name = self.joint_names
        cmd.position = q_next.tolist()
        cmd.velocity = velocity_limited.tolist()  # 发布 IK 计算的速度（用于 MIT 模式前馈）
        self.pub_cmd.publish(cmd)

    def _find_joint_by_velocity_idx(self, model, idx_v):
        """
        根据速度索引找到对应的关节 ID。
        
        Args:
            model: Pinocchio 模型
            idx_v: 速度索引
        
        Returns:
            关节 ID，如果找不到返回 -1
        """
        for jid in range(1, len(model.joints)):  # 从 1 开始，跳过 universe joint
            joint = model.joints[jid]
            if joint.idx_v == idx_v:
                return jid
            # 处理多自由度关节（如 freeflyer）
            if joint.idx_v <= idx_v < joint.idx_v + joint.nv:
                return jid
        return -1

    def get_chain_velocity_indices(self, model, ee_frame_name, max_dof=4):
        """
        从末端执行器框架向上遍历运动学链，返回该链上所有关节的速度索引。
        通用方案：不依赖关节命名约定，通过运动学拓扑追溯指定数量的自由度。
        
        Args:
            model: Pinocchio 模型
            ee_frame_name: 末端执行器框架名称（由用户传入的 target_link_names 指定）
            max_dof: 最大追溯的自由度数（默认 7，适用于大多数人形机器人手臂）
        
        Returns:
            运动链上所有关节的速度索引列表
        """
        indices = []
        dof_count = 0
        frame_id = model.getFrameId(ee_frame_name)
        if frame_id >= len(model.frames):
            self.get_logger().warn(f"Frame '{ee_frame_name}' not found in model")
            return indices
        
        # 从末端框架的父关节开始，向上遍历到根关节 (joint 0)
        frame = model.frames[frame_id]
        joint_id = frame.parent
        
        while joint_id != 0 and dof_count < max_dof:  # 0 是宇宙关节，限制最大 DOF
            joint = model.joints[joint_id]
            if joint.idx_v >= 0:  # 有效的速度索引
                indices.append(joint.idx_v)
                dof_count += joint.nv  # 累加关节的自由度数（revolute=1, freeflyer=6, etc.）
            # 通过 Pinocchio 的 parents 数组找父关节
            joint_id = model.parents[joint_id]
        
        return indices

    def broadcast_tf(self, T, child_frame, parent_frame):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = parent_frame
        t.child_frame_id = child_frame
        t.transform.translation.x, t.transform.translation.y, t.transform.translation.z = T.translation
        q = pin.Quaternion(T.rotation)
        t.transform.rotation.x, t.transform.rotation.y, t.transform.rotation.z, t.transform.rotation.w = q.x, q.y, q.z, q.w
        self.tf_broadcaster.sendTransform(t)

def main():
    rclpy.init()
    rclpy.spin(UniversalHumanIK())
    rclpy.shutdown()

if __name__ == "__main__": main()