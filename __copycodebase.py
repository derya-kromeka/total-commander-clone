import os
import shutil
import json
import socket
import hashlib

def load_custom_destinations():
    """Load custom destinations from JSON file"""
    computer_name = socket.gethostname()
    filename = '__copycodebase.json'
    
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                all_destinations = json.load(f)
                # Return only destinations for current computer, or empty dict if none exist
                return all_destinations.get(computer_name, {})
        except:
            return {}
    return {}

def save_custom_destination(name, path):
    """Save a new custom destination to JSON file"""
    computer_name = socket.gethostname()
    filename = '__copycodebase.json'
    
    # Load all existing destinations
    all_destinations = {}
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                all_destinations = json.load(f)
        except:
            pass
    
    # Initialize computer's destinations if not exists
    if computer_name not in all_destinations:
        all_destinations[computer_name] = {}
    
    # Update destination for current computer
    all_destinations[computer_name][name] = path
    
    # Save all destinations back to file
    with open(filename, 'w') as f:
        json.dump(all_destinations, f, indent=4)

def get_all_destinations():
    """Combine default and custom destinations"""
    default_destinations = {
        1: {
            "name": "Google Drive Workshop",
            "path": r"G:\My Drive\90 - DERYA\02_Areas\Workshop"
        },
        2: {
            "name": "CursorAI Workshop",
            "path": r"C:\Users\Derya\PARA\02_Areas\Workshop\CursorAI"
        },
        3: {
            "name": "Local Workshop",
            "path": r"C:\Users\Derya\PARA\02_Areas\Workshop"
        }
    }
    
    # Add separator after default destinations
    next_key = max(default_destinations.keys()) + 1
    default_destinations[next_key] = {"name": "─" * 30, "path": None, "separator": True}
    next_key += 1
    
    # Load custom destinations
    custom_destinations = load_custom_destinations()
    
    # Add custom destinations to the list
    for name, path in custom_destinations.items():
        default_destinations[next_key] = {
            "name": name,
            "path": path
        }
        next_key += 1
    
    # Add spacing before management options
    if custom_destinations:
        default_destinations[next_key] = {"name": "─" * 30, "path": None, "separator": True}
        next_key += 1
    
    # Add management options
    default_destinations[95] = {"name": "Toggle Version Control (Currently: ON)", "path": None}
    default_destinations[96] = {"name": "Edit Existing Destination", "path": None}
    default_destinations[97] = {"name": "Add Custom Destination", "path": None}
    default_destinations[98] = {"name": "─" * 30, "path": None, "separator": True}
    default_destinations[99] = {"name": "Exit", "path": None}
    
    return default_destinations

def edit_custom_destination(destinations):
    """Edit an existing custom destination"""
    print("\nSelect a destination to edit:")
    
    computer_name = socket.gethostname()
    filename = '__copycodebase.json'
    
    # Show only custom destinations
    custom_destinations = load_custom_destinations()
    if not custom_destinations:
        print("No custom destinations to edit!")
        return False
    
    # Create a mapping of menu numbers to custom destination names
    custom_menu = {}
    menu_num = 1
    for key, value in destinations.items():
        if value['path'] and value['name'] in custom_destinations:
            custom_menu[menu_num] = value['name']
            print(f"{menu_num}. {value['name']}")
            print(f"   Path: {value['path']}")
            menu_num += 1
    
    if not custom_menu:
        print("No custom destinations to edit!")
        return False
    
    # Get user choice
    while True:
        try:
            choice = int(input(f"\nEnter your choice (1-{len(custom_menu)}): "))
            if 1 <= choice <= len(custom_menu):
                break
            print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")
    
    selected_name = custom_menu[choice]
    print(f"\nEditing: {selected_name}")
    print(f"Current path: {custom_destinations[selected_name]}")
    
    # Get new details
    new_name = input("Enter new name (or press Enter to keep current): ").strip()
    new_path = input("Enter new path (or press Enter to keep current): ").strip()
    
    # Update only if new values provided
    if new_name or new_path:
        if not new_name:
            new_name = selected_name
        if not new_path:
            new_path = custom_destinations[selected_name]
        
        # Validate new path
        if not os.path.exists(new_path):
            print(f"\n❌ Error: Path does not exist: {new_path}")
            return False
        
        # Load all destinations
        all_destinations = {}
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                all_destinations = json.load(f)
        
        # Delete old entry if name changed
        if new_name != selected_name:
            del all_destinations[computer_name][selected_name]
        
        # Save updated destination
        all_destinations[computer_name][new_name] = new_path
        
        with open(filename, 'w') as f:
            json.dump(all_destinations, f, indent=4)
        
        print(f"\n✅ Successfully updated destination: {new_name}")
        return True
    
    print("\nNo changes made.")
    return False

