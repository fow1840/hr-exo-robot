
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, Command, PathJoinSubstitution
from launch.conditions import IfCondition
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue

# ============================================================================
# FK 正解链路独立 launch（单模块调试用；整链联调用 hr_exo_teleop 的 teleop_*.launch.py）
#
# 机器人模型以 src/hr_up_7dof_fixed 的 URDF 为准（HR-UP-7DOF-3KG-R-B01382-URDF-1029）：
#   根连杆 base_mount -(fixed: base_mount_to_base)-> base，
#   右臂 Joint1..Joint7   挂在 base 上（y<0），末端 Link7
#   左臂 Joint1L..Joint7L 挂在 base 上（y>0），末端 Link7L
#
# 帧契约（三处必须一致，见 docs/deployment/4：FK_和IK_的配置部署.md）：
#   MessageBridge.yaml.base_frame == fk_adapter.base_frame
#                                 == ik_retargeting.ref_link_name == "base"
# ============================================================================

def generate_launch_description():
    pkg_share = FindPackageShare('hr_up_7dof_fixed')
    urdf_path = PathJoinSubstitution([pkg_share, 'urdf', 'HR-UP-7DOF-3KG-R-B01382-URDF-1029.urdf'])
    # 默认加载的 RViz 配置路径
    default_rviz_config_path = PathJoinSubstitution([pkg_share, 'rviz', 'hr_up_fixed.rviz'])

    # 参数定义
    use_sim = LaunchConfiguration('use_sim')
    use_rviz = LaunchConfiguration('use_rviz')

    return LaunchDescription([
        DeclareLaunchArgument('use_sim', default_value='false', description='Set to false for real robot'),
        DeclareLaunchArgument('use_rviz', default_value='true'),

        # 1. Robot State Publisher (始终运行)
        # 负责将全量关节状态转换为 TF 树供适配器查询
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            # ParameterValue(value_type=str) 是必须的：Humble 的 launch 会把参数值
            # 当 YAML 解析，URDF 是 XML 会直接报 "Unable to parse ... as yaml"
            parameters=[{'robot_description': ParameterValue(Command(['cat ', urdf_path]), value_type=str)}],
            remappings=[('/joint_states', '/client_robot/joint_states')]
        ),

        # 2. FK Pose Adapter (始终运行)
        # 采用订阅触发模式，反馈频率与关节状态话题同步
        # base_frame 必须是 URDF 中真实存在的 link（HR-UP 为 "base"，没有 base_link）
        # output='both': 屏幕实时可见 + 自动写入 ~/.ros/log 当次运行目录
        Node(
            package='robot_fk_adapter',
            executable='joint_to_pose_adapter',
            name='fk_adapter',
            output='both',
            parameters=[{
                'base_frame': 'base',
                'left_ee_frame': 'Link7L',
                'right_ee_frame': 'Link7'
            }]
        ),

        # 3. Dummy Robot Driver (仅在仿真模式启动)
        # 提供初始 0.0 关节状态并接收 IK 指令
        Node(
            condition=IfCondition(use_sim),
            package='robot_fk_adapter',
            executable='dummy_robot_driver',
            name='dummy_driver',
            parameters=[{'urdf_path': urdf_path, 'publish_frequency': 500.0}]
        ),

        # 4. RViz 可视化
        Node(
            condition=IfCondition(use_rviz),
            package='rviz2',
            executable='rviz2',
            name='rviz_monitor',
            arguments=['-d', default_rviz_config_path],
        )
    ])
