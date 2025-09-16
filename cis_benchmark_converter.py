#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
File : cis_benchmark_converter.py
Author : Maxime Beauchamp
LinkedIn : https://www.linkedin.com/in/maxbeauchamp/ 
Created : 2024-11-06

Description :
This script extracts recommendations from CIS Benchmark PDF documents and exports 
them in CSV or Excel format, facilitating compliance checks and recommendation reviews 
by providing a more accessible format.

Usage :
python cis_benchmark_converter.py -i path/to/input_file.pdf -o path/to/output_file -f [csv|excel]

Arguments :
-i, --input   : Path to the input CIS Benchmark PDF file.
-o, --output  : Path to the output file (defaults to the input file name with .csv or .xlsx extension).

Dependencies :
- pdfplumber : for text extraction from PDF files.
- colorama   : for colored status messages in the terminal.

Installing dependencies :
pip install pdfplumber colorama

Changelog :
- 2025-03-06 : Initial version for converting CIS Benchmarks from PDF to CSV.

References and Resources :
- CIS Benchmarks : https://downloads.cisecurity.org/#/
- pdfplumber documentation : https://pdfplumber.readthedocs.io/
- openpyxl documentation : https://openpyxl.readthedocs.io/
- colorama documentation : https://pypi.org/project/colorama/

