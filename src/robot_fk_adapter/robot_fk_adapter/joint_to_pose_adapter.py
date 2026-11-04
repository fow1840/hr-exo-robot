import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from geometry_msgs.msg import PoseStamped
from tf2_ros import Buffer, TransformListener, LookupException, ConnectivityException, ExtrapolationException

# 统计心跳周期(秒): 每隔该时间打印一次运行统计, 便于真机上确认链路是否还活着
STATS_PERIOD_SEC = 5.0
# TF 查询失败告警的节流周期(秒): 失败会随每帧关节数据反复发生, 不节流会刷屏
LOOKUP_WARN_THROTTLE_SEC = 5.0

class JointToPoseAdapter(Node):
    def __init__(self):
        super().__init__('joint_to_pose_adapter')

        # 1. 获取配置参数 [cite: 11]
        self.base_frame = self.declare_parameter('base_frame', 'waist_pitch_link').value
        self.left_ee_frame = self.declare_parameter('left_ee_frame', 'left_wrist_roll_link').value
        self.right_ee_frame = self.declare_parameter('right_ee_frame', 'right_wrist_roll_link').value

        # 2. 发布者：发送当前机器人位姿给遥操作外骨骼 (State) [cite: 12]
        self.left_state_pub = self.create_publisher(PoseStamped, '/target_robot/left_ee/state', 10)
        self.right_state_pub = self.create_publisher(PoseStamped, '/target_robot/right_ee/state', 10)

        # 3. TF 监听器 [cite: 13]
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # 4. 【关键】事件驱动：订阅关节状态话题 [cite: 13, 21]
        # 频率将严格跟随 /client_robot/joint_states 的发布频率
        self.sub_joint = self.create_subscription(
            JointState,
            '/client_robot/joint_states',
            self.joint_callback,
            10
        )

        # 5. 运行统计（真机调试用，仅计数不影响控制流）
        self._js_count = 0            # 收到的 joint_states 总帧数
        self._stats_t0 = time.monotonic()
        self._pub_count = {'left': 0, 'right': 0}    # 周期内实际发布的位姿数
        self._lookup_fail = {'left': 0, 'right': 0}  # 周期内 TF 查询失败次数

        self.get_logger().info(
            "FK adapter 配置: base_frame='{}', left_ee_frame='{}', right_ee_frame='{}', "
            "订阅=/client_robot/joint_states, 发布=/target_robot/{{left,right}}_ee/state".format(
                self.base_frame, self.left_ee_frame, self.right_ee_frame))
        self.get_logger().info("FK adapter 统计心跳: 每 {}s 打印一次收发统计; "
                               "TF 查询失败告警节流 {}s".format(
                                   STATS_PERIOD_SEC, LOOKUP_WARN_THROTTLE_SEC))

    def joint_callback(self, msg):
        """关节数据更新时的回调函数"""
        self._js_count += 1

        # 统计心跳：频率跟随关节数据。数据流断了心跳自然停，本身就是"上游断了"的信号
        now = time.monotonic()
        if now - self._stats_t0 >= STATS_PERIOD_SEC:
            elapsed = now - self._stats_t0
            self.get_logger().info(
                "统计[{}s]: joint_states 帧数={}, 实测频率≈{:.1f}Hz, 发布 left={} right={}, "
                "TF查询失败 left={} right={}".format(
                    int(elapsed), self._js_count, self._js_count / elapsed,
                    self._pub_count['left'], self._pub_count['right'],
                    self._lookup_fail['left'], self._lookup_fail['right']))
            self._stats_t0 = now
            self._js_count = 0
            self._pub_count = {'left': 0, 'right': 0}
            self._lookup_fail = {'left': 0, 'right': 0}

        # 直接利用最新产生的 TF 树进行正解发布 [cite: 15]
        self.publish_ee_pose(self.left_ee_frame, self.left_state_pub, 'left')
        self.publish_ee_pose(self.right_ee_frame, self.right_state_pub, 'right')

    def publish_ee_pose(self, ee_frame, publisher, side):
        try:
            # 查询从 base 到末端的坐标变换 [cite: 15]
            t = self.tf_buffer.lookup_transform(
                self.base_frame,
                ee_frame,
                rclpy.time.Time()) # 获取最新变换
        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            # 真机调试关键点: TF 树缺失/断链/时间戳异常时这里原来是无声吞掉,
            # 现在记失败计数 + 节流告警(含 frame 对, 便于直接定位是哪一段链路断了)
            self._lookup_fail[side] += 1
            self.get_logger().warning(
                "TF 查询失败(共{}次): {} -> {} 状态帧未更新. 原因: {}. "
                "排查: robot_state_publisher 是否在跑 / URDF 树是否含这两个 link / "
                "joint_states 时间戳是否正常".format(
                    self._lookup_fail[side], self.base_frame, ee_frame,
                    type(e).__name__),
                throttle_duration_sec=LOOKUP_WARN_THROTTLE_SEC)
            return

        pose_msg = PoseStamped()
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.header.frame_id = self.base_frame

        # 填充位置与四元数姿态 [cite: 16, 17]
        pose_msg.pose.position.x = t.transform.translation.x
        pose_msg.pose.position.y = t.transform.translation.y
        pose_msg.pose.position.z = t.transform.translation.z
        pose_msg.pose.orientation = t.transform.rotation

        publisher.publish(pose_msg)
        self._pub_count[side] += 1

def main(args=None):
    rclpy.init(args=args)
    node = JointToPoseAdapter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
