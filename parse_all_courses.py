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
    
    # Course code pattern: 4 letters followed by 4 digits
    COURSE_PATTERN = r'\b[A-Z]{4}\s*\d{4}\b'
    
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
        """
        Parse prerequisite and concurrent text into AST.
        
        Args:
            prerequisites_text: The prerequisites field text
            concurrent_text: The concurrent field text (if separate)
        
        Returns:
            PrerequisiteAST dictionary
        """
        if not prerequisites_text and not concurrent_text:
            return {
                "prerequisites": None,
                "corequisites": None,
                "raw_text": ""
            }
        
        # Combine texts for processing
        full_text = prerequisites_text.strip()
        raw_text = full_text
        
        # Extract concurrent requirements
        prereq_node, concurrent_node = self._split_prereq_and_concurrent(full_text)
        
        # Add any concurrent from separate field
        if concurrent_text:
            raw_text += f" | Concurrent: {concurrent_text}"
            concurrent_from_field = self._parse_concurrent(concurrent_text)
            if concurrent_from_field:
                if concurrent_node:
                    # Merge both concurrent requirements
                    concurrent_node = {
                        "type": "and",
                        "children": [concurrent_node, concurrent_from_field]
                    }
                else:
                    concurrent_node = concurrent_from_field
        
        return {
            "prerequisites": prereq_node,
            "corequisites": concurrent_node,
            "raw_text": raw_text
        }
    
    def _split_prereq_and_concurrent(self, text: str) -> tuple:
        """Split text into prerequisite and concurrent parts"""
        if not text:
            return None, None
        
        text_lower = text.lower()
        
        # Check if it's ONLY a concurrent requirement
        if text_lower.startswith('concurrent') or text_lower.startswith('prerequisite: concurrent'):
            return None, self._parse_concurrent(text)
        
        # Split on "and concurrent", "concurrent with", etc.
        concurrent_match = re.search(
            r'(,?\s*and\s+concurrent\s+with|,?\s*and\s+Concurrent\s+with|Must be taken concurrently with)',
            text,
            re.IGNORECASE
        )
        
        if concurrent_match:
            prereq_part = text[:concurrent_match.start()].strip()
            concurrent_part = text[concurrent_match.end():].strip()
            
            prereq_node = self._parse_expression(prereq_part) if prereq_part else None
            concurrent_node = self._parse_concurrent(concurrent_part) if concurrent_part else None
            
            return prereq_node, concurrent_node
        
        # No concurrent found, it's all prerequisites
        return self._parse_expression(text), None
    
    def _parse_concurrent(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse concurrent/corequisite text"""
        if not text:
            return None
        
        # Extract course code
        courses = re.findall(self.COURSE_PATTERN, text)
        note = ""
        
        # Check for additional notes
        if "for" in text.lower():
            note_match = re.search(r'for\s+(.+?)(?:\.|$)', text, re.IGNORECASE)
            if note_match:
                note = note_match.group(1).strip()
        
        if courses:
            # If multiple courses, create OR node
            if len(courses) > 1:
                course_node = {
                    "type": "or",
                    "children": [{"type": "course", "course_code": c.replace(" ", "")} 
                                for c in courses]
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
        """Parse a prerequisite expression"""
        if not text:
            return None
        
        text = text.strip()
        
        # Handle "Pre-requisites or concurrent:" prefix
        text = re.sub(r'^Pre-requisites\s+or\s+concurrent:\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^Prerequisite:\s*', '', text, flags=re.IGNORECASE)
        
        # Handle parentheses for grouping
        if '(' in text and ')' in text:
            return self._parse_with_groups(text)
        
        # Split on AND (but not "and concurrent")
        and_parts = self._split_on_and(text)
        
        if len(and_parts) > 1:
            children = []
            for part in and_parts:
                child = self._parse_or_expression(part.strip())
                if child:
                    children.append(child)
            
            if len(children) == 1:
                return children[0]
            elif children:
                return {"type": "and", "children": children}
        
        # No AND found, try OR
        return self._parse_or_expression(text)
    
    def _split_on_and(self, text: str) -> List[str]:
        """Split text on 'and' but not 'and concurrent'"""
        # Replace "and concurrent" temporarily
        text = re.sub(r'\band\s+concurrent\b', '~~~CONCURRENT~~~', text, flags=re.IGNORECASE)
        
        # Split on remaining 'and'
        parts = re.split(r'\s+and\s+', text, flags=re.IGNORECASE)
        
        # Restore "and concurrent"
        parts = [p.replace('~~~CONCURRENT~~~', 'and concurrent') for p in parts]
        
        return parts
    
    def _parse_or_expression(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse an OR expression"""
        if not text:
            return None
        
        # Split on OR
        or_parts = re.split(r'\s+or\s+', text, flags=re.IGNORECASE)
        
        if len(or_parts) > 1:
            children = []
            for part in or_parts:
                child = self._parse_atomic(part.strip())
                if child:
                    children.append(child)
            
            if len(children) == 1:
                return children[0]
            elif children:
                return {"type": "or", "children": children}
        
        # No OR found, parse as atomic
        return self._parse_atomic(text)
    
    def _parse_atomic(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse an atomic expression (course or text condition)"""
        if not text:
            return None
        
        text = text.strip(' ,.')
        
        # Check for "(or concurrent)" modifier
        is_concurrent = False
        concurrent_match = re.search(r'\(\s*or\s+concurrent\s*\)', text, re.IGNORECASE)
        if concurrent_match:
            is_concurrent = True
            text = text[:concurrent_match.start()].strip() + text[concurrent_match.end():].strip()
        
        # Try to find a course code
        course_match = re.search(self.COURSE_PATTERN, text)
        
        if course_match:
            course_code = course_match.group(0).replace(" ", "")
            return {
                "type": "course",
                "course_code": course_code,
                "is_concurrent": is_concurrent,
                "is_optional": False
            }
        
        # Check if it's a text condition
        text_lower = text.lower()
        
        # Determine category
        category = "other"
        for cat, keywords in self.text_conditions.items():
            for keyword in keywords:
                if keyword in text_lower:
                    category = cat
                    break
        
        # If we found a recognizable condition, return it
        if category != "other" or len(text) > 5:  # Avoid very short non-course strings
            return {
                "type": "text_condition",
                "condition": text,
                "category": category
            }
        
        return None
    
    def _parse_with_groups(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse expression with parenthetical groups"""
        # Find all groups
        groups = []
        group_pattern = r'\([^()]+\)'
        
        # Replace groups with placeholders
        placeholder_map = {}
        counter = 0
        
        def replace_group(match):
            nonlocal counter
            group_text = match.group(0)[1:-1]  # Remove parentheses
            placeholder = f"~~~GROUP{counter}~~~"
            placeholder_map[placeholder] = group_text
            counter += 1
            return placeholder
        
        modified_text = re.sub(group_pattern, replace_group, text)
        
        # Parse the modified text
        result = self._parse_expression(modified_text)
        
        # Replace placeholders back with parsed groups
        result = self._replace_placeholders(result, placeholder_map)
        
        return result
    
    def _replace_placeholders(self, node: Optional[Dict[str, Any]], 
                             placeholder_map: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Replace placeholder groups with actual parsed groups"""
        if node is None:
            return None
        
        node_type = node.get("type")
        
        if node_type == "course":
            # Check if course_code is a placeholder
            if node["course_code"].startswith("~~~GROUP"):
                placeholder = node["course_code"]
                if placeholder in placeholder_map:
                    group_text = placeholder_map[placeholder]
                    group_node = self._parse_expression(group_text)
                    return {"type": "group", "expression": group_node}
            return node
        
        elif node_type in ["and", "or"]:
            new_children = []
            for child in node.get("children", []):
                new_child = self._replace_placeholders(child, placeholder_map)
                if new_child:
                    new_children.append(new_child)
            node["children"] = new_children
            return node
        
        elif node_type == "group":
            node["expression"] = self._replace_placeholders(node.get("expression"), placeholder_map)
            return node
        
        return node


def main():
    """Main function to parse all courses"""
    
    # File paths
    input_file = Path("all_courses.json")
    backup_file = Path("all_courses.json.backup")
    
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