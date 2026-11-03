"""仿真闭环遥操作: FK 正解 + pink IK 逆解 + 假体驱动 + RViz 可视化。

不连接任何真实设备, 用于在没有外骨骼/机械臂时验证整条链路:
    dummy_driver(500Hz 假体) -> /client_robot/joint_states
        -> robot_state_publisher(TF) -> fk_adapter -> /target_robot/*_ee/state
    手动或脚本发布 /target_robot/*_ee/target + /clutch/*
        -> ik_node(pink IK) -> /target_robot/joint_commands -> dummy_driver

用法:
    ros2 launch hr_exo_teleop teleop_sim.launch.py [use_rviz:=false]
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch.conditions import IfCondition
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

HR_UP_SHARE = FindPackageShare('hr_up_7dof_fixed')
URDF_PATH = PathJoinSubstitution([HR_UP_SHARE, 'urdf', 'HR-UP-7DOF-3KG-R-B01382-URDF-1029.urdf'])
RVIZ_CONFIG = PathJoinSubstitution([HR_UP_SHARE, 'rviz', 'hr_up_fixed.rviz'])
TELEOP_PARAMS = PathJoinSubstitution([FindPackageShare('hr_exo_teleop'), 'config', 'hr_up.yaml'])


def generate_launch_description():
    use_rviz = LaunchConfiguration('use_rviz')

    return LaunchDescription([
        DeclareLaunchArgument('use_rviz', default_value='true',
                              description='启动 RViz 可视化'),

        # 1. TF 树: URDF + 关节状态 -> /tf (FK 的数据源)
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            parameters=[{'robot_description': Command(['cat ', URDF_PATH])}],
            remappings=[('/joint_states', '/client_robot/joint_states')],
        ),

        # 2. FK 正解: 末端位姿反馈 /target_robot/{left,right}_ee/state
        Node(
            package='robot_fk_adapter',
            executable='joint_to_pose_adapter',
            name='fk_adapter',
            output='screen',
            parameters=[TELEOP_PARAMS],
        ),

        # 3. pink IK 逆解: 目标位姿 -> /target_robot/joint_commands
        Node(
            package='robot_ik_retargeting',
            executable='ik_node',
            name='ik_retargeting',
            output='screen',
            parameters=[TELEOP_PARAMS, {'urdf_path': URDF_PATH}],
        ),

        # 4. 假体驱动: 提供初始关节状态并跟随 IK 指令(仿真闭环)
        Node(
            package='robot_fk_adapter',
            executable='dummy_robot_driver',
            name='dummy_driver',
            output='screen',
            parameters=[TELEOP_PARAMS, {'urdf_path': URDF_PATH}],
        ),

        # 5. RViz 可视化
        Node(
            condition=IfCondition(use_rviz),
            package='rviz2',
            executable='rviz2',
            name='rviz',
            arguments=['-d', RVIZ_CONFIG],
        ),
    ])
