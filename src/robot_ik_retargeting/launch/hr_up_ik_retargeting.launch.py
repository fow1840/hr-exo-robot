from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

# ============================================================================
# pink IK 逆解链路独立 launch（HR-UP 双 7-DOF；单模块调试用）。
# 整链联调（FK+IK+驱动）请用 hr_exo_teleop 的 teleop_sim/teleop_real.launch.py，
# 参数以 src/hr_exo_teleop/config/hr_up.yaml 为参数中枢。
#
# 机器人模型以 src/hr_up_7dof_fixed 的 URDF 为准：
#   根连杆 base_mount -(fixed)-> base，双臂挂在 base 上；
#   右臂 Joint1..Joint7   -> 末端 Link7（y<0）
#   左臂 Joint1L..Joint7L -> 末端 Link7L（y>0）
#
# 帧契约（三处必须一致，见 docs/deployment/4：FK_和IK_的配置部署.md）：
#   MessageBridge.yaml.base_frame == fk_adapter.base_frame
#                                 == ik_retargeting.ref_link_name == "base"
# ============================================================================

def generate_launch_description():
    # ================= 参数定义 =================
    pkg_name_arg = DeclareLaunchArgument(
        'description_package',
        default_value='hr_up_7dof_fixed',
        description='Name of the robot description package'
    )

    urdf_file_arg = DeclareLaunchArgument(
        'urdf_relative_path',
        default_value='urdf/HR-UP-7DOF-3KG-R-B01382-URDF-1029.urdf',
        description='Relative path to the URDF file'
    )

    # 1. 目标 Link（外骨骼控制的末端）
    # ik_node 内部约定：target_link_names[0]=右臂末端，[1]=左臂末端
    # （代码 ee_frames = {'right': target_links[0], 'left': target_links[1]}，顺序不能颠倒）
    default_target_links = ["Link7", "Link7L"]

    # 2. 拟人化姿态配置（Null-space PostureTask 引导，弧度制）
    # HR-UP 为 SolidWorks 导出模型，关节轴向/符号需真机实测确认后再填；
    # 留空 = 全零中立位（与 hr_exo_teleop/config/hr_up.yaml 保持一致）。
    # 填法示例（届时按实测符号调整）：
    #   preferred_joints_default = ["Joint4", "Joint4L"]
    #   preferred_angles_default = [0.5, -0.5]
    preferred_joints_default = []
    preferred_angles_default = []

    # ================= 路径解析 =================
    urdf_path_resolved = PathJoinSubstitution([
        FindPackageShare(LaunchConfiguration('description_package')),
        LaunchConfiguration('urdf_relative_path')
    ])

    # ================= 节点配置 =================
    ik_params = {
        'urdf_path': urdf_path_resolved,
        'root_link_name': 'base',   # URDF 根链: base_mount -(fixed)-> base，双臂挂在 base 上
        'ref_link_name': 'base',    # 必须与 fk_adapter.base_frame / MessageBridge.yaml.base_frame 一致
        'target_link_names': default_target_links,
        'max_dof': 7,               # 从末端向上追溯的自由度数（双臂均为 7 DOF）
    }

    # 拟人化参数: 仅在填入具体关节/角度后才传入 launch。
    # 空的 Python 列表在 Humble launch 中无法自动定型(会报
    # "Expected 'value' to be one of ..." 或 "expected a list of float"),
    # 节点侧已用 dynamic_typing 兼容"参数未提供"的情形, 留空即全零中立位。
    if preferred_joints_default:
        ik_params['preferred_joints'] = preferred_joints_default
        ik_params['preferred_angles'] = preferred_angles_default

    ik_node = Node(
        package='robot_ik_retargeting',
        executable='ik_node',
        name='ik_retargeting',
        output='both',   # 屏幕实时可见 + 写入 ~/.ros/log 当次运行 launch.log(取证)
        parameters=[ik_params]
    )

    return LaunchDescription([
        pkg_name_arg,
        urdf_file_arg,
        ik_node
    ])
