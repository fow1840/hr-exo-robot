from setuptools import setup
import os
from glob import glob

package_name = 'hr_exo_teleop'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='HR-EXO-robot',
    maintainer_email='user@todo.todo',
    description='HR-UP exoskeleton teleoperation launch integration package',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # 预留：工作空间映射 / 主从缩放 / clutch 等自研节点在此注册
        ],
    },
)
