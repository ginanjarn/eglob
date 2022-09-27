"""expanded glob

Glob with extended pattern match.

Glob patterns can have the following syntax:
- `*` to match one or more characters in a path segment
- `?` to match on one character in a path segment
- `**` to match any number of path segments, including none
- `{}` to group sub patterns into an OR expression. (e.g. `**/*.{ts,js}`
  matches all TypeScript and JavaScript files)
- `[]` to declare a range of characters to match in a path segment
  (e.g., `example.[0-9]` to match on `example.0`, `example.1`, …)
- `[!...]` to negate a range of characters to match in a path segment
  (e.g., `example.[!0-9]` to match on `example.a`, `example.b`, but
  not `example.0`)

"""

import re
import os
from functools import lru_cache
from io import StringIO
from typing import List, Iterator


GLOB_CHARACTERS = "*?{}[]!,/\\"


class SegmentPattern:
    """path segment pattern"""

    def __init__(self, pattern: str):
        self.pattern = pattern
        self.regex_pattern = self._compile(pattern)

    def __repr__(self):
        return f"SegmentPattern(pattern={repr(self.pattern)})"

    @lru_cache(128)
    def _compile(self, pattern: str) -> re.Pattern:
        offset = 0
        tmp_pattern = StringIO()
        while True:
            text = pattern[offset:]
            if not text:
                break

            if match := re.match(r"\*\*", text):
                offset += match.end()
                tmp_pattern.write(".*")
                if text[offset:]:
                    raise ValueError(f"invalid pattern: {repr(text)}")
                break

            if match := re.match(r"\{", text):
                offset += match.end()
                sub_patterns = []

                while True:
                    text = pattern[offset:]
                    if match := re.match(r"(\,)", text):
                        offset += match.end()
                        continue
                    elif match := re.match(r"(\})", text):
                        offset += match.end()
                        sub_patterns_text = "|".join(sub_patterns)
                        tmp_pattern.write(f"(?:{sub_patterns_text})")
                        break
                    elif match := re.match(r"([^\{\}\,]+)", text):
                        offset += match.end()
                        sub_patterns.append(match.group(1))
                    else:
                        raise ValueError(f"invalid segment characters: {repr(text)}")

                continue

            if match := re.match(r"\*", text):
                offset += match.end()
                tmp_pattern.write(f"[^{re.escape(GLOB_CHARACTERS)}]+")
                continue

            if match := re.match(r"\?", text):
                offset += match.end()
                tmp_pattern.write(f"[^{re.escape(GLOB_CHARACTERS)}]?")
                continue

            if match := re.match(f"([^{re.escape(GLOB_CHARACTERS)}]+)", text):
                offset += match.end()
                tmp_pattern.write(re.escape(match.group(1)))
                continue

            raise ValueError(f"invalid segment characters: {repr(text)}")

        return re.compile(f"^{tmp_pattern.getvalue()}$")

    def match(self, segment: str) -> bool:
        return bool(self.regex_pattern.match(segment))


def glob1(path: str, segments: List[SegmentPattern]) -> Iterator[str]:
    """glob with defined path and segments"""

    def walk_directory(dir_name) -> Iterator[str]:
        if segments[0].pattern == "**":
            yield from glob1(dir_name, segments)
        else:
            yield from glob1(dir_name, segments[1:])

    nested = len(segments) > 1
    for name in os.listdir(path):
        path_name = os.path.join(path, name)

        if os.path.isdir(path_name):
            if segments[0].match(name):
                yield from walk_directory(path_name)
            continue

        segment_name = segments[1] if nested else segments[0]
        if segment_name.match(name):
            yield path_name


def iglob(pattern: str) -> Iterator[str]:
    """iterable glob"""

    if not pattern.strip():
        raise ValueError("pattern empty")

    # normalize to unix separator
    pattern = pattern.replace("\\", "/")
    segments = [SegmentPattern(segment) for segment in pattern.split("/")]
    yield from glob1(os.getcwd(), segments)


def glob(pattern: str) -> List[str]:
    """glob"""
    return list(iglob(pattern))
