import pytest

from eglob import SegmentPattern

test_segment_data = [
    # test directory
    ("**", "cache", True),
    ("**", "cache", True),
    ("*conda", "anaconda", True),
    ("*conda", "anaconda3", False),
    # test file
    ("*.py", "app.py", True),
    ("*.{py,pyc}", "main.py", True),
    ("*.{py,pyc}", "cache.pyc", True),
    ("*.{py,pyc}", "cache.pyo", False),
    ("tmp?", "tmp12", False),
    ("tmp?", "tmp1", True),
    ("user[1-5].py", "user1.py", True),
    ("user[!1-5].py", "user1.py", False),
    ("user[!1-5].py", "user6.py", True),
]


@pytest.mark.parametrize("pattern,test_input,expected", test_segment_data)
def test_segment_match(pattern, test_input, expected):
    segment = SegmentPattern(pattern)
    assert segment.match(test_input) is expected
