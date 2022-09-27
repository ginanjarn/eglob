
# EGLOB

Glob with extended pattern match.

## Supported pattern matches

|Character|Matches|
|---------|-------|
|`*`| to match one or more characters in a path segment|
|`?`| to match on one character in a path segment|
|`**`| to match any number of path segments, including none|
|`{}`| to group sub patterns into an OR expression. (e.g. `**/*.{ts,js}` matches all TypeScript and JavaScript files)|
|`[]`| to declare a range of characters to match in a path segment (e.g., `example.[0-9]` to match on `example.0`, `example.1`, …)|
|`[!...]`|to negate a range of characters to match in a path segment  (e.g., `example.[!0-9]` to match on `example.a`, `example.b`, but not `example.0`)|