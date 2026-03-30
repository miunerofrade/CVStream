# CVStream 

一个极简、无界、全自动的网课抓取与 AI 知识提炼流媒体工具。

CVStream 采用现代化的单页 UI 设计，集成了无感拦截、本地/云端语音转写（ASR）、视觉切片（PPT 提取）以及基于大语言模型（LLM）的自动化总结功能。

## ✨ 核心特性

- **无感流媒体拦截**：基于 Playwright 的底层网络嗅探，突破常规下载限制。
- **极简无界 UI**：抛弃传统软件的厚重感，采用类似 macOS/iOS 的全白背板与极细边框排版。
- **本地内存加速 (Ramdisk)**：内置 ImDisk 虚拟盘调度，高频 I/O 数据直接走内存，大幅延长物理 SSD 寿命。
- **全栈 AI 赋能**：
  - **ASR 转写**：支持 Faster-Whisper 本地离线转写，或对接阿里、讯飞、百度等云端 API。
  - **LLM 知识提炼**：支持 DeepSeek、Kimi、智谱、豆包等大模型，自动将碎片化转录转化为结构化 Markdown 讲义。
- **多模态提取**：支持智能抽帧提取 PPT 画面，过滤重复帧并自动合成 PDF。

## 🛠️ 安装与运行

### 1. 环境准备
确保已安装 Python 3.8+，建议使用虚拟环境（venv 或 conda）。

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 初始化浏览器内核

本项目依赖 Playwright 进行网络嗅探，首次运行前必须安装 Chromium 内核：


```Bash
playwright install chromium
```

### 4. 启动项目


```Bash
streamlit run main.py
```
## 📖 首次使用与配置排障指南

1. **授权初始化（重要）**： 初次运行或修改密码后，请进入左侧【参数配置】页面，输入账号密码后点击 **“初始化授权环境”**。请在弹出的可视化浏览器中手动完成验证码校验，以打通安全信道。
    
2. **本地 ASR 模型路径**： 若使用本地 Faster-Whisper 进行语音识别，请提前下载好模型（如 `faster-whisper-tiny`），并在【任务中心】的“模型调度配置”区域指定该模型所在的本地目录。
    
3. **LLM API 密钥配置**： AI 总结功能需要用到大模型 API。请在配置区域填入对应的 Base URL 和 API Key。
    
    - _注意：若使用火山引擎（豆包），需在“自定义模型版本”中手动添加并选择你生成的 `ep-xxxx` 格式的接入点 ID。_
        
4. **数据安全**： 所有凭据及 API Key 均会通过系统底层硬件特征进行混合加密，并保存在本地的 `config.json` 中。
    

## ⚖️ 第三方鸣谢声明

本项目的运行依赖或调用了以下优秀的开源/免费工具，特此鸣谢：

- [Streamlit](https://streamlit.io/) - 极简的纯 Python Web 框架
    
- [Playwright](https://playwright.dev/) - 强大的端到端浏览器自动化工具
    
- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) - 高效的本地语音识别引擎
    
- [ImDisk Toolkit](https://sourceforge.net/projects/imdisk-toolkit/) - 虚拟内存盘驱动核心（Windows 系统级 IO 加速）
    

## 声明

本项目仅供编程学习与学术交流使用。请遵守目标网站的用户协议，切勿用于商业或非法用途。