# 智能设计工作台 (Smart Design Workbench) v2.0

> 一个集数据清洗、资源匹配、资产处理于一体的电商设计自动化助手。

## 🎯 项目概述

本项目专为电商设计团队打造，旨在自动化处理繁琐的“数据-素材”匹配流程。它能够连接 Excel 数据与 Google Drive 素材库，自动完成图片查找、链接回填、切图处理等任务。

**推荐名称**: 如果需要在团队内部推广，建议使用 **"Smart Design Mate" (智能设计伴侣)** 或 **"E-Comm Design Hub" (电商设计中台)**，突显其“助手”和“连接器”的属性。但作为技术项目，`design_workbench` 是一个标准且清晰的工程命名，**无需更改文件夹名称**。

## ✨ 核心功能模块

### Step 1: 数据处理器 (Data Processor)
解决痛点：手动查找商品图片费时费力。

*   **☁️ Mode A: 云端实时回填 (Cloud-Sync)**
    *   **场景**: 当运营已经在 Google Sheet 中维护好数据，设计只需补全图片链接。
    *   **原理**: 程序读取 Sheet -> 根据 SKU 在 Drive 查找图片 -> 自动回填链接到表格。
    *   **优势**: 无需下载上传文件，全云端操作，实时生效。

*   **📋 Mode B: 数据粘贴模式 (Local-Paste)**
    *   **场景**: 临时处理少量数据，或者处理非标准格式的 Excel 数据。
    *   **原理**: 直接粘贴 Excel 内容 -> 自动解析 -> 匹配图片 -> 生成带链接的 Excel 下载。
    *   **优势**: 灵活快捷，即用即走。

*   **📂 Mode C: 文件上传模式 (Legacy/Upload)**
    *   **场景**: 标准化的大批量数据处理流程。
    *   **原理**: 上传标准模板 Excel -> 深度清洗 -> 匹配图片 -> 更新至指定 Sheet。

### Step 2: 切图处理器 (Slice Processor)
解决痛点：Figma 导出切图命名乱、体积大。
*   **功能**: 
    1. 自动重命名切图（按顺序 1.jpg, 2.jpg...）
    2. 智能缩放至标准宽度 (750px)
    3. 高效压缩体积 (<150KB)
    4. 一键打包下载

### Step 3: 素材下载器 (Image Downloader)
解决痛点：手动从官网/图库下载图片效率低。
*   **功能**: 输入 SKU，自动抓取并通过 Image Bank 下载标准套图。

## � 快速启动

**推荐方式**:  
直接双击根目录下的 **`启动智能设计工作台.bat`** 即可自动启动服务并打开浏览器。

**手动方式**:
```bash
python app.py
```
访问地址: `http://127.0.0.1:5000`

## 🛠️ 环境配置与依赖

使用前请确保根目录下包含以下关键文件（已在 `.gitignore` 中排除，需手动配置）：
*   `config.ini`: 指定 Python 解释器路径。
*   `config.json`: 定义项目类型、Drive 文件夹映射、表格列名规则。
*   `credentials.json` & `token.json`: Google API 认证凭证。

**依赖安装**:
主要依赖包括 `Flask`, `pandas`, `numpy`, `google-api-python-client`, `Pillow` 等。
如果遇到环境问题，请检查 `config.ini` 中的 Python 路径是否正确。

## � 问题排查工具

为了方便诊断 Google 连接问题，项目中包含了一个独立测试脚本：
*   **`test_google_sheet.py`**: 用于测试 Google Sheet 链接是否有效、权限是否足够。
    *   运行方式: `python test_google_sheet.py [Your_Spreadsheet_ID]`
    *   或者直接运行脚本并根据提示输入链接。

## ⚠️ 常见问题 FAQ

**Q: Mode A 提示 "404 Not Found" 或 "读取失败"?**
A: 这通常意味着：
1.  Google Sheet 链接/ID 不完整。
2.  该表格没有开启“知道链接的任何人均可编辑”权限，且未单独分享给您的 Google 账号。
3.  请运行 `test_google_sheet.py` 进行确诊。

**Q: 如何修改项目配置？**
A: 编辑 `config.json` 文件，仿照 `config.json.example` 的格式添加新项目。

**Q: 切图处理后颜色变了？**
A: 请确保上传的切图是 RGB 模式。如果是 CMYK，程序会自动转换为 RGB，可能会有轻微色差。

---
© 2026 Smart Design Workbench Team
