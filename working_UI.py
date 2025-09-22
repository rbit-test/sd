import os
import requests
import asyncio
import aiohttp
import async_timeout
import time
import csv
import base64
from dotenv import load_dotenv
import sys
"""

Script Function:
1. Asks user for a search query
2. Asks user for a file type (e.g., .py, .js)
3. Asks user for number of results
4. Asks user to search on prem instance of github or github cloud
5. Asks if user wants to search within an organization or outside
6. Searches GitHub code for the given pattern, file type, and organization scope
7. Print the total occurrences found
8. Concurrently fetches the raw content of top files and saves lines containing the pattern in a CSV file 
"""
OUTPUT_FOLDER = "output"
DEBUG_FOLDER = "debug"
"""
Below is the code for constants and configurations used in the main script.
"""
SEARCH_PER_PAGE = 100            # Max items per page for search API
MAX_SEARCH_RESULTS = 100         # Max search results to fetch
RETRY_DELAY_INITIAL = 2          # Initial retry delay for secondary rate limits (seconds)
# Proxies to be used when Searching Outside Organization
PROXIES = {
    # HTTP proxy
    "http": "http://your_http_proxy:port",
    # HTTPS proxy
    "https": "http://your_https_proxy:port",
}
# Github Search API URL
API_ENDPOINTS = {
    "cloud": "https://api.github.com/search/code",
    "on_prem": "https://api.github.com/search/code" # Change to your on-premise instance URL if different
}

# Predefined File Types
# Predefined File Types for GitHub Search API
FILE_TYPES = {
    "0"  : "Across All File Types",

    # Programming Languages
    "1"  : ".py",        # Python
    "2"  : ".js",        # JavaScript
    "3"  : ".ts",        # TypeScript
    "4"  : ".java",      # Java
    "5"  : ".go",        # Go
    "6"  : ".rb",        # Ruby
    "7"  : ".php",       # PHP
    "8"  : ".cpp",       # C++
    "9"  : ".c",         # C
    "10" : ".cs",        # C#
    "11" : ".swift",     # Swift
    "12" : ".kt",        # Kotlin
    "13" : ".rs",        # Rust
    "14" : ".scala",     # Scala
    "15" : ".sh",        # Shell / Bash
    "16" : ".pl",        # Perl
    "17" : ".lua",       # Lua

    # Markup & Styles
    "20" : ".html",
    "21" : ".htm",
    "22" : ".css",
    "23" : ".scss",
    "24" : ".md",        # Markdown
    "25" : ".rst",       # reStructuredText
    "26" : ".xml",

    # Data & Config
    "30" : ".json",
    "31" : ".yaml",
    "32" : ".yml",
    "33" : ".toml",
    "34" : ".ini",
    "35" : ".config",
    "36" : ".conf",
    "37" : ".properties",
    "38" : ".env",

    # Build & Package
    "40" : ".gradle",
    "41" : ".pom",       # Maven POM
    "42" : ".lock",      # Lock files (npm, pipenv, etc.)
    "43" : ".dockerfile",
    "44" : ".makefile",
    "45" : ".cmake",

    # Scripts & Misc
    "50" : ".bat",
    "51" : ".ps1",       # PowerShell
    "52" : ".sql",
    "53" : ".ipynb",     # Jupyter Notebook
    "54" : ".tex",       # LaTeX
}

# Organization List
ORGANIZATIONS = ["ethereum", "Bitbox-Connect", "seopanel"]
# Load .env file in current directory
load_dotenv()

def print_banner():
    """Display a welcome banner for the script."""
    print("=" * 70)
    print("🔍 GITHUB CODE SEARCH AUTOMATION TOOL 🔍")
    print("=" * 70)
    print("📋 Features:")
    print("   • Search across GitHub Cloud or On-Premise instances")
    print("   • Support for multiple file types and custom extensions")
    print("   • Organization-scoped searches")
    print("   • Export results to organized CSV files")
    print("   • Generate detailed search summaries")
    print("=" * 70)
    print()

