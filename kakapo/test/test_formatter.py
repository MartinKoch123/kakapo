import pytest
from typing import Any, Callable

from kakapo import formatter, grammar


def format(formatter: Callable[[Any], None], code: str) -> str:
    element = grammar.parse_string(code)
    formatter(element)
    return str(element)


@pytest.mark.parametrize(
    "input_, expected",
    [
        ("[ 1, 2\t ]", "[1, 2]"),
        ("{ 1, 2\t }", "{1, 2}"),
        ("[ \t\n  ]", "[]"),
    ],
)
def test_normalize_whitespace_in_parenthesized(input_: str, expected: str):
    actual = format(formatter.normalize_whitespace_in_parenthesized, input_)
    assert actual == expected


@pytest.mark.parametrize(
    "input_, expected",
    [
        ("a  =   \t 1", "a = 1"),
        ("[a, b]=func(1, 2)", "[a, b] = func(1, 2)"),
    ],
)
def test_normalize_whitespace_in_assignment(input_: str, expected: str):
    actual = format(formatter.normalize_whitespace_in_assignment, input_)
    assert actual == expected


@pytest.mark.parametrize(
    "input_, expected",
    [
        ("a = 1 ;", "a = 1;"),
        ("mean([1, 2])\t  ;", "mean([1, 2]);"),
    ],
)
def test_remove_white_space_before_semicolon(input_: str, expected: str):
    actual = format(formatter.remove_white_space_before_semicolon, input_)
    assert actual == expected


@pytest.mark.parametrize(
    "input_, expected",
    [
        ("if true\n a = 1\n end  ;", "if true\n a = 1\n end"),
        ("function func()\n clear\n end;", "function func()\n clear\n end"),
    ],
)
def test_remove_semicolon_and_whitespace_after_end_keyword(input_: str, expected: str):
    actual = format(formatter.remove_semicolon_and_whitespace_after_end_keyword, input_)
    assert actual == expected


@pytest.mark.parametrize(
    "input_, expected",
    [
        ("if true;\n a = 1\n end", "if true\n a = 1\n end"),
        (
            "if func(1) + func(a, b) ;\n a = 1\n end",
            "if func(1) + func(a, b)\n a = 1\n end",
        ),
    ],
)
def test_remove_semicolon_after_if_condition(input_: str, expected: str):
    actual = format(
        formatter.remove_white_space_and_semicolon_after_if_condition, input_
    )
    assert actual == expected


@pytest.mark.parametrize(
    "input_, expected",
    [
        ("return ;", "return"),
        ("break\t ;", "break"),
        ("continue   ;", "continue"),
    ],
)
def test_remove_semicolon_after_keyword(input_: str, expected: str):
    actual = format(formatter.remove_white_space_and_semicolon_after_keyword, input_)
    assert actual == expected


@pytest.mark.parametrize(
    "input_, expected",
    [
        ("function func()\ndisp('hello')", "function func()\ndisp('hello')\nend"),
    ],
)
def test_ensure_function_end(input_: str, expected: str):
    actual = format(formatter.ensure_function_end, input_)
    assert actual == expected


@pytest.mark.parametrize(
    "input_, expected",
    (
        ("disp('hello')", "disp('hello')\n"),
        ("function func()\ndisp(1)", "function func()\ndisp(1)\n"),
    ),
)
def test_normalize_trailing_whitespace(input_: str, expected: str):
    actual = format(formatter.normalize_trailing_whitespace, input_)
    assert actual == expected


@pytest.mark.parametrize(
    "input_, expected",
    (
        ("   \n\n  disp('hello')", "disp('hello')"),
        ("\t\t function func()\ndisp(1)", "function func()\ndisp(1)"),
    ),
)
def test_normalize_leading_whitespace(input_: str, expected: str):
    actual = format(formatter.normalize_leading_whitespace, input_)
    assert actual == expected


@pytest.mark.parametrize(
    "input_, expected",
    (
        ("disp('hello')\n%comment", "disp('hello')\n% comment"),
        ("disp('hello')\n% comment", "disp('hello')\n% comment"),
        ("disp('hello')\n%  comment", "disp('hello')\n%  comment"),
    ),
)
def test_ensure_comment_leading_space(input_: str, expected: str):
    actual = format(formatter.ensure_comment_leading_space, input_)
    assert actual == expected
