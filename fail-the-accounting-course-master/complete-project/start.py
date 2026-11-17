"""从完整项目根目录启动原有后端和前端。"""
from pathlib import Path
import runpy
import sys

backend = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend))
runpy.run_path(str(backend / "server.py"), run_name="__main__")
