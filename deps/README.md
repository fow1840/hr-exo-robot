# deps/ — 离线依赖包

真机(目标机: Ubuntu 22.04 + ROS 2 Humble + Python 3.10 + x86_64)的离线安装物料，
在开发机上由 `scripts/download_deps.sh` 生成，随项目一起拷贝到真机。

| 目录 | 内容 | 生成方式 | 真机安装方式 |
|------|------|----------|--------------|
| `pip/` | 仓库根目录 `requirements.txt` 全部传递依赖的 wheel + `pin_pink` wheel(--no-deps 单独装)。注意 requirements.txt 本身在仓库根目录，不在本目录 | `pip download --only-binary=:all:` | `install_deps.sh`: 先 `--no-deps` 装 pin_pink，再 `pip install --no-index --find-links=deps/pip -r requirements.txt`(根目录) |
| `apt/` | ROS 2 Humble 相关 .deb(package.xml 依赖 + **ros-humble-pinocchio 组** + colcon/rosdep/venv 工具) | `apt-get download` | `sudo apt-get install --no-download deps/apt/*.deb` |

日常不需要手动敲上面的命令，直接运行部署脚本:

```bash
./scripts/install_deps.sh           # 离线装依赖 + 导入自检
./scripts/install_deps.sh --build   # 装完顺便 colcon build --symlink-install
```

## 配方要点(Walker S2 真机实证，详见 `docs/deployment/3：IK的依赖得配置.md`)

- **Pinocchio 走 apt**（`ros-humble-pinocchio` 4.0.0，依赖 `ros-humble-coal`/`eigenpy`），
  不走 pip——pip 的 `pin` 会遮蔽 ROS 版，连续求解 native 崩溃(P-016 M3 实证)。
  因此 `pip/` 里没有 pin 及 cmeel 系列 wheel。
- **`pin-pink==3.5.0` 必须 `--no-deps`** 安装，阻止 pip 自动拉入遮蔽版 pin。
- **numpy 锁 1.26.4**: numpy 2.x 与 apt pinocchio ABI 不兼容，import 即段错误(本机实证)。
- `install_deps.sh` 自检会 import pinocchio(需 source ROS)并断言 numpy 为 1.x。

## 注意事项

- wheel/deb 与 **x86_64 + Python 3.10** 平台绑定，换架构或换 Ubuntu 版本必须重新在对应平台跑 `download_deps.sh`。
- `deps/apt/` 覆盖本项目 package.xml 声明的 ROS 包、pinocchio 组及直连工具；pinocchio 的深层系统库
  (libboost1.74、libeigen3-dev、python3-dev 等)假定由目标机 ros-humble-desktop 基线提供，
  若真机缺件，离线 `apt` 会明确报缺哪个，此时需补网或单独补下对应 deb。
- `rosdep init/update` 需要联网，离线真机上跳过即可(不影响编译运行)。
