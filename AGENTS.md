# AGENTS.md - Development Guide for Agentic Coding

## Build Commands
- **Build site**: `sh build.sh` - Tangles build.org → build.el, then publishes site to public/
- **Development**: `uv run hotreload.py` - Auto-rebuilds on file changes with browser refresh
- **Single test**: No formal test framework - verify by building and checking public/ output

## Code Style Guidelines

### Emacs Lisp (build.el)
- Use `my/` prefix for custom functions (e.g., `my/org-publish`)
- Follow existing patterns in posts/build.org for new functionality
- Keep literate programming style - document code blocks in Org format
- Use `setq` for configuration, `defun` for functions

### Org Files
- Add `#+SELECT_TAGS: publish` to include files in site generation
- Use `#+TITLE:` and `#+DATE:` for post metadata
- Follow existing post structure in posts/ directory
- Keep content after first heading for RSS feed extraction

### Project Structure
- **posts/**: Blog posts (Org files with publish tag)
- **asset/**: CSS/JS files (prism.js for syntax highlighting)
- **html-templates/**: Site templates (preample.html)
- **public/**: Generated output (git-ignored)
- **.packages/**: Local Emacs packages (git-ignored)

### Development Workflow
1. Write content in Org files with publish tag
2. Use hotreload.py for live development
3. Build script handles Emacs cache cleaning and lock conflict resolution
4. RSS feed auto-generated from post metadata
5. GitHub Actions deploys main branch to GitHub Pages

### Error Handling
- Build script includes retry logic for Emacs lock conflicts
- Hot reload skips circular builds and Emacs lock files
- Port conflict resolution for development server
- Cache cleaning prevents stale build issues