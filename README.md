# 双人在线迷宫游戏

这是一个使用Python编写的简单的双人在线迷宫游戏。玩家可以通过网络连接进行迷宫竞赛，看看谁能最先找到出口。

## 功能

- 双人在线游戏
- 生成随机迷宫
- 实时同步玩家位置
- 计时功能

## 安装

1. 克隆这个仓库到你的本地机器：
    ```bash
    git clone https://github.com/yourusername/online-maze-game.git
    ```
2. 进入项目目录：
    ```bash
    cd online-maze-game
    ```
3. 安装所需的依赖包：
    ```bash
    pip install -r requirements.txt
    ```

## 使用

1. 运行服务器：
    ```bash
    python server.py
    ```
2. 在两个不同的终端窗口中分别运行客户端：
    ```bash
    python client.py
    ```
3. 按照屏幕上的指示操作，开始游戏。

## 文件说明

- `server.py`：服务器端代码，负责处理玩家连接和游戏同步。
- `client.py`：客户端代码，玩家使用此程序连接到服务器并进行游戏。
- `maze.py`：迷宫生成和游戏逻辑代码。
- `requirements.txt`：列出项目所需的所有依赖包。

## 贡献

欢迎对这个项目进行贡献！你可以通过以下方式贡献：

1. 提交issue报告bug或提出新功能建议。
2. 提交pull request修复bug或实现新功能。

## 许可证

该项目采用MIT许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。

## 联系

如果你有任何问题或建议，请通过 [your-email@example.com](mailto:your-email@example.com) 联系我。