def print_progress_bar(current, total, length=40):
    """Display a progress bar."""
    if total == 0:
        return
    percent = current / total
    filled = int(length * percent)
    bar = "█" * filled + "-" * (length - filled)
    print(f"\r📊 Progress: [{bar}] {percent:.1%} ({current}/{total})", end="", flush=True)

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def pause_for_user():
    """Pause and wait for user input."""
    input("\n👆 Press Enter to continue...")

def print_section_header(title):
    """Print a formatted section header."""
    print(f"\n📌 {title}")
    print("-" * (len(title) + 4))

def print_success(message):
    """Print a success message with green formatting."""
    print(f"✅ {message}")

def print_error(message):
    """Print an error message with red formatting."""
    print(f"❌ {message}")

def print_warning(message):
    """Print a warning message with yellow formatting."""
    print(f"⚠️  {message}")

def print_info(message):
    """Print an info message with blue formatting."""
    print(f"ℹ️  {message}")

def display_file_types_menu():
    """Display file types in a formatted menu."""
    print("\n📂 Available File Types:")
    print("┌" + "─" * 68 + "┐")
    
    # Group file types by category
    categories = {
        "Programming Languages": [str(i) for i in range(1, 18)],
        "Markup & Styles": [str(i) for i in range(20, 27)],
        "Data & Config": [str(i) for i in range(30, 39)],
        "Build & Package": [str(i) for i in range(40, 46)],
        "Scripts & Misc": [str(i) for i in range(50, 55)]
    }
    
    for category, keys in categories.items():
        print(f"│ {category:20} │")
        for i in range(0, len(keys), 3):
            row = keys[i:i+3]
            line = "│ "
            for key in row:
                if key in FILE_TYPES:
                    line += f"{key:>2}: {FILE_TYPES[key]:<15} "
            line += " " * (66 - len(line)) + "│"
            print(line)
        print("├" + "─" * 68 + "┤")
    
    print(f"│ {'0: Across All File Types':^66} │")
    print("└" + "─" * 68 + "┘")

def get_user_choice(prompt, valid_choices, allow_multiple=False):
    """Get and validate user choice with enhanced UI."""
    while True:
        try:
            choice = input(f"🔹 {prompt}: ").strip()
            if choice.lower() == 'exit':
                print_info("Exit requested. Thank you for using GitHub Search Tool!")
                sys.exit(0)
            
            if not choice:
                print_error("Input cannot be empty. Please try again or type 'exit' to quit.")
                continue
            
            if allow_multiple:
                choices = [c.strip() for c in choice.split(",")]
                if all(c in valid_choices for c in choices):
                    return choices
                print_error("Invalid choice(s). Please select from the available options.")
            else:
                if choice in valid_choices:
                    return choice
                print_error("Invalid choice. Please select a valid option.")
        except KeyboardInterrupt:
            print_info("\n\nOperation cancelled by user. Goodbye!")
            sys.exit(0)
# This function will handle all the required inputs and error handling for inputs
def ask_required(prompt : str, label : str) -> str:
    # Keep asking with a custom prompt until a non-empty input is received
    while True:
        try:
            user_input = input(f"🔹 {prompt}: ").strip()
            if user_input.lower() == 'exit':
                print_info("Exit requested. Thank you for using GitHub Search Tool!")
                sys.exit(0)
            if user_input:
                return user_input
            print_error(f"{label} is required. Please provide a valid {label} or type 'exit' to quit.")
        except KeyboardInterrupt:
            print_info("\n\nOperation cancelled by user. Goodbye!")
            sys.exit(0)

