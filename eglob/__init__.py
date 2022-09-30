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
from typing import List, Iterator, Optional


GLOB_CHARACTERS = "*?{}[]!,/\\"


class SegmentPattern:
    """path segment pattern"""

    def __init__(self, pattern: str):
        self.pattern = pattern
        self.regex_pattern = self._compile_pattern(pattern)

    def __repr__(self):
        return f"SegmentPattern(pattern={repr(self.pattern)})"

    @staticmethod
    @lru_cache(128)
    def glob_to_regex(pattern: str) -> str:
        """convert glob to regular expression"""

        offset = 0
        escaped_glob_chars = re.escape(GLOB_CHARACTERS)

        def get_text() -> str:
            return pattern[offset:]

        def parse_inline() -> str:
            nonlocal offset
            pattern_block = []

            while True:
                sub_text = get_text()
                if not sub_text:
                    return "".join(pattern_block)

                # match one or more characters
                if match := re.match(r"\*", sub_text):
                    offset += match.end()
                    pattern_block.append(f"[^{escaped_glob_chars}]+")
                    continue

                # match exacty one character
                if match := re.match(r"\?", sub_text):
                    offset += match.end()
                    pattern_block.append(f"[^{escaped_glob_chars}]{{1}}")
                    continue

                # match defined characters
                if match := re.match(f"([^{escaped_glob_chars}]+)", sub_text):
                    offset += match.end()
                    pattern_block.append(re.escape(match.group(1)))
                    continue

                # else
                return "".join(pattern_block)

        def parse_range() -> str:
            nonlocal offset
            pattern_block = []

            while True:
                sub_text = get_text()
                # EOF
                if not sub_text:
                    # revert to original character
                    if pattern_block[1] == "^":
                        pattern_block[1] = "!"
                    return "".join(pattern_block)

                # open range
                if match := re.match(r"\[", sub_text):
                    offset += match.end()
                    pattern_block.append("[")

                    # negate to range
                    # negate character only valid after open bracket
                    sub_text = get_text()
                    if match := re.match("!", sub_text):
                        offset += match.end()
                        pattern_block.append("^")

                    continue

                # close range
                if match := re.match(r"\]", sub_text):
                    offset += match.end()
                    pattern_block.append("]")
                    return "".join(pattern_block)

                # range characters
                if match := re.match(r"([^\[\]]+)", sub_text):
                    offset += match.end()
                    pattern_block.append(match.group(1))
                    continue

                raise ValueError(f"invalid range characters: {repr(sub_text)}")

        def parse_subpattern() -> str:
            nonlocal offset
            pattern_block = []
            enter_scope = False

            while True:
                sub_text = get_text()

                # EOF
                if not sub_text:
                    text = ",".join(pattern_block)
                    return f"{{{text}"

                # open sub pattern
                if match := re.match(r"\{", sub_text):
                    offset += match.end()

                    if enter_scope:
                        # parse nested sub pattern
                        text = "".join((parse_subpattern(), parse_inline()))
                        try:
                            pattern_block[-1] = "".join((pattern_block[-1], text))
                        except IndexError:
                            pattern_block = [text]

                    enter_scope = True
                    continue

                # next sub pattern item
                if match := re.match(r"\,", sub_text):
                    offset += match.end()
                    continue

                # close sub pattern
                if match := re.match(r"\}", sub_text):
                    offset += match.end()
                    text = "|".join(pattern_block)
                    return f"(?:{text})"

                # match range
                if match := re.match(r"\[", sub_text):
                    text = "".join((parse_range(), parse_inline()))
                    try:
                        pattern_block[-1] = "".join((pattern_block[-1], text))
                    except IndexError:
                        pattern_block = [text]
                    continue

                # sub pattern charaters
                if sub_pattern := parse_inline():
                    pattern_block.append(sub_pattern)
                    continue

                raise ValueError(f"invalid segment characters: {repr(sub_text)}")

        tmp_pattern = []
        while True:
            text = pattern[offset:]
            if not text:
                break

            # match any characters
            if match := re.match(r"\*\*", text):
                offset += match.end()
                tmp_pattern.append(".*")
                if text[offset:]:
                    raise ValueError(f"invalid pattern: {repr(text)}")
                break

            # match sub pattern
            if match := re.match(r"\{", text):
                sub_pattern = parse_subpattern()
                tmp_pattern.append(sub_pattern)
                continue

            # match range
            if match := re.match(r"\[", text):
                sub_pattern = parse_range()
                tmp_pattern.append(sub_pattern)
                continue

            if sub_pattern := parse_inline():
                tmp_pattern.append(sub_pattern)
                continue

            raise ValueError(f"invalid segment characters: {repr(text)}")

        return "".join(tmp_pattern)

    def _compile_pattern(self, pattern: str) -> re.Pattern:
        regex = self.glob_to_regex(self.pattern)
        return re.compile(f"^{regex}$")

    def match(self, segment: str) -> bool:
        return bool(self.regex_pattern.match(segment))


class DirectorySegment(SegmentPattern):
    """Directory segment"""


class FileSegment(SegmentPattern):
    """File segment"""


def glob1(root_path: str, segments: List[SegmentPattern]):
    """glob with defined path and patterns"""

    for name in os.listdir(root_path):
        absolute_path = os.path.join(root_path, name)

        # match directory segment
        if isinstance(segments[0], DirectorySegment):
            if os.path.isdir(absolute_path):
                if segments[0].match(name):
                    yield from glob1(absolute_path, segments[1:])
            else:
                # match any subpattern ('**/(any_chars)')
                if segments[0].pattern == "**" and segments[1].match(name):
                    yield absolute_path
            continue

        # match file segment
        if os.path.isfile(absolute_path) and segments[0].match(name):
            yield absolute_path


def iglob(pattern: str, cwd: Optional[str] = None) -> Iterator[str]:
    """iterable glob"""

    if not pattern.strip():
        raise ValueError("pattern empty")

    # normalize to unix separator
    pattern = pattern.replace("\\", "/")

    *dir_segments, file_segment = pattern.split("/")
    segments = [DirectorySegment(segment) for segment in dir_segments]
    segments.append(FileSegment(file_segment))
    cwd = cwd or os.getcwd()
    yield from glob1(cwd, segments)


def glob(pattern: str, cwd: Optional[str] = None) -> List[str]:
    """glob"""
    return list(iglob(pattern, cwd))
