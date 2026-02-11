import requests
from bs4 import BeautifulSoup
import re
import json
import time
import sys
import traceback

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

BASE_URL = "https://catalog.aucegypt.edu/"
PROGRAM_URL = "https://catalog.aucegypt.edu/preview_program.php?catoid=44&poid=8171&returnto=2285"
OUTPUT_FILE = "computer_science_courses.json"

def get_soup(url):
    try:
        response = requests.get(url, verify=False, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def extract_course_details(catoid, coid):
    try:
        url = f"{BASE_URL}preview_course_nopop.php?catoid={catoid}&coid={coid}"
        soup = get_soup(url)
        if not soup:
            return None
        
        course_data = {
            "url": url,
            "title": "",
            "credits": "",
            "description": "",
            "prerequisites": "",
            "concurrent": "",
            "cross_listed": "",
            "hours": "",
            "when_offered": "",
            "repeatable": "",
            "notes": ""
        }

        h1 = soup.find('h1', id='course_preview_title')
        if not h1:
            # Fallback if no h1 found (unlikely)
            content_container = soup.find('td', class_='block_content')
        else:
            course_data['title'] = clean_text(h1.get_text())
            match = re.search(r'\((\d+(?:-\d+)?)\s*cr\.\)', course_data['title'])
            if match:
                course_data['credits'] = match.group(1)
            
            # The content siblings are usually inside the same parent as h1
            content_container = h1.parent

        if not content_container:
            return course_data

        # Cleanup unwanted elements
        # We need to be careful not to delete parts of the container if it's the <body> or something global, 
        # but content_container should be a <p> or <td> specific to the course.
        
        # Safe removal of unwanted elements
        for unwanted in content_container.find_all(['div', 'a', 'script', 'hr'], recursive=False): # Only direct children or careful recursive
             # Actually, help_block etc might be siblings or inside.
             # Let's iterate children and skip unwanted ones instead of deleting, to be safer.
             pass

        # Parse content sections
        current_section = "description_start"
        captured_text = {
            "description_start": [],
            "Prerequisites": [],
            "Concurrent": [],
            "Description": [],
            "When Offered": [],
            "Notes": [],
            "Note": [], 
            "Corequisite": [],
            "Cross-listed": [],
            "Hours": [],
            "Repeatable": []
        }
        
        for child in content_container.children:
            if child is h1:
                continue
            
            if child.name in ['div', 'script', 'hr']:
                 # Check if it's junk
                 classes = child.get('class', [])
                 if 'help_block' in classes or 'print_link' in classes or 'acalog-social-media-links' in classes:
                     continue
                 if child.get_text(strip=True) == "Back to Top":
                     continue
                 # If it's a div with just whitespace, ignore
                 if not child.get_text(strip=True):
                     continue
            
            if child.name == 'a':
                 if 'showCatalogData' not in str(child.get('onclick', '')) and 'preview_course' not in child.get('href', ''):
                      # Likely a utility link
                      if child.get_text(strip=True) in ["Print-Friendly Page (opens a new window)", "Add to Portfolio (opens a new window)", "Back to Top", "HELP"]:
                          continue
            
            if child.name == 'strong':
                header = clean_text(child.get_text()).rstrip(':')
                if "Prerequisite" in header:
                    current_section = "Prerequisites"
                elif "Concurrent" in header:
                    current_section = "Concurrent"
                elif "Description" in header:
                    current_section = "Description"
                elif "When Offered" in header:
                    current_section = "When Offered"
                elif "Note" in header or "Notes" in header:
                    current_section = "Notes"
                elif "Corequisite" in header:
                    current_section = "Corequisite"
                elif "Cross-listed" in header or "Cross listed" in header:
                    current_section = "Cross-listed"
                elif "Hour" in header:
                    current_section = "Hours"
                elif "Repeatable" in header:
                    current_section = "Repeatable"
                else:
                    # Treat as part of text if not a known header?
                    # Or capture as new section
                    pass 
                # Don't append the header itself to the text
                continue
                
            if child.name == 'br':
                if current_section in captured_text:
                    captured_text[current_section].append("\n")
                continue
                
            if isinstance(child, str) or child.name is None:
                text = str(child)
                if text.strip() and current_section in captured_text:
                    captured_text[current_section].append(text.strip())
            elif child.name == 'a':
                if current_section in captured_text:
                    captured_text[current_section].append(child.get_text())
            elif child.name == 'div' and child.get('style') == 'display: inline':
                 # Sometimes links are wrapped in div style="display: inline"
                 if current_section in captured_text:
                    captured_text[current_section].append(child.get_text())

        course_data['description'] = "\n".join(captured_text.get("Description", [])).strip()
        if not course_data['description'] and captured_text.get("description_start"):
             course_data['description'] = "\n".join(captured_text["description_start"]).strip()
        
        # Clean up descriptions that have "Same as" / "same as" text accidentally embedded
        # (this happens when the cross-listed info is not in a proper <strong> section)
        desc = course_data['description']
        same_as_match = re.search(r'\n*\s*[Ss]ame\s+as\s*\n', desc)
        if same_as_match:
            before = desc[:same_as_match.start()].strip()
            after = desc[same_as_match.end():].strip()
            course_data['description'] = before
            if after and not course_data.get('cross_listed'):
                course_data['cross_listed'] = "same as " + after
             
        course_data['prerequisites'] = " ".join(captured_text.get("Prerequisites", [])).strip()
        course_data['concurrent'] = " ".join(captured_text.get("Concurrent", [])).strip()
        course_data['cross_listed'] = " ".join(captured_text.get("Cross-listed", [])).strip() or course_data['cross_listed']
        course_data['hours'] = " ".join(captured_text.get("Hours", [])).strip().lstrip('.')
        course_data['when_offered'] = " ".join(captured_text.get("When Offered", [])).strip()
        course_data['repeatable'] = " ".join(captured_text.get("Repeatable", [])).strip()
        course_data['notes'] = " ".join(captured_text.get("Notes", [])).strip()
        if captured_text.get("Note"):
             course_data['notes'] += " " + " ".join(captured_text["Note"]).strip()

        return course_data
    except Exception:
        print(f"\nError extracting details for {catoid}-{coid}:")
        traceback.print_exc()
        return None

def main():
    print(f"Fetching program page: {PROGRAM_URL}")
    soup = get_soup(PROGRAM_URL)
    if not soup:
        print("Failed to fetch program page.")
        return

    course_links = []
    
    onclick_pattern = re.compile(r"showCourse\(['\"](\d+)['\"]\s*,\s*['\"](\d+)['\"]")
    links = soup.find_all('a')
    print(f"Scanning {len(links)} links...")
    
    unique_ids = set()

    for a in links:
        catoid = None
        coid = None
        
        onclick = a.get('onclick', '')
        if onclick and 'showCourse' in onclick:
            match = onclick_pattern.search(onclick)
            if match:
                catoid = match.group(1)
                coid = match.group(2)
        elif 'href' in a.attrs and 'preview_course' in a['href']:
             href = a['href']
             c_match = re.search(r"catoid=(\d+)", href)
             co_match = re.search(r"coid=(\d+)", href)
             if c_match and co_match:
                 catoid = c_match.group(1)
                 coid = co_match.group(1)

        if catoid and coid:
            key = (catoid, coid)
            if key not in unique_ids:
                unique_ids.add(key)
                course_links.append(key)

    print(f"Found {len(course_links)} unique courses.")
    sorted_links = sorted(course_links)

    all_courses = []
    for i, (catoid, coid) in enumerate(sorted_links):
        sys.stdout.write(f"\rfetching {i+1}/{len(sorted_links)}: {catoid}-{coid}")
        sys.stdout.flush()
        
        details = extract_course_details(catoid, coid)
        if details:
            all_courses.append(details)
        time.sleep(0.1) 

    print(f"\nScraping complete. Saving {len(all_courses)} courses to {OUTPUT_FILE}.")
    
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_courses, f, indent=4, ensure_ascii=False)
        print("Done.")
    except Exception as e:
        print(f"\nError saving file: {e}")

if __name__ == "__main__":
    main()
