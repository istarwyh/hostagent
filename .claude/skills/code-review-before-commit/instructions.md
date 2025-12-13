# Code Review Before Commit

Perform a thorough code review of all uncommitted changes before creating a git commit.

## Objective

Review all staged and unstaged changes in the repository to identify potential issues in:
1. Code quality (best practices, potential bugs, security vulnerabilities)
2. Test coverage (missing or insufficient tests)
3. Documentation completeness (comments, docstrings, README updates)

## Process

### 1. Gather Changes

First, collect all uncommitted changes:
- Run `git status` to see modified and untracked files
- Run `git diff HEAD` to see all changes (staged + unstaged)
- For new files, use Read tool to view their content

### 2. Code Quality Review

For each modified or new file, check:

**General Code Quality:**
- Code follows language conventions and best practices
- No obvious bugs or logic errors
- Proper error handling where needed
- No hardcoded credentials or sensitive data
- Security vulnerabilities (SQL injection, XSS, command injection, etc.)
- No debugging code (console.log, print statements, etc.) unless intentional
- Consistent code style with the existing codebase

**Python-Specific:**
- Type hints where appropriate
- Proper exception handling
- No mutable default arguments
- Proper use of context managers for resources

**JavaScript/TypeScript-Specific:**
- Proper async/await usage
- No memory leaks (event listeners, intervals)
- Proper null/undefined checks

**Performance:**
- No obvious performance bottlenecks
- Efficient algorithms and data structures
- Proper resource cleanup

### 3. Test Coverage Review

Check if changes include appropriate tests:
- New functions/features have corresponding test cases
- Edge cases are covered
- Test files are updated when implementation changes
- Mock/stub external dependencies properly

### 4. Documentation Review

Verify documentation completeness:
- Complex logic has explanatory comments
- Public APIs have docstrings/JSDoc
- README updated if user-facing changes
- Breaking changes are documented
- Configuration changes are documented

### 5. Report Generation

Generate a comprehensive report with:

**Summary Section:**
- Total files changed
- Lines added/removed
- Overall assessment (Ready to commit / Needs attention / Has critical issues)

**Issues by Severity:**

**CRITICAL** (Must fix before commit):
- Security vulnerabilities
- Hardcoded secrets/credentials
- Code that will definitely break
- Missing critical error handling

**HIGH** (Should fix before commit):
- Logic errors or bugs
- Missing important tests
- Performance issues
- Significant code quality problems

**MEDIUM** (Recommended to fix):
- Code style inconsistencies
- Missing documentation for complex logic
- Minor performance optimizations
- Test coverage gaps

**LOW** (Optional improvements):
- Additional comments for clarity
- Minor refactoring suggestions
- Code organization improvements

**Format each issue as:**
```
[SEVERITY] file_path:line_number
Description of the issue
Suggestion for fixing
```

### 6. User Decision

After presenting the report:
- DO NOT automatically fix issues
- Let the user decide whether to:
  - Fix issues before committing
  - Commit as-is
  - Review specific issues in detail
  - Cancel the commit

## Example Output

```
## Code Review Report

### Summary
- Files changed: 3
- Lines added: +145
- Lines removed: -12
- Overall: Needs attention (2 high priority issues found)

### Issues Found

#### CRITICAL Issues: 0

#### HIGH Priority Issues: 2

[HIGH] src/auth/login.py:45
SQL injection vulnerability - user input directly interpolated into query
Suggestion: Use parameterized queries or ORM methods

[HIGH] src/api/users.py:78
Missing error handling for database connection failure
Suggestion: Add try-except block and proper error response

#### MEDIUM Priority Issues: 3

[MEDIUM] src/services/email.py:23
Missing unit tests for new send_bulk_email function
Suggestion: Add test cases covering success, failure, and edge cases

[MEDIUM] src/utils/helpers.py:56
Complex logic without explanatory comments
Suggestion: Add docstring explaining the algorithm

[MEDIUM] src/api/users.py:102
Debug print statement left in code
Suggestion: Remove or replace with proper logging

#### LOW Priority Issues: 1

[LOW] src/models/user.py:15
Could add type hints for better IDE support
Suggestion: Add -> User return type annotation

### Recommendation

Please address the HIGH priority issues before committing. The SQL injection vulnerability is a security risk that should be fixed immediately.

Would you like me to:
1. Help fix these issues?
2. Show detailed context for specific issues?
3. Proceed with commit anyway?
```

## Important Guidelines

- Be thorough but concise
- Focus on actionable feedback
- Provide specific file paths and line numbers
- Explain why something is an issue, not just what
- Prioritize issues realistically
- Consider the project context (test files may have different standards)
- NEVER automatically fix or commit - always let user decide
- If no issues found, give a positive summary but stay objective

## Edge Cases

- **No changes found**: Inform user there are no uncommitted changes
- **Only configuration files changed**: Focus on documentation and breaking changes
- **Test files only**: Review test quality and coverage
- **Large changesets (>500 lines)**: Provide high-level summary first, then detailed issues
- **Binary or generated files**: Skip review, just note them