# This function will handle all the console input from the user
def get_user_input():
    print_section_header("GitHub Token Configuration")
    
    # check for token in the .env file in current directory
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print_warning("No GitHub token found in environment variables.")
        token = ask_required("Enter your GitHub Personal Access Token", "GitHub Token")
        # Ask user to save token in env variable for future use
        save_choice = get_user_choice("Save this token in .env file for future use? (y/n)", ['y', 'n'])
        if save_choice == 'y':
            try:
                with open(".env", "w") as f:
                    f.write(f"GITHUB_TOKEN={token}\n")
                print_success("Token saved in .env file for future use.")
            except Exception as e:
                print_error(f"Failed to save token: {e}")
    else:
        print_success(f"Using GitHub token from .env file: {token[:4]}****{token[-4:]}")
    
    print_section_header("Search Configuration")
    
    pattern = ask_required("Enter the code pattern to search for (e.g., 'secret_key =', 'password')", "Search Pattern")
    print_info(f"Search pattern set to: '{pattern}'")
    
    # Get result limit with validation
    while True:
        try:
            result_limit = ask_required("Enter the number of results to fetch (1-1000)", "Number of Results")
            result_limit = int(result_limit)
            if 1 <= result_limit <= 1000:
                break
            print_error("Please enter a number between 1 and 1000.")
        except ValueError:
            print_error("Please enter a valid number.")
    
    print_success(f"Result limit set to: {result_limit}")
    
    print_section_header("File Type Selection")
    
    # Display file types menu
    display_file_types_menu()
    
    valid_choices = set(FILE_TYPES.keys())
    
    print_info("You can select multiple file types by separating them with commas (e.g., 1,2,3)")
    choices = get_user_choice("Your choice (e.g., 1,3,5 or 0 for all types)", valid_choices, allow_multiple=True)
    
    if "0" in choices:
        file_type = ""  # Search across all file types
        print_success("Selected: All file types")
    else:
        # remove duplicates and join with space
        file_type = " ".join(set(FILE_TYPES[choice] for choice in choices))
        selected_types = [FILE_TYPES[choice] for choice in choices]
        print_success(f"Selected file types: {', '.join(selected_types)}")
    
    # Enter custom extensions
    print_info("You can also add custom file extensions if needed.")
    custom_ext = input("🔹 Enter custom file extensions (comma-separated, e.g., .custom,.ext) or press Enter to skip: ").strip()
    
    if custom_ext:
        # Normalize custom extensions by stripping leading '.'
        custom_exts = [ext.strip().lstrip('.') for ext in custom_ext.split(",") if ext.strip().startswith(".")]
        if custom_exts:
            if file_type:
                file_type += " " + " ".join(custom_exts)
            else:
                file_type = " ".join(custom_exts)
            print_success(f"Added custom extensions: {', '.join(['.' + ext for ext in custom_exts])}")
    
    pause_for_user()
    return token, pattern, result_limit, file_type
# function to handle github instance selection and organization scope
def get_github_instance():
    print_section_header("GitHub Instance Selection")
    
    print("🏢 Available GitHub Instances:")
    print("┌────────────────────────────────────────────────────────────┐")
    print("│  1. GitHub Cloud (https://github.com)                     │")
    print("│  2. GitHub On-Premise Instance                            │")
    print("└────────────────────────────────────────────────────────────┘")
    
    instance_choice = get_user_choice("Select GitHub instance (1 or 2)", ['1', '2'])
    github_instance = "cloud" if instance_choice == '1' else "on_prem"
    
    if github_instance == "cloud":
        print_success("Selected: GitHub Cloud")
        print_info(f"Search will be performed within organizations: {', '.join(ORGANIZATIONS)}")
        repo_scope = "2"  # default to all repos including user repos
        pause_for_user()
    else:
        print_success("Selected: GitHub On-Premise")
        print_section_header("Repository Scope Selection")
        
        print("📁 Repository Scope Options:")
        print("┌────────────────────────────────────────────────────────────┐")
        print("│  1. Organization Repositories only                        │")
        print("│  2. All Repositories (including User Repositories)       │")
        print("└────────────────────────────────────────────────────────────┘")
        
        repo_scope = get_user_choice("Select repository scope (1 or 2)", ['1', '2'])
        
        if repo_scope == '1':
            print_success("Selected: Organization repositories only")
            print_info("Search will be performed within all organization repositories.")
        else:
            print_success("Selected: All repositories")
            print_info("Search will be performed across all repositories including user repositories.")
        
        pause_for_user()
    
    return github_instance, repo_scope


    
