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
        
        return {
            "prerequisites": prereq_node,
            "corequisites": concurrent_node,
            "raw_text": raw_text
        }
    
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
        text = re.sub(r'\band\s+concurrent\b', '~~~CONCURRENT~~~', text, flags=re.IGNORECASE)
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
        # Pre-process text to avoid turning specific modifiers into groups
        # Replace "(or concurrent)" with a flat token
        text = re.sub(r'\(\s*or\s+concurrent\s*\)', '__OR_CONCURRENT__', text, flags=re.IGNORECASE)
        
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
    input_file = (Path(__file__).parent / "../data/computer_engineering_courses.json").resolve()
    if not input_file.exists():
        print(f"Error: {input_file} not found")
        return
        
    with open(input_file, 'r', encoding='utf-8') as f:
        courses = json.load(f)
        
    parser = PrerequisiteParser()
    parsed_courses = []
    
    for course in courses:
        prereq_text = course.get("prerequisites", "")
        concurrent_text = course.get("concurrent", "")
        
        ast = parser.parse(prereq_text, concurrent_text)
        course["prerequisite_ast"] = ast
        parsed_courses.append(course)
        
    output_file = (Path(__file__).parent / "../data/parsed_ce_courses.json").resolve()
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(parsed_courses, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully processed {len(courses)} CE courses and saved to {output_file}")
    
    # Print out CSCE 2202 to verify
    for c in parsed_courses:
        if c.get("title", "").startswith("CSCE 2202"):
            print("\nVerification for CSCE 2202:")
            print(json.dumps(c.get("prerequisite_ast"), indent=2))

if __name__ == "__main__":
    main()
