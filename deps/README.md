# deps/ — 离线依赖包

真机(目标机: Ubuntu 22.04 + ROS 2 Humble + Python 3.10 + x86_64)的离线安装物料，
在开发机上由 `scripts/download_deps.sh` 生成，随项目一起拷贝到真机。

| 目录 | 内容 | 生成方式 | 真机安装方式 |
|------|------|----------|--------------|
| `pip/` | requirements.txt 及全部传递依赖的 wheel | `pip download --only-binary=:all:` | `pip install --no-index --find-links=deps/pip -r requirements.txt` |
| `apt/` | ROS 2 Humble 相关 .deb(package.xml 依赖 + colcon/rosdep 等工具) | `apt-get download` | `sudo apt-get install --no-download deps/apt/*.deb` |

日常不需要手动敲上面的命令，直接运行部署脚本:

```bash
./scripts/install_deps.sh           # 离线装依赖 + 导入自检
./scripts/install_deps.sh --build   # 装完顺便 colcon build --symlink-install
```

## 注意事项

- wheel/deb 与 **x86_64 + Python 3.10** 平台绑定，换架构或换 Ubuntu 版本必须重新在对应平台跑 `download_deps.sh`。
- pip 侧额外约束了 `setuptools<80`（osqp 无版本号依赖 setuptools，放任取最新会与 colcon-core 冲突、破坏 ament_python 编译）。
- `deps/apt/` 只覆盖本项目 package.xml 声明的 ROS 包及其直连工具；若真机的 Humble 安装不完整(比如缺 rviz2 的图形依赖)，离线 `apt` 会因缺依赖报错，此时需补网或参考 `scripts/install_deps.sh` 失败提示。
- `rosdep init/update` 需要联网，离线真机上跳过即可(不影响编译运行)。