def add_custom_destination():
    """Prompt user to add a custom destination"""
    print("\nAdding Custom Destination")
    name = input("Enter destination name: ").strip()
    path = input("Enter full path: ").strip()
    
    if os.path.exists(path):
        save_custom_destination(name, path)
        print(f"\n✅ Successfully added custom destination: {name}")
        return True
    else:
        print(f"\n❌ Error: Path does not exist: {path}")
        return False

def get_folder_hash(folder_path):
    """Calculate a hash for the entire folder contents"""
    sha256_hash = hashlib.sha256()

    for root, dirs, files in os.walk(folder_path):
        # Sort directories and files for consistent ordering
        dirs.sort()
        files.sort()
        
        for file in files:
            file_path = os.path.join(root, file)
            # Get file stats
            stats = os.stat(file_path)
            # Update hash with file path (relative to folder), size and modification time
            relative_path = os.path.relpath(file_path, folder_path)
            hash_string = f"{relative_path}|{stats.st_size}|{stats.st_mtime}"
            sha256_hash.update(hash_string.encode())
    
    return sha256_hash.hexdigest()

def verify_folders_match(source_path, dest_path):
    """Verify that source and destination folders have identical contents"""
    source_files = set()
    dest_files = set()
    
    # Collect all files and their sizes from source
    for root, _, files in os.walk(source_path):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, source_path)
            try:
                size = os.path.getsize(full_path)
                source_files.add((rel_path, size))
            except (OSError, IOError) as e:
                print(f"⚠️ Warning: Couldn't read source file {rel_path}: {e}")
    
    # Collect all files and their sizes from destination
    for root, _, files in os.walk(dest_path):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, dest_path)
            try:
                size = os.path.getsize(full_path)
                dest_files.add((rel_path, size))
            except (OSError, IOError) as e:
                print(f"⚠️ Warning: Couldn't read destination file {rel_path}: {e}")
    
    # Compare the sets
    missing_in_dest = source_files - dest_files
    missing_in_source = dest_files - source_files
    
    return len(missing_in_dest) == 0 and len(missing_in_source) == 0, missing_in_dest, missing_in_source

