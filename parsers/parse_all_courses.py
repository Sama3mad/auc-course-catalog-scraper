#!/usr/bin/env python3
"""
Standalone Prerequisite Parser Script

Usage:
    python parse_all_courses.py

This script will:
1. Read all_courses.json from the current directory
2. Parse all prerequisites into AST format
3. Output parsed_courses.json with the AST structures
"""

import json
import re
from typing import Dict, Any, Optional, List
from pathlib import Path


class PrerequisiteParser:
    """Parse prerequisite text into AST structure"""
    
    # Course code pattern: 4 letters followed by 4 digits, optional 1 letter suffix
    COURSE_PATTERN = r'\b[A-Z]{4}\s*\d{4}[A-Z]?\b'
    
    def __init__(self):
        self.text_conditions = {
            'standing': ['senior standing', 'junior standing', 'sophomore standing', 
                        'freshman standing', 'standing'],
            'approval': ['instructor approval', 'consent of instructor', 'approval',
                        'permission', 'instructor consent'],
            'exemption': ['exemption'],
            'preparation': ['preparation course', 'college level'],
        }
    
    def parse(self, prerequisites_text: str, concurrent_text: str = "") -> Dict[str, Any]:
        if not prerequisites_text and not concurrent_text:
            return {
                "prerequisites": None,
                "corequisites": None,
                "raw_text": ""
            }
        
        full_text = prerequisites_text.strip()
        raw_text = full_text
        
        prereq_node, concurrent_node = self._split_prereq_and_concurrent(full_text)
        
        if concurrent_text:
            raw_text += f" | Concurrent: {concurrent_text}"
            concurrent_from_field = self._parse_concurrent(concurrent_text)
            if concurrent_from_field:
                if concurrent_node:
                    concurrent_node = {
                        "type": "and",
                        "children": [concurrent_node, concurrent_from_field]
                    }
                else:
                    concurrent_node = concurrent_from_field
        
        # Cleanup: remove duplicated concurrent requirements from corequisites
        if prereq_node and concurrent_node:
            concurrent_prereqs = self._get_concurrent_prereqs(prereq_node)
            if concurrent_prereqs:
                concurrent_node = self._remove_courses_from_node(concurrent_node, concurrent_prereqs)
        
        return {
            "prerequisites": prereq_node,
            "corequisites": concurrent_node,
            "raw_text": raw_text
        }
    
    def _get_concurrent_prereqs(self, node: Optional[Dict[str, Any]]) -> set:
        if not node:
            return set()
            
        node_type = node.get("type")
        if node_type == "course":
            if node.get("is_concurrent") is True:
                return {node.get("course_code")}
            return set()
        elif node_type in ("and", "or"):
            result = set()
            for child in node.get("children", []):
                result.update(self._get_concurrent_prereqs(child))
            return result
        elif node_type == "group":
            return self._get_concurrent_prereqs(node.get("expression"))
            
        return set()
        
    def _remove_courses_from_node(self, node: Optional[Dict[str, Any]], courses_to_remove: set) -> Optional[Dict[str, Any]]:
        if not node or not courses_to_remove:
            return node
            
        node_type = node.get("type")
        if node_type == "course":
            if node.get("course_code") in courses_to_remove:
                return None
            return node
        elif node_type == "concurrent":
            new_course_node = self._remove_courses_from_node(node.get("course"), courses_to_remove)
            if not new_course_node:
                return None
            node["course"] = new_course_node
            return node
        elif node_type in ("and", "or"):
            new_children = []
            for child in node.get("children", []):
                new_child = self._remove_courses_from_node(child, courses_to_remove)
                if new_child:
                    new_children.append(new_child)
            if not new_children:
                return None
            if len(new_children) == 1:
                return new_children[0]
            node["children"] = new_children
            return node
        elif node_type == "group":
            new_expr = self._remove_courses_from_node(node.get("expression"), courses_to_remove)
            if not new_expr:
                return None
            node["expression"] = new_expr
            return node
            
        return node
    
    def _split_prereq_and_concurrent(self, text: str) -> tuple:
        if not text:
            return None, None
        
        text_lower = text.lower()
        if text_lower.startswith('concurrent') or text_lower.startswith('prerequisite: concurrent'):
            return None, self._parse_concurrent(text)
        
        concurrent_match = re.search(
            r'(,?\s*and\s+concurrent\s+with|,?\s*and\s+Concurrent\s+with|Must be taken concurrently with)',
            text,
            re.IGNORECASE
        )
        
        if concurrent_match:
            prereq_part = text[:concurrent_match.start()].strip()
            concurrent_part = text[concurrent_match.end():].strip()
            return self._parse_expression(prereq_part) if prereq_part else None, self._parse_concurrent(concurrent_part) if concurrent_part else None
            
        return self._parse_expression(text), None
    
    def _parse_concurrent(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        courses = re.findall(self.COURSE_PATTERN, text)
        note = ""
        if "for" in text.lower():
            note_match = re.search(r'for\s+(.+?)(?:\.|$)', text, re.IGNORECASE)
            if note_match:
                note = note_match.group(1).strip()
        
        if courses:
            if len(courses) > 1:
                course_node = {
                    "type": "or",
                    "children": [{"type": "course", "course_code": c.replace(" ", "")} for c in courses]
                }
            else:
                course_node = {"type": "course", "course_code": courses[0].replace(" ", "")}
            return {
                "type": "concurrent",
                "course": course_node,
                "note": note
            }
        return None
    
    def _parse_expression(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        text = text.strip()
        text = re.sub(r'^Pre-requisites\s+or\s+concurrent:\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^Prerequisite:\s*', '', text, flags=re.IGNORECASE)
        
        # Convert both "(or concurrent)" and "or concurrent" (and their "ly" variants) to a special token
        text = re.sub(r'\(\s*or\s+concurrent(?:ly)?\s*\)', '__OR_CONCURRENT__', text, flags=re.IGNORECASE)
        text = re.sub(r'\bor\s+concurrent(?:ly)?\b', '__OR_CONCURRENT__', text, flags=re.IGNORECASE)
        
        if '(' in text and ')' in text:
            return self._parse_with_groups(text)
            
        and_parts = self._split_on_and(text)
        if len(and_parts) > 1:
            children = [child for part in and_parts if (child := self._parse_or_expression(part.strip()))]
            if len(children) == 1:
                return children[0]
            elif children:
                return {"type": "and", "children": children}
        return self._parse_or_expression(text)
    
    def _split_on_and(self, text: str) -> List[str]:
        # Normalize commas between course codes into "and" so that lists like
        # "CSCE 3301 , CSCE 3401 , CSCE 3312" are treated as an AND-expression
        # and each course is captured individually.
        course_to_course_comma = rf'({self.COURSE_PATTERN})\s*,\s*(?={self.COURSE_PATTERN})'
        text = re.sub(course_to_course_comma, r'\1 and ', text)
        text = re.sub(r'\band\s+concurrent(?:ly)?\b', '~~~CONCURRENT~~~', text, flags=re.IGNORECASE)
        parts = re.split(r'\s+and\s+', text, flags=re.IGNORECASE)
        return [p.replace('~~~CONCURRENT~~~', 'and concurrent') for p in parts]
    
    def _parse_or_expression(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        or_parts = re.split(r'\s+or\s+', text, flags=re.IGNORECASE)
        if len(or_parts) > 1:
            children = [child for part in or_parts if (child := self._parse_atomic(part.strip()))]
            if len(children) == 1:
                return children[0]
            elif children:
                return {"type": "or", "children": children}
        return self._parse_atomic(text)
    
    def _parse_atomic(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        text = text.strip(' ,.')
        
        # Check for placeholder first
        placeholder_match = re.search(r'~~~GROUP\d+~~~', text)
        if placeholder_match:
            return {
                "type": "group_placeholder",
                "placeholder": placeholder_match.group(0)
            }
            
        is_concurrent = False
        if '__OR_CONCURRENT__' in text:
            is_concurrent = True
            text = text.replace('__OR_CONCURRENT__', '').strip()
            
        course_match = re.search(self.COURSE_PATTERN, text)
        if course_match:
            return {
                "type": "course",
                "course_code": course_match.group(0).replace(" ", ""),
                "is_concurrent": is_concurrent,
                "is_optional": False
            }
            
        category = "other"
        for cat, keywords in self.text_conditions.items():
            if any(k in text.lower() for k in keywords):
                category = cat
                break
                
        if category != "other" or len(text) > 5:
            return {
                "type": "text_condition",
                "condition": text,
                "category": category
            }
        return None
    
    def _parse_with_groups(self, text: str) -> Optional[Dict[str, Any]]:
        groups = []
        group_pattern = r'\([^()]+\)'
        placeholder_map = {}
        counter = 0
        
        def replace_group(match):
            nonlocal counter
            group_text = match.group(0)[1:-1]
            placeholder = f"~~~GROUP{counter}~~~"
            placeholder_map[placeholder] = group_text
            counter += 1
            return placeholder
        
        while re.search(group_pattern, text):
            text = re.sub(group_pattern, replace_group, text)
            
        result = self._parse_expression(text)
        result = self._replace_placeholders(result, placeholder_map)
        return result
    
    def _replace_placeholders(self, node: Optional[Dict[str, Any]], placeholder_map: Dict[str, str]) -> Optional[Dict[str, Any]]:
        if node is None:
            return None
        
        node_type = node.get("type")
        if node_type == "group_placeholder":
            placeholder = node["placeholder"]
            if placeholder in placeholder_map:
                group_text = placeholder_map[placeholder]
                group_node = self._parse_expression(group_text)
                return {"type": "group", "expression": group_node}
            return node
            
        elif node_type in ["and", "or"]:
            node["children"] = [new_child for child in node.get("children", []) if (new_child := self._replace_placeholders(child, placeholder_map))]
            return node
            
        elif node_type == "group":
            node["expression"] = self._replace_placeholders(node.get("expression"), placeholder_map)
            return node
            
        return node


def main():
    """Main function to parse all courses"""
    
    # File paths
    input_file = (Path(__file__).parent / "../data/all_courses.json").resolve()
    backup_file = (Path(__file__).parent / "../data/all_courses.json.backup").resolve()
    
    # Check if input file exists
    if not input_file.exists():
        print(f"❌ Error: {input_file} not found in current directory")
        print(f"   Current directory: {Path.cwd()}")
        return
    
    print(f"📖 Reading {input_file}...")
    
    # Load courses
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            courses = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        return
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return
    
    print(f"✅ Loaded {len(courses)} courses")
    
    # Create backup
    print(f"💾 Creating backup: {backup_file}...")
    try:
        import shutil
        shutil.copy2(input_file, backup_file)
        print(f"✅ Backup created")
    except Exception as e:
        print(f"⚠️  Warning: Could not create backup: {e}")
        response = input("Continue without backup? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    # Initialize parser
    parser = PrerequisiteParser()
    
    # Parse all courses
    print(f"🔄 Parsing prerequisites...")
    
    parsed_courses = []
    stats = {
        "total": len(courses),
        "with_prerequisites": 0,
        "with_corequisites": 0,
        "empty": 0,
        "errors": 0
    }
    
    for i, course in enumerate(courses, 1):
        try:
            # Extract prerequisite fields
            prereq_text = course.get("prerequisites", "").strip()
            concurrent_text = course.get("concurrent", "").strip()
            
            # Parse
            ast = parser.parse(prereq_text, concurrent_text)
            
            # Update stats
            if not prereq_text and not concurrent_text:
                stats["empty"] += 1
            if ast.get("prerequisites"):
                stats["with_prerequisites"] += 1
            if ast.get("corequisites"):
                stats["with_corequisites"] += 1
            
            # Add parsed AST to the course (preserves all original fields)
            course["prerequisite_ast"] = ast
            
            parsed_courses.append(course)
            
            # Progress indicator
            if i % 10 == 0 or i == len(courses):
                print(f"   Progress: {i}/{len(courses)} courses processed", end='\r')
        
        except Exception as e:
            print(f"\n⚠️  Error parsing course {course.get('title', 'Unknown')}: {e}")
            stats["errors"] += 1
            # Still add the course but with error info in AST
            course["prerequisite_ast"] = {
                "prerequisites": None,
                "corequisites": None,
                "raw_text": prereq_text,
                "parse_error": str(e)
            }
            parsed_courses.append(course)
    
    print()  # New line after progress
    
    # Save output (overwrite the same file)
    print(f"💾 Updating {input_file}...")
    
    try:
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(parsed_courses, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        print(f"⚠️  Your original file is backed up at: {backup_file}")
        return
    
    # Print statistics
    print("\n" + "="*60)
    print("📊 PARSING STATISTICS")
    print("="*60)
    print(f"Total courses:              {stats['total']}")
    print(f"With prerequisites:         {stats['with_prerequisites']}")
    print(f"With corequisites:          {stats['with_corequisites']}")
    print(f"Empty (no requirements):    {stats['empty']}")
    print(f"Parsing errors:             {stats['errors']}")
    print("="*60)
    
    print(f"\n✅ Done! {input_file} has been updated")
    print(f"📁 Backup saved to: {backup_file}")
    print(f"\n💡 Each course now has:")
    print(f"   - All original fields (unchanged)")
    print(f"   - New 'prerequisite_ast' field with parsed structure")
    
    # Show an example
    if parsed_courses:
        print(f"\n📝 Example parsed course:")
        example = next((c for c in parsed_courses if c.get("prerequisite_ast", {}).get("prerequisites")), None)
        if example:
            print(f"\n   Course: {example.get('title', 'N/A')}")
            print(f"   Raw: {example.get('prerequisites', 'N/A')}")
            print(f"   AST:")
            print(json.dumps(example.get("prerequisite_ast"), indent=6))


if __name__ == "__main__":
    main()