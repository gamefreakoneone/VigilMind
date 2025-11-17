
import sys
import os

# --- Configuration ---
HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
REDIRECT_IP = "150.171.27.10"  # IP for bing.com
DOMAINS_TO_REDIRECT = [
    "google.com",
    "www.google.com"
]
# --- End Configuration ---

def print_usage():
    """Prints how to use the script."""
    print("Usage: python website_monitor.py [--redirect | --revert]")
    print("  --redirect: Adds entries to the hosts file to redirect google.com to bing.com.")
    print("  --revert:   Removes the redirection entries from the hosts file.")
    print("\nNOTE: This script must be run with administrator privileges.")

def get_redirection_lines():
    """Generates the lines to be added to the hosts file."""
    return [f"{REDIRECT_IP} {domain}\n" for domain in DOMAINS_TO_REDIRECT]

def redirect():
    """Adds the redirection entries to the hosts file."""
    print("Applying redirection...")
    try:
        with open(HOSTS_PATH, "a") as f:
            f.writelines(get_redirection_lines())
        print("Successfully redirected google.com to bing.com.")
        print("Changes will take effect after a browser restart or DNS cache flush (ipconfig /flushdns).")
    except PermissionError:
        print("Error: Permission denied. Please run this script as an administrator.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def revert():
    """Removes the redirection entries from the hosts file."""
    print("Reverting redirection...")
    redirection_lines = get_redirection_lines()
    try:
        with open(HOSTS_PATH, "r") as f:
            lines = f.readlines()

        with open(HOSTS_PATH, "w") as f:
            for line in lines:
                if line not in redirection_lines:
                    f.write(line)

        print("Successfully removed redirection for google.com.")
        print("Changes will take effect after a browser restart or DNS cache flush (ipconfig /flushdns).")
    except PermissionError:
        print("Error: Permission denied. Please run this script as an administrator.")
    except FileNotFoundError:
        print(f"Error: Hosts file not found at {HOSTS_PATH}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print_usage()
        sys.exit(1)

    action = sys.argv[1]

    if action == "--redirect":
        redirect()
    elif action == "--revert":
        revert()
    else:
        print_usage()
        sys.exit(1)