def copy_folder_to_location(source_path, destination_base, keep_versions=True):
    """
    Copy folder to destination location with optional versioning
    
    Args:
        source_path (str): Path to the source folder
        destination_base (str): Base path for the destination
        keep_versions (bool): Whether to keep versions of the folder (default: True)
    """
    # Get the name of the source folder
    source_folder_name = os.path.basename(source_path)
    
    # Create versions folder name
    versions_folder_name = f"{source_folder_name}_versions"
    versions_folder_path = os.path.join(destination_base, versions_folder_name)
    
    # Create versions folder if keeping versions and it doesn't exist
    if keep_versions and not os.path.exists(versions_folder_path):
        os.makedirs(versions_folder_path)
    
    # Calculate hash of source folder
    print("\n📊 Calculating source folder hash...")
    source_hash = get_folder_hash(source_path)
    
    # Check if there's an existing folder with the same name in destination_base
    existing_folder_path = os.path.join(destination_base, source_folder_name)
    if os.path.exists(existing_folder_path):
        print("📊 Calculating existing folder hash...")
        existing_hash = get_folder_hash(existing_folder_path)
        
        # If hashes match, verify contents to be sure
        if source_hash == existing_hash:
            print("🔍 Verifying folder contents...")
            match, missing_dest, missing_source = verify_folders_match(source_path, existing_folder_path)
            if match:
                print("\n✅ Folder contents are identical - skipping copy")
                return True
        
        if keep_versions:
            # Version control logic
            existing_versions = []
            for item in os.listdir(versions_folder_path):
                if os.path.isdir(os.path.join(versions_folder_path, item)):
                    try:
                        version = int(item.split('_v')[-1])
                        existing_versions.append(version)
                    except ValueError:
                        continue
            
            # Determine new version number
            new_version = 1 if not existing_versions else max(existing_versions) + 1
            
            # Move existing folder to versions folder
            move_folder_name = f"{source_folder_name}_v{new_version}"
            move_folder_path = os.path.join(versions_folder_path, move_folder_name)
            
            print(f"\n📦 Moving existing folder to versions: {move_folder_name}")
            try:
                shutil.move(existing_folder_path, move_folder_path)
            except Exception as move_error:
                print(f"\n⚠️ Warning: Could not move existing folder: {move_error}")
                print("Continuing with copy operation...")
        else:
            # If not keeping versions, simply remove the existing folder
            print("\n🗑️ Removing existing folder...")
            try:
                shutil.rmtree(existing_folder_path)
            except Exception as remove_error:
                print(f"\n⚠️ Warning: Could not remove existing folder: {remove_error}")
                print("Continuing with copy operation...")

    # If no existing folder, just copy the source
    try:
        print(f"\n📦 Copying to main location: {source_folder_name}")
        shutil.copytree(source_path, existing_folder_path)
        
        # Verify the copy operation
        print("\n🔍 Verifying copy operation...")
        match, missing_dest, missing_source = verify_folders_match(source_path, existing_folder_path)
        
        if not match:
            print("\n⚠️ Copy verification failed! Attempting to copy again...")
            try:
                # Instead of removing and recreating, just copy over the contents
                shutil.copytree(source_path, existing_folder_path, dirs_exist_ok=True)
                
                # Verify again
                match, missing_dest, missing_source = verify_folders_match(source_path, existing_folder_path)
                if not match:
                    print("\n❌ Copy operation failed verification even after retry!")
                    if missing_dest:
                        print("\nMissing files in destination:")
                        for file, size in missing_dest:
                            print(f"  - {file} ({size} bytes)")
                    if missing_source:
                        print("\nUnexpected files in destination:")
                        for file, size in missing_source:
                            print(f"  - {file} ({size} bytes)")
                    return False
            except Exception as retry_error:
                print(f"\n⚠️ Error during retry: {retry_error}")
                print("Attempting one final copy with force overwrite...")
                # One final attempt with force overwrite
                shutil.copytree(source_path, existing_folder_path, dirs_exist_ok=True)
                match, missing_dest, missing_source = verify_folders_match(source_path, existing_folder_path)
                if not match:
                    print("\n❌ Final copy attempt failed verification!")
                    return False
        
        print("\n✅ Successfully copied folder and verified contents")
        return True
        
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        return False

def main():
    # Add version control state
    keep_versions = True
    
    while True:
        # Get the current working directory
        current_directory = os.getcwd()
        print(f"\nCurrent Directory: {current_directory}")
        
        # Get all destinations including custom ones
        destinations = get_all_destinations()
        
        # Update version control status in menu
        version_status = "ON" if keep_versions else "OFF"
        destinations[95]["name"] = f"Toggle Version Control (Currently: {version_status})"
        
        # Display options
        print("\nWhere would you like to copy the folder?")
        for key, value in destinations.items():
            if value.get("separator"):
                print(value["name"])  # Print separator without number
            else:
                print(f"{key}. {value['name']}")
                if value['path']:
                    print(f"   Path: {value['path']}")
        
        # Get user choice
        while True:
            try:
                choice = int(input("\nEnter your choice: "))
                if choice in destinations and not destinations[choice].get("separator"):
                    break
                print(f"Invalid choice. Please select a valid number.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Handle exit choice
        if choice == 99:
            print("\nGoodbye! 👋")
            break
        
        # Handle version control toggle
        if choice == 95:
            keep_versions = not keep_versions
            status = "enabled" if keep_versions else "disabled"
            print(f"\n✅ Version control {status}")
            continue
        
        # Handle edit destination choice
        if choice == 96:
            edit_custom_destination(destinations)
            continue
            
        # Handle custom destination choice
        if choice == 97:
            add_custom_destination()
            continue
        
        # Copy to selected destination
        selected_destination = destinations[choice]
        print(f"\nCopying to: {selected_destination['name']}")
        print(f"Version Control: {'Enabled' if keep_versions else 'Disabled'}")
        
        # Perform the copy operation with version control setting
        success = copy_folder_to_location(current_directory, selected_destination['path'], keep_versions)

if __name__ == "__main__":
    main()