# Build the search query with exact matching
def build_search_query(pattern: str, file_type: str = None) -> str:
    """
    Build a GitHub code search query with exact matching.
    
    Args:
        pattern (str): The search string (e.g., 'secret =', 'password.equals(').
        file_type (str, optional): Space-separated list of file extensions (e.g., 'py js java').

    Returns:
        str: The full GitHub search query string.
    """
    # Wrap the pattern in quotes for exact match
    query = f"\"{pattern}\" in:file"

    if file_type:
        # Add multiple extension filters (no OR/parentheses in REST API)
        types = file_type.split()
        type_query = " ".join(f"extension:{t.lstrip('.')}" for t in types)
        query += f" {type_query}"

    return query



# Github Search
async def search_github_code(session, api_url, query, max_results=MAX_SEARCH_RESULTS, repo_scope=None):
    """Search GitHub code API and return a list of file objects."""
    all_files = []
    page = 1
    while len(all_files) < max_results:
        params = {
            'q': query,
            'per_page': min(SEARCH_PER_PAGE, max_results - len(all_files)),
            'page': page
        }
        async with session.get(api_url, params=params) as resp:
            if resp.status == 403:  # changed from resp.status_code
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset - int(time.time()), RETRY_DELAY_INITIAL)
                print(f"Search API rate limit hit, waiting {wait}s")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            # save response in a json file for debugging
            # with open(f"debug_response_page_{page}.json", "w", encoding="utf-8") as f:
            #     f.write(await resp.text())
            data = await resp.json()  # make sure to await
            items = data.get('items', [])
            if not items:
                break
            # If repo_scope is '1', only add to list if  repository.owner.type is 'Organization' else append all
            if repo_scope == '1':
                org_items = [item for item in items if item.get("repository", {}).get("owner", {}).get("type") == "Organization"]
                all_files.extend(org_items)
            else:
                all_files.extend(items)
            if len(items) < params['per_page']:
                break
            page += 1
    return all_files, data.get('total_count', 0)


