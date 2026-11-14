from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

from src.ui.dashboard import render_app

render_app()
