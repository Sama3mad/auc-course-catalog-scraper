from pathlib import Path
import json
import re

with open(str((Path(__file__).parent / "../data/computer_engineering_courses.json").resolve()), "r", encoding="utf-8") as f:
    courses = json.load(f)

for c in courses:
    code = c.get('course_code')
    if code in ['ECON 5219', 'CSCE 2202']:
        print(f"--- {code} ---")
        print(f"Prereq text: {c.get('prerequisites', '')}")
        print(f"Concurrent text: {c.get('concurrent', '')}")
        print()
