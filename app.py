"""Entrypoint used by Streamlit Community Cloud.

The application code follows a ``src/`` layout, while the deployment is
configured to start ``app.py`` from the repository root.  Add ``src`` to the
module search path so this works whether or not the package was installed
editable before Streamlit starts.
"""

from __future__ import annotations

import sys
from pathlib import Path


SRC_DIRECTORY = Path(__file__).resolve().parent / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

from competition_analysis.app import main


if __name__ == "__main__":
    main()
