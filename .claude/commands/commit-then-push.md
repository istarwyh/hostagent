# Commit Then Push

Create a git commit and push it to the remote repository.

## Instructions

When this command is invoked, follow these steps:

1. **Check Git Status**: Run `git status` to see what changes are staged and unstaged
2. **Review Changes**: Run `git diff` to review both staged and unstaged changes
3. **Stage Changes**: If there are unstaged changes that should be committed, ask the user which files to stage, or stage all relevant files with `git add`
4. **Review Commit History**: Run `git log --oneline -5` to see recent commit messages and follow the repository's commit message style
5. **Create Commit**:
   - Draft a concise, descriptive commit message that follows the project's conventions
   - Create the commit with the message ending with:
     ```
     🤖 Generated with [Claude Code](https://claude.com/claude-code)

     Co-Authored-By: Claude <noreply@anthropic.com>
     ```
   - Use a HEREDOC format for the commit message
6. **Push to Remote**: After successful commit, push to the remote repository with `git push`
7. **Verify**: Run `git status` to confirm the push was successful

## Important Notes

- NEVER skip git hooks (don't use --no-verify)
- NEVER force push to main/master branches
- Always check that you're on the correct branch before pushing
- If pre-commit hooks modify files, handle the changes appropriately
- Ensure commit messages are meaningful and follow project conventions
- Confirm with the user if unsure about which files to commit

## Example Usage

```bash
# Stage changes
git add .

# Create commit
git commit -m "$(cat <<'EOF'
feat: add user authentication module
)"

# Push to remote
git push
```
