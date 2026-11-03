import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from geometry_msgs.msg import PoseStamped
from tf2_ros import Buffer, TransformListener, LookupException, ConnectivityException, ExtrapolationException

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
        self.get_logger().info(f"High-frequency adapter active. Listening to /client_robot/joint_states")

    def joint_callback(self, msg):
        """关节数据更新时的回调函数"""
        # 直接利用最新产生的 TF 树进行正解发布 [cite: 15]
        self.publish_ee_pose(self.left_ee_frame, self.left_state_pub)
        self.publish_ee_pose(self.right_ee_frame, self.right_state_pub)

    def publish_ee_pose(self, ee_frame, publisher):
        try:
            # 查询从 base 到末端的坐标变换 [cite: 15]
            t = self.tf_buffer.lookup_transform(
                self.base_frame, 
                ee_frame, 
                rclpy.time.Time()) # 获取最新变换

            pose_msg = PoseStamped()
            pose_msg.header.stamp = self.get_clock().now().to_msg()
            pose_msg.header.frame_id = self.base_frame
            
            # 填充位置与四元数姿态 [cite: 16, 17]
            pose_msg.pose.position.x = t.transform.translation.x
            pose_msg.pose.position.y = t.transform.translation.y
            pose_msg.pose.position.z = t.transform.translation.z
            pose_msg.pose.orientation = t.transform.rotation

            publisher.publish(pose_msg)
        except (LookupException, ConnectivityException, ExtrapolationException):
            pass

def main(args=None):
    rclpy.init(args=args)
    node = JointToPoseAdapter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()