"""TEMPORARY: run the source doctor on GitHub's network (removed before merge)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doctor
doctor.main(["--all"])
