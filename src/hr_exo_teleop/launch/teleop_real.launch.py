"""真机遥操作: FK 正解 + pink IK 逆解(不含任何仿真节点)。

配套外部组件:
    - standalone/bin/ROS_2/MessageBridge   外骨骼数据 -> ROS2 话题
    - standalone/bin/Puppetry              遥操作主程序(发布 *_ee/target)
    - 机械臂真实驱动                        发布 /client_robot/joint_states,
                                          订阅 /target_robot/joint_commands

用法:
    ros2 launch hr_exo_teleop teleop_real.launch.py [use_rviz:=true]
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch.conditions import IfCondition
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue

HR_UP_SHARE = FindPackageShare('hr_up_7dof_fixed')
URDF_PATH = PathJoinSubstitution([HR_UP_SHARE, 'urdf', 'HR-UP-7DOF-3KG-R-B01382-URDF-1029.urdf'])
RVIZ_CONFIG = PathJoinSubstitution([HR_UP_SHARE, 'rviz', 'hr_up_fixed.rviz'])
TELEOP_PARAMS = PathJoinSubstitution([FindPackageShare('hr_exo_teleop'), 'config', 'hr_up.yaml'])


def generate_launch_description():
    use_rviz = LaunchConfiguration('use_rviz')

    return LaunchDescription([
        DeclareLaunchArgument('use_rviz', default_value='false',
                              description='启动 RViz 可视化(默认关闭, 真机现场一般不需要)'),

        # 1. TF 树: 真机关节状态 -> /tf
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            # ParameterValue(value_type=str)：Humble launch 会把参数值当 YAML 解析，
            # URDF(XML) 会报 "Unable to parse ... as yaml"，必须显式声明为字符串
            parameters=[{'robot_description': ParameterValue(Command(['cat ', URDF_PATH]), value_type=str)}],
            remappings=[('/joint_states', '/client_robot/joint_states')],
        ),

        # 2. FK 正解: 机械臂实际末端位姿 -> /target_robot/{left,right}_ee/state
        # output='both': 屏幕实时可见 + 自动写入 ~/.ros/log 当次运行目录(现场取证用)
        Node(
            package='robot_fk_adapter',
            executable='joint_to_pose_adapter',
            name='fk_adapter',
            output='both',
            parameters=[TELEOP_PARAMS],
        ),

        # 3. pink IK 逆解: 外骨骼目标位姿 -> /target_robot/joint_commands
        Node(
            package='robot_ik_retargeting',
            executable='ik_node',
            name='ik_retargeting',
            output='both',
            parameters=[TELEOP_PARAMS, {'urdf_path': URDF_PATH}],
        ),

        # 4. RViz 可视化(可选)
        Node(
            condition=IfCondition(use_rviz),
            package='rviz2',
            executable='rviz2',
            name='rviz',
            arguments=['-d', RVIZ_CONFIG],
        ),
    ])