# Main async flow
async def main():
    # Clear screen and show banner
    clear_screen()
    print_banner()
    
    # Step 1: Get user inputs
    # check if output folder exists if not create it
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    # check if debug folder exists if not create it
    # os.makedirs(DEBUG_FOLDER, exist_ok=True)
    
    try:
        token, pattern, max_results, file_type = get_user_input()
        instance, repo_scope = get_github_instance()
        
        clear_screen()
        print_section_header("Search Execution")
        
        query = build_search_query(pattern, file_type)
        api_url = API_ENDPOINTS[instance]

        print(f"🔍 Searching for '{pattern}' in '{file_type or 'All'}' files...")
        print_info(f"GitHub Instance: {'Cloud' if instance == 'cloud' else 'On-Premise'}")
        print_info(f"Maximum Results: {max_results}")
        
        # file_name is pattern_name without spaces and special chars + timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_pattern = "".join(c if c.isalnum() else "_" for c in pattern)[:20]
        file_name = f"{safe_pattern}_{instance}_{timestamp}"
        # create folder inside output folder with safe_pattern name
        pattern_folder = os.path.join(OUTPUT_FOLDER, file_name)
        os.makedirs(pattern_folder, exist_ok=True)
        print_success(f"Output folder created: {pattern_folder}")
        
        # DS for storing multiple results when calling multiple times due to repo scope filtering
        results = []
        
        if instance == "cloud":
            print_info(f"Searching across {len(ORGANIZATIONS)} organizations...")
            total_orgs = len(ORGANIZATIONS)
            
            # perform search for each organization and aggregate results
            for idx, org in enumerate(ORGANIZATIONS):
                org_query = f"{query} org:{org}"
                print(f"\n🔎 Searching in organization: {org}")
                print_progress_bar(idx, total_orgs)
                
                async with aiohttp.ClientSession(headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3.text-match+json"
                }) as session:
                    org_results, total_count = await search_github_code(
                        session, api_url, org_query, max_results, repo_scope
                    )
                    results.extend(org_results)
                    
                    # Append total_count from each org to Search_Summary.txt in pattern_folder
                    summary_file = os.path.join(pattern_folder, "Search_Summary.txt")
                    try:
                        with open(summary_file, "a", encoding="utf-8") as f:
                            f.write(f"Organization: {org}, Occurrences Found: {total_count}\n")
                        print(f" - Found {total_count} occurrences")
                    except Exception as e:
                        print_error(f"Error saving summary for {org}: {e}")
            
            print_progress_bar(total_orgs, total_orgs)
            print()  # New line after progress bar
            
            # write other details to Search_Summary.txt
            try:
                with open(summary_file, "a", encoding="utf-8") as f:
                    f.write(f"\nSearch Configuration:\n")
                    f.write(f"Search Pattern: {pattern}\n")
                    f.write(f"File Types: {file_type or 'All'}\n")
                    f.write(f"GitHub Instance: {instance} ({'GitHub Cloud' if instance == 'cloud' else 'GitHub On-Premise'})\n")
                    scope_desc = "Organization Repositories only"
                    f.write(f"Repository Scope: {scope_desc}\n")
                    f.write(f"Total Results Fetched: {len(results)}\n")
                print_success(f"Search summary saved to {summary_file}")
            except Exception as e:
                print_error(f"Error saving search summary: {e}")
        else:
            print_info("Performing On-Premise search...")
            # On-Prem instance, perform single search with or without repo scope filtering
            async with aiohttp.ClientSession(headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3.text-match+json"
            }) as session:
                results, total_count = await search_github_code(
                    session, api_url, query, max_results, repo_scope
                )
            
            print_success(f"Total occurrences of '{pattern}' found: {total_count}")
            print_info(f"Fetched {len(results)} detailed results")
            
            # create a Search Summary.txt with pattern, file types selected, instance type, repo scope and total_count and save in pattern_folder
            summary_file = os.path.join(pattern_folder, "Search_Summary.txt")
            try:
                with open(summary_file, "w", encoding="utf-8") as f:
                    f.write(f"GitHub Search Automation - Results Summary\n")
                    f.write(f"=" * 50 + "\n\n")
                    f.write(f"Search Configuration:\n")
                    f.write(f"Search Pattern: {pattern}\n")
                    f.write(f"File Types: {file_type or 'All'}\n")
                    f.write(f"GitHub Instance: {instance} ({'GitHub Cloud' if instance == 'cloud' else 'GitHub On-Premise'})\n")
                    scope_desc = "Organization Repositories only" if repo_scope == '1' else "All Repositories including User Repositories"
                    f.write(f"Repository Scope: {scope_desc}\n")
                    f.write(f"Total Occurrences Found: {total_count}\n")
                    f.write(f"Results Fetched: {len(results)}\n")
                    f.write(f"Timestamp: {timestamp}\n")
                print_success(f"Search summary saved to {summary_file}")
            except Exception as e:
                print_error(f"Error saving search summary: {e}")
                
        print_section_header("Processing Results")
        print_info(f"Processing {len(results)} search results...")
        
        # Step 4: Define columns including fragments from text_matches
        gh_code_search_columns = [
            "html_url",
            "name",                   # File name
            "path",                   # File path
            "repository.fork",        # Whether repo is a fork
            "repository.html_url",    # Repository URL
            "repository.name",        # Repository name
            "repository.owner.type",  # Owner type (User/Organization)
            "repository.owner.login",
            "fragment"                # Code snippet fragment
        ]

        # Step 5: Extract fragments into each item for CSV
        for item in results:
            # Join all fragments if multiple text_matches exist
            fragments = []
            for tm in item.get("text_matches", []):
                fragment_text = tm.get("fragment")
                if fragment_text:
                    fragments.append(fragment_text.replace("\r", "").strip())
            item["fragment"] = "\n---\n".join(fragments)  # separate multiple matches by --- 
            
        fragments_file = os.path.join(pattern_folder, f"{file_name}_fragments.csv")
        pattern_lines_file = os.path.join(pattern_folder, f"{file_name}_pattern_lines.csv")
        
        # Step 6: Save results to CSV (robust)
        save_results_to_csv(results, gh_code_search_columns, fragments_file)
        
        # Step 7: Filter fragments by pattern and save to new CSV (robust)
        filter_fragments_by_pattern(fragments_file, pattern_lines_file, pattern)
        
        # Final summary
        print_section_header("Search Complete!")
        print_success(f"All files saved in: {pattern_folder}")
        print_info("Generated files:")
        print(f"   📄 Search_Summary.txt - Detailed search configuration and results")
        print(f"   📊 {file_name}_fragments.csv - Complete search results with code fragments")
        print(f"   🎯 {file_name}_pattern_lines.csv - Filtered lines containing the search pattern")
        
        print("\n" + "=" * 70)
        print("🎉 Thank you for using GitHub Search Automation Tool! 🎉")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print_info("\n\nOperation cancelled by user. Goodbye!")
    except Exception as e:
        print_error(f"An unexpected error occurred: {e}")
        print_info("Please check your configuration and try again.")


