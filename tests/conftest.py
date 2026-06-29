import os
import sys

# Make the project root importable so `backend.*` resolves in all test modules.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
