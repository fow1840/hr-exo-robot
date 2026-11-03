#!/usr/bin/env python3
import math

import numpy as np
import pinocchio as pin
import pink
import rclpy
import tf2_ros
from geometry_msgs.msg import PoseStamped, TransformStamped
from pink import solve_ik
from pink.limits import ConfigurationLimit, VelocityLimit
from pink.tasks import DampingTask, FrameTask, PostureTask
from rcl_interfaces.msg import ParameterDescriptor, ParameterType
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool

from robot_ik_retargeting.ik_node import PoseFilter


class SingleArmIKRetargeting(Node):
    def __init__(self):
        super().__init__('ik_retargeting_single_arm')

        self.declare_parameter('urdf_path', '')
        self.declare_parameter('root_link_name', 'link0')
        self.declare_parameter('ref_link_name', '')
        self.declare_parameter('side', 'right')
        self.declare_parameter('target_link_name', 'Link7')
        self.declare_parameter('max_dof', 7)

        string_array_desc = ParameterDescriptor(type=ParameterType.PARAMETER_STRING_ARRAY)
        double_array_desc = ParameterDescriptor(type=ParameterType.PARAMETER_DOUBLE_ARRAY)
        self.declare_parameter('preferred_joints', value=None, descriptor=string_array_desc)
        self.declare_parameter('preferred_angles', value=None, descriptor=double_array_desc)

        urdf_path = self.get_parameter('urdf_path').value
        self.root_link = self.get_parameter('root_link_name').value
        self.max_dof = self.get_parameter('max_dof').value

        self.side = self.get_parameter('side').value
        if self.side not in ('left', 'right'):
            self.get_logger().warn("Invalid side parameter, fallback to 'right'")
            self.side = 'right'

        self.ee_frame = self.get_parameter('target_link_name').value

        user_ref = self.get_parameter('ref_link_name').value
        self.ref_link = user_ref if user_ref else self.root_link

        pref_joints = self.get_parameter('preferred_joints').value or []
        pref_angles = self.get_parameter('preferred_angles').value or []

        self.ik_freq = 250.0
        self.dt = 1.0 / self.ik_freq

        input_freq = 500.0
        self.filter = PoseFilter(freq=input_freq, mincutoff=2.5, beta=0.05)

        self.last_loop_time = None
        self.max_allowed_dt = 0.01
        self.max_joint_velocity = 2.0

        self.model = pin.buildModelFromUrdf(urdf_path)
        self.data = self.model.createData()

        if self.model.existFrame(self.ref_link):
            self.get_logger().info(f"Reference Frame '{self.ref_link}' active.")
        else:
            self.get_logger().warn(
                f"Reference Frame '{self.ref_link}' NOT FOUND! Fallback to '{self.root_link}'."
            )
            self.ref_link = self.root_link

        self.get_logger().info(
            f"Single-arm IK config: side='{self.side}', root_link='{self.root_link}', ref_link='{self.ref_link}', ee='{self.ee_frame}'"
        )

        self.joint_names = [str(n) for n in self.model.names[1:]]
        self.config = pink.Configuration(self.model, self.data, pin.neutral(self.model))

        self.q_natural = pin.neutral(self.model)
        for j_name, angle in zip(pref_joints, pref_angles):
            if self.model.existJointName(j_name):
                jid = self.model.getJointId(j_name)
                idx_q = self.model.joints[jid].idx_q
                self.q_natural[idx_q] = angle

        self.tasks = {
            'ee': FrameTask(self.ee_frame, position_cost=300.0, orientation_cost=30.0),
            'posture': PostureTask(cost=1.0),
            'damping': DampingTask(cost=20.0),
        }
        self.tasks['posture'].set_target(self.q_natural)
        self.limits = [ConfigurationLimit(self.model), VelocityLimit(self.model)]

        self.q_measured = pin.neutral(self.model)
        self.q_commanded = None

        self.is_initialized = False
        self.clutch = False
        self.prev_clutch = False
        self.last_velocity = np.zeros(self.model.nv)

        self.latest_target_in_ref = None
        self.anchor_pose_in_ref = pin.SE3.Identity()
        self.soft_start_timer = 0.0
        self.soft_start_duration = 0.5

        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)
        self.create_subscription(JointState, '/client_robot/joint_states', self.state_cb, 1)
        self.create_subscription(
            PoseStamped,
            f'/target_robot/{self.side}_ee/target',
            self.target_cb,
            1,
        )
        self.create_subscription(Bool, f'/clutch/{self.side}', self.clutch_cb, 1)
        self.pub_cmd = self.create_publisher(JointState, '/target_robot/joint_commands', 1)

        self.timer = self.create_timer(self.dt, self.control_loop)

    def state_cb(self, msg):
        received_valid_joints = False

        for name, pos in zip(msg.name, msg.position):
            if self.model.existJointName(name):
                idx = self.model.joints[self.model.getJointId(name)].idx_q
                self.q_measured[idx] = pos
                received_valid_joints = True

        if not self.is_initialized and received_valid_joints:
            self.q_commanded = self.q_measured.copy()
            self.get_logger().info('IK single-arm node initialized from live joint states.')
            self.is_initialized = True

    def clutch_cb(self, msg):
        self.clutch = msg.data

    def target_cb(self, msg):
        raw_pos = np.array([msg.pose.position.x, msg.pose.position.y, msg.pose.position.z])
        raw_quat = np.array([
            msg.pose.orientation.x,
            msg.pose.orientation.y,
            msg.pose.orientation.z,
            msg.pose.orientation.w,
        ])

        if msg.header.frame_id != self.ref_link and not hasattr(self, '_frame_warned'):
            self.get_logger().warn(
                f"Frame mismatch: expected '{self.ref_link}', got '{msg.header.frame_id}'."
            )
            self._frame_warned = True

        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        filt_pos, filt_quat = self.filter.process(raw_pos, raw_quat, timestamp)

        q_obj = pin.Quaternion(filt_quat[3], filt_quat[0], filt_quat[1], filt_quat[2])
        self.latest_target_in_ref = pin.SE3(q_obj.toRotationMatrix(), filt_pos)

    def control_loop(self):
        if not self.is_initialized:
            return

        current_time = self.get_clock().now().nanoseconds * 1e-9

        if self.last_loop_time is None:
            self.last_loop_time = current_time
            return

        actual_dt = current_time - self.last_loop_time
        self.last_loop_time = current_time

        if actual_dt > self.max_allowed_dt:
            return

        combined_velocity = np.zeros(self.model.nv)

        if self.clutch and not self.prev_clutch:
            sync_jump = 0.0
            chain_indices = self.get_chain_velocity_indices(self.model, self.ee_frame, self.max_dof)
            for idx_v in chain_indices:
                joint_id = self._find_joint_by_velocity_idx(self.model, idx_v)
                if joint_id >= 0:
                    idx_q = self.model.joints[joint_id].idx_q
                    nq = self.model.joints[joint_id].nq
                    for i in range(nq):
                        jump = self.q_measured[idx_q + i] - self.q_commanded[idx_q + i]
                        sync_jump += abs(jump)
                        self.q_commanded[idx_q + i] = self.q_measured[idx_q + i]
            for idx_v in chain_indices:
                self.last_velocity[idx_v] = 0.0
            if sync_jump > 0.001:
                self.get_logger().info(f'Sync jump {sync_jump:.4f} rad on clutch enable')

        self.config.update(self.q_commanded)
        pin.forwardKinematics(self.model, self.data, self.q_commanded)
        pin.updateFramePlacements(self.model, self.data)

        T_world_ee = self.config.get_transform_frame_to_world(self.tasks['ee'].frame)

        ref_id = self.model.getFrameId(self.ref_link)
        if ref_id >= len(self.data.oMf):
            ref_id = 0
        T_world_ref = self.data.oMf[ref_id]

        T_current_in_ref = T_world_ref.inverse() * T_world_ee
        T_display_in_ref = T_current_in_ref

        if self.clutch:
            if not self.prev_clutch:
                self.anchor_pose_in_ref = T_current_in_ref
                self.soft_start_timer = 0.0
                self.last_velocity.fill(0.0)

            T_target = self.latest_target_in_ref or T_current_in_ref

            if self.soft_start_timer < self.soft_start_duration:
                self.soft_start_timer += self.dt
                alpha = self.soft_start_timer / self.soft_start_duration
                T_display_in_ref = pin.SE3.Interpolate(self.anchor_pose_in_ref, T_target, alpha)
                self.tasks['damping'].cost = 200.0 * (1.0 - alpha) + 20.0 * alpha
            else:
                T_display_in_ref = T_target
                self.tasks['damping'].cost = 20.0

            T_ik_target_world = T_world_ref * T_display_in_ref
            self.tasks['ee'].set_target(T_ik_target_world)

            v = solve_ik(
                self.config,
                self.tasks.values(),
                actual_dt,
                solver='osqp',
                safety_break=False,
            )
            chain_indices = self.get_chain_velocity_indices(self.model, self.ee_frame, self.max_dof)
            for idx_v in chain_indices:
                combined_velocity[idx_v] = v[idx_v]
        else:
            self.soft_start_timer = 0.0

        self.broadcast_tf(T_display_in_ref, f'ik_target_{self.side}', self.ref_link)

        filter_alpha = 0.5
        filtered_velocity = filter_alpha * combined_velocity + (1 - filter_alpha) * self.last_velocity
        self.last_velocity = filtered_velocity
        velocity_limited = np.clip(filtered_velocity, -self.max_joint_velocity, self.max_joint_velocity)

        if self.clutch:
            self.q_commanded = pin.integrate(self.model, self.q_commanded, velocity_limited * actual_dt)
            for i in range(len(self.q_commanded)):
                q_min = self.model.lowerPositionLimit[i]
                q_max = self.model.upperPositionLimit[i]
                if self.q_commanded[i] < q_min:
                    self.q_commanded[i] = q_min
                elif self.q_commanded[i] > q_max:
                    self.q_commanded[i] = q_max
            q_next = self.q_commanded
        else:
            q_next = self.q_commanded

        cmd = JointState()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.name = self.joint_names
        cmd.position = q_next.tolist()
        cmd.velocity = velocity_limited.tolist()
        self.pub_cmd.publish(cmd)

        self.prev_clutch = self.clutch

    def _find_joint_by_velocity_idx(self, model, idx_v):
        for jid in range(1, len(model.joints)):
            joint = model.joints[jid]
            if joint.idx_v == idx_v:
                return jid
            if joint.idx_v <= idx_v < joint.idx_v + joint.nv:
                return jid
        return -1

    def get_chain_velocity_indices(self, model, ee_frame_name, max_dof=4):
        indices = []
        dof_count = 0
        frame_id = model.getFrameId(ee_frame_name)
        if frame_id >= len(model.frames):
            self.get_logger().warn(f"Frame '{ee_frame_name}' not found in model")
            return indices

        frame = model.frames[frame_id]
        joint_id = frame.parent

        while joint_id != 0 and dof_count < max_dof:
            joint = model.joints[joint_id]
            if joint.idx_v >= 0:
                indices.append(joint.idx_v)
                dof_count += joint.nv
            joint_id = model.parents[joint_id]

        return indices

    def broadcast_tf(self, T, child_frame, parent_frame):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = parent_frame
        t.child_frame_id = child_frame
        t.transform.translation.x, t.transform.translation.y, t.transform.translation.z = T.translation
        q = pin.Quaternion(T.rotation)
        t.transform.rotation.x = q.x
        t.transform.rotation.y = q.y
        t.transform.rotation.z = q.z
        t.transform.rotation.w = q.w
        self.tf_broadcaster.sendTransform(t)


def main():
    rclpy.init()
    rclpy.spin(SingleArmIKRetargeting())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
