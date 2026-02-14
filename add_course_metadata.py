#!/usr/bin/env python3
"""
Add course_title, course_code, and difficulty_level fields

This script:
1. Reads final_all_courses.json
2. Extracts course code and title from the "title" field
3. Calculates difficulty level based on first digit of course number
4. Adds three new fields:
   - course_code: e.g., "APLN 5331"
   - course_title: e.g., "Sociolinguistics"
   - difficulty_level: 1-4 (capped at 4)
5. Updates final_all_courses.json

Example:
    "APLN 5331 - Sociolinguistics (3 cr.)"
    →
    course_code: "APLN 5331"
    course_title: "Sociolinguistics"
    difficulty_level: 4 (first digit is 5, capped at 4)
"""

import json
import re
import sys
from pathlib import Path

# Ensure UTF-8 stdout on Windows so emoji and Unicode print correctly
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def parse_title_field(title: str) -> tuple:
    """
    Parse the title field to extract course code and course name.
    
    Args:
        title: Full title like "APLN 5331 - Sociolinguistics (3 cr.)"
    
    Returns:
        tuple: (course_code, course_title)
        Example: ("APLN 5331", "Sociolinguistics")
    """
    # Clean the title - remove extra whitespace
    title = ' '.join(title.split())
    
    # Pattern 1: Cross-listed courses (e.g., "SOC/ANTH 5280 - History and Memory (3 cr.)")
    pattern_crosslisted = r'^([A-Z]{3,4}/[A-Z]{3,4})\s+(\d{4})\s+-\s+(.+?)\s+\(.+\)$'
    match = re.match(pattern_crosslisted, title)
    if match:
        dept = match.group(1)      # e.g., "SOC/ANTH"
        number = match.group(2)    # e.g., "5280"
        name = match.group(3)      # e.g., "History and Memory"
        
        course_code = f"{dept} {number}"
        course_title = name.strip()
        return course_code, course_title
    
    # Pattern 2: Multi-course sequences (e.g., "ALIN 1101-1102-1103-1104 - Elementary...")
    # Take only the FIRST course number (dept can be 3 or 4 letters, e.g. SCI, ALIN)
    pattern_multi = r'^([A-Z]{3,4})\s+([\d-]+)\s+-\s+(.+?)\s+\(.+\)$'
    match = re.match(pattern_multi, title)
    if match:
        dept = match.group(1)           # e.g., "ALIN"
        number_str = match.group(2)     # e.g., "1101-1102-1103-1104"
        name = match.group(3)           # e.g., "Elementary Modern Standard Arabic"
        
        # Extract first number
        first_number = number_str.split('-')[0]  # "1101"
        
        course_code = f"{dept} {first_number}"
        course_title = name.strip()
        return course_code, course_title
    
    # Pattern 3: Lab courses with 'L' suffix (e.g., "ECNG 1501L - Exploring...")
    pattern_lab = r'^([A-Z]{3,4})\s+(\d{4}L)\s+-\s+(.+?)\s+\(.+\)$'
    match = re.match(pattern_lab, title)
    if match:
        dept = match.group(1)      # e.g., "ECNG"
        number = match.group(2)    # e.g., "1501L"
        name = match.group(3)      # e.g., "Exploring Electrical Engineering"
        
        course_code = f"{dept} {number}"
        course_title = name.strip()
        return course_code, course_title
    
    # Pattern 4: Standard format with parentheses (e.g., "APLN 5331 - Sociolinguistics (3 cr.)")
    # Department code can be 3 or 4 letters (LAW, MRS, SOC, SCI vs APLN, THTR, ECNG)
    pattern = r'^([A-Z]{3,4})\s+(\d{4})\s+-\s+(.+?)\s+\(.+\)$'
    match = re.match(pattern, title)
    if match:
        dept = match.group(1)      # e.g., "APLN"
        number = match.group(2)    # e.g., "5331"
        name = match.group(3)      # e.g., "Sociolinguistics"
        
        course_code = f"{dept} {number}"
        course_title = name.strip()
        return course_code, course_title
    
    # Pattern 5: Without parentheses (e.g., "ECNG 5980 - Thesis", "LAW 5286 - Independent Study")
    pattern_no_parens = r'^([A-Z]{3,4})\s+(\d{4})\s+-\s+(.+)$'
    match = re.match(pattern_no_parens, title)
    if match:
        dept = match.group(1)
        number = match.group(2)
        name = match.group(3)
        
        course_code = f"{dept} {number}"
        course_title = name.strip()
        return course_code, course_title
    
    # If no pattern matches, return empty strings
    return "", ""


