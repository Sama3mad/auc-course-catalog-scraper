import os
import glob
import re
from pathlib import Path

def main():
    root = Path(".")
    
    # Create directories
    for d in ["data", "scrapers", "parsers", "processors", "tests"]:
        (root / d).mkdir(exist_ok=True)
        
    # JSON files
    json_files = list(root.glob("*.json")) + list(root.glob("*.json.backup"))
    for jf in json_files:
        if jf.is_file():
            jf.rename(root / "data" / jf.name)
            
    # Python files categories
    categories = {
        "scrapers": ["scrape_*.py"],
        "parsers": ["parse_*.py"],
        "processors": ["add_*.py"],
        "tests": ["test_*.py"]
    }
    
    for folder, patterns in categories.items():
        for pattern in patterns:
            for py_file in root.glob(pattern):
                if py_file.is_file() and py_file.name != "test_parse.py":
                    # Read content
                    content = py_file.read_text(encoding="utf-8")
                    
                    # Add pathlib import if needed
                    if "from pathlib import Path" not in content and "import pathlib" not in content:
                        content = "from pathlib import Path\n" + content
                    
                    # Replace JSON filename strings with robust Path(__file__).parent / "../data/..."
                    json_names = [
                        "computer_engineering_courses.json", "math_courses.json", 
                        "computer_science_courses.json", "core_courses.json", 
                        "all_courses.json", "all_courses.json.backup",
                        "final_all_courses.json", "final_all_courses.json.backup",
                        "parsed_ce_courses.json", "parsed_courses.json"
                    ]
                    
                    for jn in json_names:
                        # Replace Path("...")
                        content = content.replace(f'Path("{jn}")', f'(Path(__file__).parent / "../data/{jn}").resolve()')
                        content = content.replace(f"Path('{jn}')", f"(Path(__file__).parent / '../data/{jn}').resolve()")
                        
                        # Replace "..." when used mostly as string constants
                        content = re.sub(
                            fr'(?<!Path\()"{jn}"', 
                            fr'str((Path(__file__).parent / "../data/{jn}").resolve())', 
                            content
                        )
                        content = re.sub(
                            fr"(?<!Path\()'{jn}'", 
                            fr"str((Path(__file__).parent / '../data/{jn}').resolve())", 
                            content
                        )
                    
                    py_file.write_text(content, encoding="utf-8")
                    py_file.rename(root / folder / py_file.name)
                    
    # test_parse.py might be running, maybe skip or just move
    for py_file in root.glob("test_parse.py"):
        try:
            py_file.rename(root / "tests" / py_file.name)
        except Exception:
            pass

if __name__ == "__main__":
    main()
