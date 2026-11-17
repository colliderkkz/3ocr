# 原始模块清单

基线：Gitee master `757fede`。原始文件均保留，生成缓存未列出。

```text
README.md、README.en.md
ocr-menu-demo/{README.md,index.html,app.js,sample-menu.svg,demo-preview.png,PRD}
模块划分版本/
  组员1_OCR识别/{ocr_engine.py,menu_parser.py,run_demo.py,test_ocr.py,requirements-ocr.txt,sample/}
  组员2_后端接口/{server.py,db.py,test_backend.py,API.md,README.md,start.cmd,backend-home.html,sample/}
  组员3_前端页面/{index.html,app.js,README.md,sample-menu.svg,sample-menu.png,demo-preview.png}
```

| 组件 | 职责 | 依赖与现状 |
|---|---|---|
| 原 Demo | 浏览器菜单校验、样例和导出原型 | 静态 HTML/JS；与组员 3 的页面有大量共同功能 |
| OCR | 图片预处理、OCR 引擎适配、菜单字段解析 | Python；可选 OpenCV、RapidOCR；Windows 适配引用的脚本在基线缺失 |
| 后端 | HTTP API、OCR 上传、SQLite 门店及菜品数据、XLSX 导出 | Python 标准库；自动导入同级 OCR、托管同级前端 |
| 前端 | 图片上传、人工校验、门店和菜品操作、导出 | 原生 HTML/CSS/JS；localStorage/IndexedDB 与后端 API 并存 |

OCR 脚本 `windows_ocr.ps1` 在历史中存在但 master 缺失，且 RapidOCR 未安装时自动回退会失败。前端从 Demo 演进，已有 API 接入；不能只按目录名称认为三个模块尚未连接。项目未发现常规构建系统；前端字体依赖 Google Fonts 网络。未在扫描结果中发现真实硬编码密钥；这不是安全审计保证。
