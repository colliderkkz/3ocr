# G06-T007-1：菜单 OCR 基础能力

本目录是组员 1 的独立交付物，包含可运行的 OCR、菜单文本解析、测试样例和实际识别结果。该目录不依赖后端即可运行。

## 验收内容

- 对菜单图片执行 OCR。
- 输出菜品名称、价格、分类等结构化字段。
- 支持分类标题、同行价格、菜名与价格分离、缺失项和低置信度标记。
- 提供测试样例图片与实际 OCR 输出。

## 运行环境

- Python 3.10+
- Windows 10/11 可直接使用系统中文 OCR。
- 非 Windows 环境安装可选的 RapidOCR：

```powershell
python -m pip install -r requirements-ocr.txt
```

## 直接运行

```powershell
python run_demo.py
```

指定其他图片或输出文件：

```powershell
python run_demo.py --image "D:\menu.png" --output result.json
```

控制台会打印类似结果：

```text
宫保鸡丁        38        招牌热菜
麻婆豆腐        28        招牌热菜
水煮鱼          68        招牌热菜
红烧肉          58        招牌热菜
```

## 测试

```powershell
python -m unittest -v test_ocr
```

测试会调用真实 OCR 并校验样例图片是否返回菜名和价格。

## 文件说明

| 文件 | 作用 |
|---|---|
| `ocr_engine.py` | OCR 引擎适配、图片预处理 |
| `windows_ocr.ps1` | Windows 系统中文 OCR 调用脚本 |
| `menu_parser.py` | 菜名、价格、分类解析和异常标记 |
| `run_demo.py` | 命令行运行入口 |
| `sample/sample-menu.png` | 测试菜单图片 |
| `sample/sample-ocr-output.json` | 实际运行生成的识别结果 |

## 与其他模块拼接

组员 2 的后端会自动寻找同级目录 `组员1_OCR识别`，无需修改导入路径。三个提交目录应保持以下同级结构：

```text
组员1_OCR识别
组员2_后端接口
组员3_前端页面
```

## 上传 Gitee

```powershell
git init -b main
git add .
git commit -m "feat: add OCR recognition and menu parser"
git remote add origin https://gitee.com/你的用户名/你的仓库.git
git push -u origin main
```