def extract_pattern_lines_from_fragment(fragment, pattern):
    """Extract lines containing the pattern from a code fragment."""
    matching_lines = []
    # write best way to extract lines containing the pattern in any case (upper/lower/mixed)
    for line in fragment.splitlines():
        if pattern.lower() in line.lower():
            matching_lines.append(line.strip())
    return matching_lines

# load the fragments csv and create a new csv using save_results_to_csv() only with lines containing the pattern
def filter_fragments_by_pattern(input_file, output_file, pattern):
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames if reader.fieldnames else []
            output_rows = []
            for row in reader:
                fragment = row.get("fragment", "")
                for line in extract_pattern_lines_from_fragment(fragment, pattern):
                    # Copy all columns from input, add matching_line
                    new_row = [row.get(col, "") for col in fieldnames] + [line]
                    output_rows.append(new_row)
    except Exception as e:
        print_error(f"Error reading fragments file: {e}")
        fieldnames = []
        output_rows = []
    # Always attempt to save output file, even if no matches
    try:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames + ["matching_line"])
            writer.writerows(output_rows)
        print_success(f"Pattern lines saved to {os.path.basename(output_file)} ({len(output_rows)} matching lines)")
    except Exception as e:
        print_error(f"Error saving filtered lines: {e}")

def save_results_to_csv(results, columns, filename="search_results.csv"):
    """Save results to CSV with dynamic columns including nested keys.
       Handles errors gracefully (file in use, missing directory, etc.).
    """

    def get_nested_value(data, path):
        keys = path.split(".")
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None
        return data

    # Try to save file, always attempt to write, handle errors gracefully
    try:
        dir_name = os.path.dirname(filename)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for item in results:
                row = [get_nested_value(item, col) for col in columns]
                writer.writerow(row)
        print_success(f"Results saved to {os.path.basename(filename)} ({len(results)} records)")
    except Exception as e:
        print_error(f"Error saving results to {filename}: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_info("\n\nProcess interrupted by user. Goodbye!")
    except Exception as e:
        print_error(f"Application error: {e}")
        print_info("Please check your configuration and try again.")