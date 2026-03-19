# 🐟 摸鱼阅读器 (Moyu Reader)

> 一款伪装成桌面背景的小说阅读器 —— 上班摸鱼神器

半透明无边框窗口 + 一键老板键，让你在工位上安心看小说。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 📖 网页抓取 | 输入小说网址，自动提取正文内容，识别「下一章」链接 |
| 📂 TXT 导入 | 打开本地 TXT 文件，自动按章节标题分章，无章节时按字数分页 |
| 🐟 摸鱼模式 | 半透明 + 无边框 + 窗口置顶 + 暗色主题，融入桌面背景 |
| 🚨 老板键 | 按 `Esc` 一键最小化，摸鱼模式下同样生效 |
| 🎨 外观调节 | 右键菜单调节字体、字号、行距、窗口透明度 |
| 📌 窗口置顶 | 阅读窗口始终在最前面 |
| 🔧 工具栏隐藏 | 隐藏顶部地址栏，界面更极简 |

## 📸 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Esc` | 老板键（最小化窗口） |
| `←` / `→` | 上一页 / 下一页 |
| `↑` / `↓` | 滚动正文 |
| `Ctrl+O` | 打开 TXT 文件 |
| `F2` | 在窗口中央弹出右键菜单 |
| `右键` | 打开设置菜单 |

## 🚀 快速开始

### 方式一：直接下载 exe（推荐）

前往 [Releases](https://github.com/gzg66/moyu-reader/releases) 下载最新版 `moyu-reader-v0.1.0.exe`，双击即可运行，无需安装 Python。

### 方式二：从源码运行

```bash
# 克隆仓库
git clone https://github.com/gzg66/moyu-reader.git
cd moyu-reader

# 安装依赖（需要 Python 3.11+）
pip install -r requirements.txt
# 或使用 uv
uv sync

# 运行
python main.py
```

## 📦 依赖

- Python >= 3.11
- ttkbootstrap — 现代化 tkinter 主题
- beautifulsoup4 + lxml — 网页解析
- requests — HTTP 请求
- chardet — 文件编码检测

## 🛠️ 打包为 exe

```bash
pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed \
    --name "小说阅读器" \
    --collect-all ttkbootstrap \
    --hidden-import ttkbootstrap \
    --hidden-import lxml \
    --hidden-import chardet \
    --hidden-import requests \
    main.py
```

打包完成后，exe 文件在 `dist/` 目录下。

## 📄 License

[MIT](LICENSE)
