"""
Entrypoint script for generating/updating the HTML Dashboard for Day 10 Lab.
Role 4 (R4) - RAG & Demo Owner
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.config import load_settings
from src.presentation.dashboard import generate_dashboard_html


def main() -> None:
    settings = load_settings()
    output_file = generate_dashboard_html(settings)
    print(f"[OK] Dashboard generated successfully at: {output_file}")


if __name__ == "__main__":
    main()
