from chunker import chunk_file

PY = '''import os
import sys  # glue code before first def

@decorator
def alpha(x):
    return x + 1


def beta(y):
    return y * 2


class Gamma:
    def m(self):
        return 3
'''


def test_python_three_definitions_with_symbols_and_lines():
    chunks = chunk_file("a.py", PY)
    defs = [c for c in chunks if c.symbol]
    assert [c.symbol for c in defs] == ["alpha", "beta", "Gamma"]
    alpha, beta, gamma = defs
    assert (alpha.start_line, alpha.end_line) == (4, 6)  # decorator included
    assert alpha.text.splitlines()[0] == "@decorator"
    assert (beta.start_line, beta.end_line) == (9, 10)
    assert (gamma.start_line, gamma.end_line) == (13, 15)
    assert gamma.citation == "a.py:13-15"
    # glue code before the first def is its own chunk
    glue = [c for c in chunks if not c.symbol]
    assert glue and glue[0].start_line == 1


def test_chunk_text_matches_line_range():
    lines = PY.splitlines()
    for c in chunk_file("a.py", PY):
        assert c.text == "\n".join(lines[c.start_line - 1 : c.end_line])


def test_markdown_windows():
    text = "\n".join(f"line number {i} of the document" for i in range(1, 201))
    chunks = chunk_file("doc.md", text)
    assert [c.start_line for c in chunks] == [1, 46, 91, 136, 181]
    assert chunks[0].end_line == 60
    assert chunks[-1].end_line == 200


def test_syntax_error_falls_back_to_windows():
    text = "def broken(:\n" + "\n".join(f"x = {i}  # padding" for i in range(100))
    chunks = chunk_file("bad.py", text)
    assert chunks and all(c.symbol == "" for c in chunks)
    assert chunks[0].start_line == 1


def test_long_function_is_windowed_with_symbol():
    body = "\n".join(f"    x{i} = {i}" for i in range(200))
    chunks = chunk_file("big.py", "def big():\n" + body + "\n")
    assert len(chunks) > 1
    assert all(c.symbol == "big" for c in chunks)


def test_empty_file_and_embedding_text():
    assert chunk_file("e.py", "") == []
    c = next(c for c in chunk_file("a.py", PY) if c.symbol == "alpha")
    assert c.embedding_text().startswith("File: a.py | Symbol: alpha\n")