def calculate_difficulty(course_code: str) -> int:
    """
    Calculate difficulty level based on first digit of course number.
    
    Args:
        course_code: e.g., "APLN 5331", "CSCE 1001", "ELIN 0101", "ECNG 1501L"
    
    Returns:
        int: Difficulty level (1-4, capped at 4)
    
    Examples:
        "CSCE 1001" → 1
        "CSCE 2303" → 2
        "CSCE 3301" → 3
        "CSCE 4301" → 4
        "APLN 5331" → 4 (5 is capped at 4)
        "GRAD 9000" → 4 (9 is capped at 4)
        "ELIN 0101" → 1 (0 defaults to 1)
        "ECNG 1501L" → 1 (lab course, first digit is 1)
    """
    # Extract the course number (digits part, may have 'L' suffix)
    match = re.search(r'\d{4}L?', course_code)
    
    if match:
        course_number = match.group(0)  # e.g., "5331" or "1501L"
        # Remove 'L' if present
        course_number = course_number.rstrip('L')
        first_digit = int(course_number[0])  # e.g., 5
        
        # Handle 0 (treat as level 1)
        if first_digit == 0:
            return 1
        
        # Cap at 4
        difficulty = min(first_digit, 4)
        
        return difficulty
    
    # Default to 1 if we can't extract the number
    return 1


def main():
    """Main function to add course_code, course_title, and difficulty_level fields"""
    
    # File paths
    input_file = Path("final_all_courses.json")
    backup_file = Path("final_all_courses.json.backup")
    
    # Check if input file exists
    if not input_file.exists():
        print(f"❌ Error: {input_file} not found in current directory")
        print(f"   Current directory: {Path.cwd()}")
        print(f"\n💡 Make sure you've run the previous scripts first!")
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
    
    # Process courses
    print(f"\n🔄 Adding course_code, course_title, and difficulty_level fields...")
    
    stats = {
        "total": len(courses),
        "parsed": 0,
        "failed": 0,
        "difficulty_distribution": {1: 0, 2: 0, 3: 0, 4: 0}
    }
    
    updated_courses = []
    
    for i, course in enumerate(courses, 1):
        try:
            # Get the full title
            full_title = course.get("title", "")
            
            # Parse it
            course_code, course_title = parse_title_field(full_title)
            
            if course_code and course_title:
                # Calculate difficulty
                difficulty = calculate_difficulty(course_code)
                
                # Add new fields
                course["course_code"] = course_code
                course["course_title"] = course_title
                course["difficulty_level"] = difficulty
                
                stats["parsed"] += 1
                stats["difficulty_distribution"][difficulty] += 1
            else:
                # Parsing failed - add empty fields
                course["course_code"] = ""
                course["course_title"] = ""
                course["difficulty_level"] = 1
                
                stats["failed"] += 1
                print(f"\n⚠️  Could not parse: {full_title}")
            
            updated_courses.append(course)
            
            # Progress indicator
            if i % 10 == 0 or i == len(courses):
                print(f"   Progress: {i}/{len(courses)} courses processed", end='\r')
        
        except Exception as e:
            print(f"\n⚠️  Error processing course {course.get('title', 'Unknown')}: {e}")
            stats["failed"] += 1
            updated_courses.append(course)
    
    print()  # New line after progress
    
    # Save output
    print(f"\n💾 Updating {input_file}...")
    
    try:
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(updated_courses, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        print(f"⚠️  Your original file is backed up at: {backup_file}")
        return
    
    # Print statistics
    print("\n" + "="*60)
    print("📊 STATISTICS")
    print("="*60)
    print(f"Total courses:                {stats['total']}")
    print(f"Successfully parsed:          {stats['parsed']}")
    print(f"Failed to parse:              {stats['failed']}")
    print("\nDifficulty Distribution:")
    print(f"  Level 1 (Intro):            {stats['difficulty_distribution'][1]}")
    print(f"  Level 2 (Intermediate):     {stats['difficulty_distribution'][2]}")
    print(f"  Level 3 (Advanced):         {stats['difficulty_distribution'][3]}")
    print(f"  Level 4 (Expert/Graduate):  {stats['difficulty_distribution'][4]}")
    print("="*60)
    
    # Show examples
    print(f"\n📝 Example courses with new fields:")
    
    # Show one from each difficulty level
    for level in [1, 2, 3, 4]:
        example = next((c for c in updated_courses 
                       if c.get("difficulty_level") == level), None)
        if example:
            print(f"\n   Difficulty {level}: {example.get('course_code', 'N/A')}")
            print(f"   Full title: {example.get('title', 'N/A')}")
            print(f"   Course code: {example.get('course_code', 'N/A')}")
            print(f"   Course title: {example.get('course_title', 'N/A')}")
            print(f"   Difficulty: {example.get('difficulty_level', 'N/A')}")
    
    print(f"\n✅ Done! {input_file} has been updated")
    print(f"📁 Backup saved to: {backup_file}")
    print(f"\n💡 Each course now has:")
    print(f"   - course_code: e.g., 'CSCE 1001'")
    print(f"   - course_title: e.g., 'Fundamentals of Computing I'")
    print(f"   - difficulty_level: 1-4 (based on course number)")


if __name__ == "__main__":
    main()