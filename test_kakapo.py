import unittest

import pyparsing as pp
import pytest

from kakapo import grammar, model


def assert_parsing_fails(element: pp.ParserElement, string: str):
    with pytest.raises(pp.ParseException):
        element.parse_string(string, parse_all=True)


def assert_parsing_returns_unmodified_string(element: pp.ParserElement, string: str):
    result = element.parse_string(string, parse_all=True)
    assert [string] == result.as_list()


@pytest.mark.parametrize("string", [" ", "\t", "\n", "\t\n"])
def test_white_space(string):
    assert_parsing_returns_unmodified_string(grammar.ws, string)


@pytest.mark.parametrize("string", ["", "abc"])
def test_white_space_error(string):
    assert_parsing_fails(grammar.ws, string)


@pytest.mark.parametrize("string", ["", " \t\n"])
def test_optional_white_space(string):
    assert_parsing_returns_unmodified_string(grammar.ows, string)


@pytest.mark.parametrize("string", ["a", ".", "  b"])
def test_optional_white_space_error(string):
    assert_parsing_fails(grammar.ows, string)


@pytest.mark.parametrize(
    "string",
    [
        " ",
        " \t ",
        " ... ",
        " ... ...",
        "...\n",
        "...\n... \n \t",
    ]
)
def test_element_delimiter(string):
    assert_parsing_returns_unmodified_string(grammar.element_delimiter, string)


@pytest.mark.parametrize(
    "string",
    [
        "",
        "\n",
        "\n ...",
        "...\n\n ",
    ]
)
def test_element_delimiter_error(string):
    assert_parsing_fails(grammar.element_delimiter, string)


@pytest.mark.parametrize("string", grammar.OPERATORS)
def test_operator(string):
    assert_parsing_returns_unmodified_string(grammar.operator, string)


@pytest.mark.parametrize("string", ["", "~", "'", "%", "abc"])
def test_operator_error(string):
    assert_parsing_fails(grammar.operator, string)


@pytest.mark.parametrize("string", grammar.KEYWORDS)
def test_keyword(string):
    assert_parsing_returns_unmodified_string(grammar.ReservedKeyword(), string)


@pytest.mark.parametrize("string", ["", "disp", "test", ".", "class", "iff"])
def test_keyword_error(string):
    assert_parsing_fails(grammar.ReservedKeyword(), string)


@pytest.mark.parametrize("string", ["a", "TEST", "x_123", "a" * 63])
def test_identifier(string):
    assert_parsing_returns_unmodified_string(grammar.identifier, string)


@pytest.mark.parametrize("string", ["", "_a", "asd$"])
def test_identifier_error(string):
    assert_parsing_fails(grammar.identifier, string)


@pytest.mark.parametrize(
    "string, expected",
    [
        ("import abc", model.Command(["import", " ", "abc"])),
        ("import ab.cd.ef", model.Command(["import", " ", "ab.cd.ef"])),
        ("import a.b.*", model.Command(["import", " ", "a.b.*"])),
    ],
)
def test_import(string, expected):
    actual = grammar.parse_string(string)[1][0] # noqa
    assert actual == expected


@pytest.mark.parametrize(
    "string, expected",
    [
        ("% hello world", model.Comment(("%", " hello world"))),
        ("%", model.Comment(("%", ""))),
    ],
)
def test_comment(string, expected):
    actual = grammar.parse_string(string)[1][0]
    assert actual == expected


@pytest.mark.parametrize("string", [",", ";"])
def test_array_delimiter(string):
    assert_parsing_returns_unmodified_string(grammar.array_delimiter, string)


@pytest.mark.parametrize(
    "string, expected",
    [
        ("clear", model.Command(["clear"])),
        ("clear a123 b_", model.Command(["clear", " ", "a123", " ", "b_"])),
        # ("command -flag arg", model.Command(["command", " ", "-flag", " ", "arg"]))
    ],
)
def test_command(string, expected):
    actual = grammar.parse_string(string)[1][0]
    assert actual == expected


@pytest.mark.parametrize(
    "string",
    [
        "command\narg",
        "command;arg",
        "command(arg)",
    ]
)
def test_command_error(string):
    assert_parsing_fails(grammar.command, string)


@pytest.mark.parametrize(
    ["string", "parser", "expected"],
    (
        (
            "a",
            grammar.DelimitedList(pp.Word(pp.alphas), delimiter=","),
            model.DelimitedList(["a"]),
        ),
        (
            "a\n, b",
            grammar.DelimitedList(pp.Word(pp.alphas), delimiter=","),
            model.DelimitedList(["a", "\n, ", "b"]),
        ),
        (
            "a ;; b   ;;c",
            grammar.DelimitedList(pp.Word(pp.alphas), delimiter=";;"),
            model.DelimitedList(["a", " ;; ", "b", "   ;;", "c"]),
        ),
    )
)
def test_delimited_list(string, parser, expected):
    actual = parser.parse_string(string, parse_all=True)[0]
    assert actual == expected

@pytest.mark.parametrize(
    ("input_", "expected"),
    (
        ("'test'", "'test'"),
        ('"test"', '"test"'),
        ('"a""b"', '"a""b"'),
        ('"a' 'b"', '"a' 'b"'),
    )
)
def test_string(input_, expected):
    actual = grammar.string.parse_string(input_)[0]
    assert actual == expected

@pytest.mark.parametrize(
    "string",
    (
        "func",
        "func()",
        "func(  )",
        "func(1)",
        "func(1, a)",
        "func(1,a,  c)",
    )
)
def test_call(string):
    model = grammar.call.parse_string(string, parse_all=True)[0]
    expected = str(model)
    assert expected == string

@pytest.mark.parametrize(
    "string",
    (
        "a + 1 + 's1' + \"s2\"",
        "1 - 2 / 3 * 4 == 5 ~= 6 > 7 < 8 >= 9 <= 10 .* 11 ./12 \\ 13",
        "1+2",
    )
)
def test_operation(string):
    model = grammar.operation.parse_string(string, parse_all=True)[0]
    expected = str(model)
    assert expected == string

@pytest.mark.parametrize(
    "string",
    (
        "@(x)x",
        "@(x) x",
        "@(x, y) 1 + 2",
        "@() 1 + 2",
        "@mean",
    )
)
def test_anonymous_function(string):
    model = grammar.anonymous_function.parse_string(string, parse_all=True)[0]
    expected = str(model)
    assert expected == string

@pytest.mark.parametrize(
    "string",
    (
        "[]",
        "[1, a, 'hello', true, mean(x + 1)]",
        "{1, 2, 3}",
    )
)
def test_array(string):
    model = grammar.array.parse_string(string, parse_all=True)[0]
    expected = str(model)
    assert expected == string


if __name__ == "__main__":
    pytest.main()
