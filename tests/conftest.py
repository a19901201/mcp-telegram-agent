"""pytest 共用設定：確保專案根目錄位於 sys.path，可直接 import 套件。"""

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

