#!/usr/bin/env sh

# Check if Emacs is installed
if ! command -v emacs &> /dev/null; then
    echo "Emacs could not be found."

    # Check if the script is running on a Linux system
    if [ "$(uname)" = "Linux" ]; then
        echo "Installing Emacs on Linux..."

        # Add commands to install Emacs for your Linux distribution
        # For Debian/Ubuntu:
        sudo apt-get update && sudo apt-get install emacs

        # For Red Hat/CentOS:
        # sudo yum install emacs

        # After attempting installation, verify if Emacs is installed
        if ! command -v emacs &> /dev/null; then
            echo "Failed to install Emacs. Exiting."
            exit 1
        fi
    else
        echo "Emacs installation is only automated for Linux systems. Please install Emacs manually."
        exit 1
    fi
fi

# Continue with your original script
# Tangle the Org file
emacs --batch --eval "(require 'org)" --eval "(org-babel-tangle-file \"build.org\")"

# Run the tangled Emacs Lisp script
emacs -Q --script build.el
