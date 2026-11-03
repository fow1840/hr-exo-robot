import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from geometry_msgs.msg import PoseStamped
from tf2_ros import (
    Buffer,
    TransformListener,
    LookupException,
    ConnectivityException,
    ExtrapolationException,
)


class SingleJointToPoseAdapter(Node):
    def __init__(self):
        super().__init__('single_joint_to_pose_adapter')

        self.base_frame = self.declare_parameter('base_frame', 'link0').value
        self.ee_frame = self.declare_parameter('ee_frame', 'Link7').value
        self.joint_states_topic = self.declare_parameter(
            'joint_states_topic', '/client_robot/joint_states'
        ).value
        self.output_topic = self.declare_parameter(
            'output_topic', '/target_robot/right_ee/state'
        ).value

        self.state_pub = self.create_publisher(PoseStamped, self.output_topic, 10)

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.sub_joint = self.create_subscription(
            JointState,
            self.joint_states_topic,
            self.joint_callback,
            10,
        )

        self.get_logger().info(
            f'Single-arm FK adapter active. Listening to {self.joint_states_topic}, '
            f'publishing to {self.output_topic}'
        )

    def joint_callback(self, _msg: JointState):
        self.publish_ee_pose()

    def publish_ee_pose(self):
        try:
            t = self.tf_buffer.lookup_transform(
                self.base_frame,
                self.ee_frame,
                rclpy.time.Time(),
            )

            pose_msg = PoseStamped()
            pose_msg.header.stamp = self.get_clock().now().to_msg()
            pose_msg.header.frame_id = self.base_frame

            pose_msg.pose.position.x = t.transform.translation.x
            pose_msg.pose.position.y = t.transform.translation.y
            pose_msg.pose.position.z = t.transform.translation.z
            pose_msg.pose.orientation = t.transform.rotation

            self.state_pub.publish(pose_msg)
        except (LookupException, ConnectivityException, ExtrapolationException):
            pass


def main(args=None):
    rclpy.init(args=args)
    node = SingleJointToPoseAdapter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
