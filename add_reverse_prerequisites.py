"""
Add "is_prerequisite_for" Field to Courses

This script:
1. Reads all_courses.json (with prerequisite_ast field)
2. Analyzes which courses are prerequisites for which other courses
3. Adds "is_prerequisite_for" field to each course
4. Outputs final_all_courses.json

Example:
    If CSCE 1001 is a prerequisite for CSCE 1101, CSCE 2303, etc.
    Then CSCE 1001 gets:
    "is_prerequisite_for": ["CSCE 1101", "CSCE 2303", ...]
"""

import json
from pathlib import Path
from typing import Set, Dict, List


def extract_course_code_from_title(title: str) -> str:
    """
    Extract course code from title.
    Example: "CSCE 1101 - Fundamentals..." -> "CSCE1101"
    """
    import re
    match = re.search(r'([A-Z]{4})\s*(\d{4})', title)
    if match:
        return match.group(1) + match.group(2)
    return ""


def get_all_prerequisite_courses(node, include_corequisites=False) -> Set[str]:
    """
    Extract all course codes from an AST node.
    
    Args:
        node: AST node (dict)
        include_corequisites: Whether to include courses from corequisite nodes
    
    Returns:
        Set of course codes
    """
    if node is None:
        return set()
    
    courses = set()
    node_type = node.get("type")
    
    if node_type == "course":
        courses.add(node.get("course_code", ""))
    
    elif node_type in ["and", "or"]:
        for child in node.get("children", []):
            courses.update(get_all_prerequisite_courses(child, include_corequisites))
    
    elif node_type == "group":
        courses.update(get_all_prerequisite_courses(node.get("expression"), include_corequisites))
    
    elif node_type == "concurrent":
        if include_corequisites:
            course_node = node.get("course")
            if course_node:
                courses.update(get_all_prerequisite_courses(course_node, include_corequisites))
    
    # text_condition nodes don't contribute courses
    
    return courses


def build_reverse_prerequisite_map(courses: List[Dict]) -> Dict[str, Set[str]]:
    """
    Build a reverse mapping: course_code -> list of courses that require it.
    
    Args:
        courses: List of course dictionaries with prerequisite_ast
    
    Returns:
        Dictionary mapping course codes to sets of courses that require them
    """
    reverse_map = {}
    
    for course in courses:
        # Get this course's code
        course_code = extract_course_code_from_title(course.get("title", ""))
        if not course_code:
            continue
        
        # Get the prerequisite AST
        ast = course.get("prerequisite_ast", {})
        
        # Extract all prerequisite courses (not corequisites)
        prereq_courses = get_all_prerequisite_courses(ast.get("prerequisites"), include_corequisites=False)
        
        # For each prerequisite, add this course to its "is_prerequisite_for" list
        for prereq_code in prereq_courses:
            if prereq_code:  # Skip empty strings
                if prereq_code not in reverse_map:
                    reverse_map[prereq_code] = set()
                reverse_map[prereq_code].add(course_code)
    
    return reverse_map


def build_reverse_corequisite_map(courses: List[Dict]) -> Dict[str, Set[str]]:
    """
    Build a reverse mapping for corequisites: course_code -> list of courses that need it concurrently.
    
    Args:
        courses: List of course dictionaries with prerequisite_ast
    
    Returns:
        Dictionary mapping course codes to sets of courses that need them as corequisites
    """
    reverse_map = {}
    
    for course in courses:
        # Get this course's code
        course_code = extract_course_code_from_title(course.get("title", ""))
        if not course_code:
            continue
        
        # Get the prerequisite AST
        ast = course.get("prerequisite_ast", {})
        
        # Extract all corequisite courses
        coreq_courses = get_all_prerequisite_courses(ast.get("corequisites"), include_corequisites=True)
        
        # For each corequisite, add this course to its "is_corequisite_for" list
        for coreq_code in coreq_courses:
            if coreq_code:  # Skip empty strings
                if coreq_code not in reverse_map:
                    reverse_map[coreq_code] = set()
                reverse_map[coreq_code].add(course_code)
    
    return reverse_map


