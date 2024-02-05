#!/usr/bin/env sh

# Step 1: Tangle the Org file
emacs --batch --eval "(require 'org)" --eval "(org-babel-tangle-file \"posts/build.org\")"

# Step 2: Run the tangled Emacs Lisp script
emacs -Q --script build.el

