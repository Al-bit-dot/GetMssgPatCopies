# Opens GetMssgPatCopies without a console window (Windows: double-click this file).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import GetMssgPatCopies

sys.exit(GetMssgPatCopies.main())