def main():
    """Main function to add is_prerequisite_for field"""
    
    # File paths
    input_file = Path("all_courses.json")
    output_file = Path("final_all_courses.json")
    
    # Check if input file exists
    if not input_file.exists():
        print(f"❌ Error: {input_file} not found in current directory")
        print(f"   Current directory: {Path.cwd()}")
        print(f"\n💡 Make sure you've run parse_all_courses.py first!")
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
    
    # Check if courses have prerequisite_ast field
    courses_with_ast = sum(1 for c in courses if "prerequisite_ast" in c)
    if courses_with_ast == 0:
        print(f"⚠️  Warning: No courses have 'prerequisite_ast' field!")
        print(f"   Did you run parse_all_courses.py first?")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    else:
        print(f"✅ Found {courses_with_ast} courses with prerequisite_ast")
    
    # Build reverse mappings
    print(f"\n🔄 Building reverse prerequisite mappings...")
    prereq_reverse_map = build_reverse_prerequisite_map(courses)
    
    print(f"🔄 Building reverse corequisite mappings...")
    coreq_reverse_map = build_reverse_corequisite_map(courses)
    
    print(f"✅ Built mappings for {len(prereq_reverse_map)} courses with prerequisites")
    print(f"✅ Built mappings for {len(coreq_reverse_map)} courses with corequisites")
    
    # Add the reverse mapping to each course
    print(f"\n🔄 Adding is_prerequisite_for and is_corequisite_for fields...")
    
    stats = {
        "total": len(courses),
        "with_prereq_for": 0,
        "with_coreq_for": 0,
        "orphans": 0  # Courses that are not prerequisites for anything
    }
    
    enhanced_courses = []
    
    for course in courses:
        # Get course code
        course_code = extract_course_code_from_title(course.get("title", ""))
        
        # Get the list of courses this is a prerequisite for
        is_prerequisite_for = sorted(list(prereq_reverse_map.get(course_code, set())))
        
        # Get the list of courses this is a corequisite for
        is_corequisite_for = sorted(list(coreq_reverse_map.get(course_code, set())))
        
        # Add fields to course
        course["is_prerequisite_for"] = is_prerequisite_for
        course["is_corequisite_for"] = is_corequisite_for
        
        # Update stats
        if is_prerequisite_for:
            stats["with_prereq_for"] += 1
        if is_corequisite_for:
            stats["with_coreq_for"] += 1
        if not is_prerequisite_for and not is_corequisite_for:
            stats["orphans"] += 1
        
        enhanced_courses.append(course)
    
    # Save output
    print(f"\n💾 Writing to {output_file}...")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(enhanced_courses, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error writing output file: {e}")
        return
    
    # Print statistics
    print("\n" + "="*60)
    print("📊 STATISTICS")
    print("="*60)
    print(f"Total courses:                           {stats['total']}")
    print(f"Courses that are prerequisites:          {stats['with_prereq_for']}")
    print(f"Courses that are corequisites:           {stats['with_coreq_for']}")
    print(f"Leaf courses (not required by others):   {stats['orphans']}")
    print("="*60)
    
    # Show examples
    print(f"\n📝 Example courses with is_prerequisite_for:")
    
    # Find courses with the most prerequisites
    courses_by_prereq_count = sorted(
        enhanced_courses,
        key=lambda c: len(c.get("is_prerequisite_for", [])),
        reverse=True
    )
    
    for course in courses_by_prereq_count[:5]:
        prereq_list = course.get("is_prerequisite_for", [])
        if prereq_list:
            course_code = extract_course_code_from_title(course.get("title", ""))
            print(f"\n   {course_code} is a prerequisite for {len(prereq_list)} courses:")
            for prereq in prereq_list[:5]:  # Show first 5
                print(f"      - {prereq}")
            if len(prereq_list) > 5:
                print(f"      ... and {len(prereq_list) - 5} more")
    
    print(f"\n✅ Done! Enhanced courses saved to {output_file}")
    print(f"\n💡 Each course now has:")
    print(f"   - All original fields")
    print(f"   - prerequisite_ast (from previous script)")
    print(f"   - is_prerequisite_for (NEW - courses that require this)")
    print(f"   - is_corequisite_for (NEW - courses that need this concurrently)")
    
    # Show a complete example
    print(f"\n📋 Complete example:")
    example = next((c for c in enhanced_courses if c.get("is_prerequisite_for")), None)
    if example:
        print(f"\n   Course: {example.get('title', 'N/A')}")
        print(f"   Is prerequisite for: {json.dumps(example.get('is_prerequisite_for', []), indent=6)}")
        print(f"   Is corequisite for: {json.dumps(example.get('is_corequisite_for', []), indent=6)}")


if __name__ == "__main__":
    main()