License :
This script is provided under the MIT License.
Please respect the copyright of the CIS Benchmarks documents when using and sharing this script.
"""

import csv
import re
import argparse
import pdfplumber
import os
from colorama import Fore, Style, init

# Initialize colorama for Windows
init(autoreset=True)

# Regular expressions for extracting recommendations and cleaning text
recommendation_pattern = re.compile(r'^\s*(\d+(?:\.\d+)+)\s+(.+)')  # Matches numbers like 1.1.1, 2.2.2.2, etc.
remove_pattern = re.compile(r'Page\s\d{1,4}|•')
remove_pattern2 = re.compile(r'\d{1,4}\s*\|\s*P\s*a\s*ge')
#title_pattern = re.compile(r'^([1-9]\d{0,1}\.\d+(?:\.\d+)*)\s*(\(L\d+\))?\s*(.*)')
title_pattern = re.compile(r'^([1-9]\d{0,2}(?:\.\d+){1,7})\s{1,}(\(L\d+\))?\s*(.*)')
category_pattern = re.compile(r'^(\d+)\s+([A-Za-z][A-Za-z\s\-\'\,\(\)\/]+)[\s\.]+\d+\b')
category_in_file_pattern = re.compile(r'^(\d+)\s+([\w+ *]+)[ \n]*\b')

# Pattern to remove page numbers (e.g., "Page 123")
page_number_pattern = re.compile(r'\bPage\s+\d+\b', re.IGNORECASE)

# Old page number pattern (e.g., "123 | P a ge")
old_page_number_pattern = re.compile(r'\d+\s*\|\s*P\s*a\s*ge', re.IGNORECASE)

def remove_page_numbers(text):
    return page_number_pattern.sub('', text)

def remove_old_page_numbers(text):
    return old_page_number_pattern.sub('', text)

# Clean text by removing page numbers
def clean_page_numbers(text):
    text = remove_page_numbers(text)
    text = remove_old_page_numbers(text)
    return text

# Sections to extract
sections = [
    'Profile Applicability:',
    'Description:',
    'Rationale:',
    'Impact:',
    'Audit:',
    'Remediation:',
    'Default Value:',
    'References:',
    #'Additional Information:'
]

categories = {}
recommendation_page = None

def extract_title_and_version(input_file):
    with pdfplumber.open(input_file) as pdf:
        first_page = pdf.pages[0]
        page_text = first_page.extract_text().splitlines()
    title_lines = []
    version = None
    for line in page_text:
        if line.lower().startswith("v") and "-" in line:
            version = line.strip()
            break
        else:
            title_lines.append(line.strip())
    title = " ".join(title_lines) if title_lines else "CIS Benchmark Document"
    return title, version

# Generate a unique filename if the file already exists
def generate_unique_filename(base_name, extension):
    counter = 1
    file_name = f"{base_name}.{extension}"
    while os.path.exists(file_name):
        file_name = f"{base_name}({counter}).{extension}"
        counter += 1
    return file_name

def write_output(recommendations, output_file, input_file):
    log_info(f"Writing output to {output_file}...")
    
    headers = [
        'Category',
        'Subcategory', 
        'Number',
        'Title'
    ] + [sec[:-1] for sec in sections if sec != 'CIS Controls:']
    
    with open(output_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=',')
        writer.writerow(headers)  # Column headers

        for recommendation in recommendations:
            # Extract the actual recommendation data
            rec_number = recommendation.get('Number', '')
            rec_title = recommendation.get('Title', '')
            
            # Create row with proper mapping
            row = [
                '',  # Category - will be filled below
                '',  # Subcategory - will be filled below  
                rec_number,  # Number (e.g., "1.1.1")
                rec_title   # Title
            ]
            
            # Add section content to the row
            for sec in sections:
                if sec != 'CIS Controls:':
                    section_key = sec[:-1]  # Remove the colon
                    content = recommendation.get(section_key, '')
                    # Clean the content
                    content = content.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
                    content = content.replace('\uf0b7 ', '').replace('• ', '')
                    row.append(content)
            
            # Get category and subcategory names
            if rec_number:
                parts = rec_number.split('.')
                category_key = parts[0]  # e.g., "1" for "1.1.1"
                category_name = categories.get(category_key, "Unknown")
                
                # For subcategory, check if there's a two-part number (e.g., "1.1" for "1.1.1")
                if len(parts) >= 3:
                    subcategory_key = '.'.join(parts[:-1])  # e.g., "1.1" for "1.1.1"
                    subcategory_name = categories.get(subcategory_key, "No subcategory")
                else:
                    subcategory_name = "No subcategory"
                
                if category_name == "Unknown":
                    print(f"Unknown category for recommendation {rec_number}: {rec_title}\nCategories : {categories}")
                
                row[0] = category_name
                row[1] = subcategory_name
            
            writer.writerow(row)

    log_info(f"Finished writing {len(recommendations)} recommendations to {output_file}.")

# Logging functions
def log_info(message):
    print(f"\n{Fore.GREEN}[INFO]{Style.RESET_ALL} {message}")

def log_warning(message):
    print(f"\n{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}")

def log_debug(message):
    print(f"\n{Fore.BLUE}[DEBUG]{Style.RESET_ALL} {message}")

def extract_categories(pdf, rec_page_num):
    global categories
    
    for page in pdf.pages[:rec_page_num]:
        page_text = page.extract_text()
        lines = page_text.splitlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Original pattern for single-line categories
            match = category_pattern.match(line)
            if match:
                number, name = match.groups()
                categories[number] = name.strip()
                i += 1
                continue
            
            # Pattern for multi-line categories (like category 9)
            multi_line_match = re.match(r'^(\d+)\s+([A-Za-z].*)$', line)
            if multi_line_match:
                number, name_start = multi_line_match.groups()
                
                # Look ahead to collect the full category name
                full_name = name_start
                j = i + 1
                
                # Continue reading lines until we find dots and a page number
                while j < len(lines):
                    next_line = lines[j].strip()
                    
                    # Check if this line contains the page number pattern (dots followed by number)
                    if re.search(r'\.{3,}.*\d+\s*$', next_line):
                        # Extract any remaining text before the dots
                        text_before_dots = re.sub(r'\s*\.{3,}.*$', '', next_line).strip()
                        if text_before_dots:
                            full_name += " " + text_before_dots
                        break
                    
                    # Check if next line starts with a number (new category/section)
                    elif re.match(r'^\d+[\.\s]', next_line):
                        j -= 1  # Step back since this is a new section
                        break
                    
                    # Otherwise, append this line to the category name
                    else:
                        full_name += " " + next_line
                    
                    j += 1
                
                # Clean up the category name
                full_name = re.sub(r'\s+', ' ', full_name.strip())
                categories[number] = full_name
                i = j + 1
                continue
            
            # Enhanced pattern for subsections like "1.1 Password Policy"
            subsection_match = re.match(r'^(\d+\.\d+)\s+([A-Za-z][^.]*?)(?:\s*\.+.*)?$', line)
            if subsection_match:
                number, name = subsection_match.groups()
                name = re.sub(r'\s*\.+.*$', '', name.strip())
                categories[number] = name
            
            # Pattern for deeper subsections like "18.6.10.1 Peer Name Resolution Protocol"
            deep_subsection_match = re.match(r'^(\d+(?:\.\d+){2,})\s+([A-Za-z][^.]*?)(?:\s*\.+.*)?$', line)
            if deep_subsection_match:
                number, name = deep_subsection_match.groups()
                name = re.sub(r'\s*\.+.*$', '', name.strip())
                categories[number] = name
            
            i += 1
    
    if not categories:
        log_warning("Categories not in the Table of Contents. Extracting from the PDF pages...")
        
        for page in pdf.pages[rec_page_num:]:
            page_text = page.extract_text()
            lines = page_text.splitlines()
            
            for line in lines:
                match = category_in_file_pattern.match(line)
                if match:
                    number, name = match.groups()
                    categories[number] = name.strip()
    
    # Debug: Print all found categories
    log_debug(f"Total categories found: {len(categories)}")

def read_pdf(input_file):
    log_info("Starting to read the PDF file...")
    text = []
    with pdfplumber.open(input_file) as pdf:
        total_pages = len(pdf.pages)
        extraction_started = False
        global recommendation_page
        
        # Start reading from page 5 to skip the table of contents
        for page_number, page in enumerate(pdf.pages[5:], start=6):
            page_text = page.extract_text()
            
            # Display progress 10 by 10
            if page_number % 10 == 0 or page_number == total_pages:
                print(f"\r{Fore.GREEN}[INFO]{Style.RESET_ALL} Processing page {page_number}/{total_pages}...", end="", flush=True)
            
            if not extraction_started:
                if "Recommendations" in page_text and "....." not in page_text and "Recommendation Definitions" not in page_text:
                    extraction_started = True
                    recommendation_page = page_number
                    log_debug("Recommendations section detected. Starting extraction... (This may take a while)")
            
            if extraction_started:
                if "Appendix: Summary Table" in page_text or ("Checklist" in page_text and not any(title_pattern.match(line) for line in page_text.splitlines() if "Checklist" in line)):
                    log_debug("End of Recommendations section reached.")
                    break
                text.append(page_text)
            
        log_debug("Extracting categories of all recommendations...")
        extract_categories(pdf, recommendation_page)

    log_info("Completed reading the PDF file.")
    return '\n'.join(text)

def find_profile_applicability(lines, start_index, max_depth=10):
    """
    Look for 'Profile Applicability:' within a certain depth from the start index.
    Returns True if found within the limit, otherwise False.
    """
    for i in range(start_index + 1, min(start_index + max_depth, len(lines))):
        line = lines[i].strip()
        
        # Check for "Profile Applicability:"
        if line.startswith("Profile Applicability:"):
            return True
        
        # Stop if another title or section is detected
        if title_pattern.match(line) or any(line.startswith(sec) for sec in sections):
            return False
    
    return False

def extract_recommendations(text):
    """
    Extract recommendations while avoiding duplicates and confirming section content.
    """
    recommendations = []
    lines = text.splitlines()
    current_recommendation = {}
    current_index = 0

    while current_index < len(lines):
        line = lines[current_index].strip()
        line = clean_page_numbers(line)  # Remove any page number mentions

        # Utilisation dans le contexte principal
        title_match = title_pattern.match(line)
        if title_match:
            if line.startswith("2.16.840.1.101.3.4.1.2"):
                print(current_recommendation)
                print(lines[current_index])
                print(lines[current_index - 1])
                
            # Utilise find_profile_applicability pour vérifier dynamiquement
            if find_profile_applicability(lines, current_index):
                # Sauvegarde la recommandation précédente
                if current_recommendation:
                    recommendations.append(current_recommendation)
                
                # Initialiser une nouvelle recommandation sans doublons
                current_recommendation = {
                    'Number': title_match.group(1),
                    'Level': title_match.group(2) or '',
                    'Title': title_match.group(3),
                }
                
                # Capture multi-line titles
                while (
                    current_index + 1 < len(lines) and
                    not any(lines[current_index + 1].strip().startswith(sec) for sec in sections) and
                    not title_pattern.match(lines[current_index + 1].strip())
                ):
                    current_index += 1
                    additional_line = lines[current_index].strip()
                    additional_line = clean_page_numbers(additional_line)
                    current_recommendation['Title'] += " " + additional_line

        # Capture sections for the current recommendation
        for section in sections:
            if line.startswith(section):
                content, next_index = extract_section(lines, current_index, section)
                current_recommendation[section[:-1]] = content  # Exclude the colon
                current_index = next_index - 1  # Adjust index after extraction
                break
        
        current_index += 1

    # Final recommendation
    if current_recommendation:
        recommendations.append(current_recommendation)
    
    # Remove duplicates based on recommendation number and title
    unique_recommendations = { (rec['Number'], rec['Title']): rec for rec in recommendations }
    return list(unique_recommendations.values())

def extract_section(lines, start_index, section_name):
    """
    Extract content of a section until encountering another section or title.
    Lines containing "CIS Controls" are excluded.
    """
    content = []
    current_index = start_index + 1
    while current_index < len(lines):
        line = lines[current_index].strip()
        line = clean_page_numbers(line)  # Clean each line of page numbers

        # Stop at new section, title, or "CIS Controls"
        if any(line.startswith(sec) for sec in sections) or title_pattern.match(line) or 'CIS Controls' in line:
            break

        content.append(line)
        current_index += 1
    
    return ' '.join(content).strip(), current_index

# Main function
def main():
    parser = argparse.ArgumentParser(description="Extract and format recommendations from CIS Benchmark PDF")
    parser.add_argument("-i", "--input", required=True, help="Input PDF file")
    parser.add_argument("-o", "--output", help="Output file (default: same as input file name with .csv or .xlsx extension)")
    args = parser.parse_args()
    input_file = args.input
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_file = args.output if args.output else generate_unique_filename(base_name, "csv")
    text = read_pdf(input_file)
    recommendations = extract_recommendations(text)
    write_output(recommendations, output_file, input_file)

if __name__ == "__main__":
    main()
