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
    actual = grammar.ws.parse_string(string)[0]
    assert actual == model.Literal(string)


@pytest.mark.parametrize("string", ["", "abc"])
def test_white_space_error(string):
    assert_parsing_fails(grammar.ws, string)


@pytest.mark.parametrize("string", ["", " \t\n"])
def test_optional_white_space(string):
    actual = grammar.ows.parse_string(string)[0]
    assert actual == model.Literal(string)


@pytest.mark.parametrize("string", ["a", ".", "  b"])
def test_optional_white_space_error(string):
    assert_parsing_fails(grammar.ows, string)


@pytest.mark.parametrize("string", ("var", "x", "TEST", "x_123", "a" * 63))
def test_identifier(string):
    actual = grammar.identifier.parse_string(string)[0]
    expected = model.Literal(string)
    assert actual == expected


@pytest.mark.parametrize(
    "string",
    [
        " ",
        " \t ",
        " ... ",
        " ... ...",
        "...\n",
        "...\n... \n \t",
    ],
)
def test_element_delimiter(string):
    actual = grammar.element_delimiter.parse_string(string)[0]
    expected = model.Literal(string)
    assert actual == expected


@pytest.mark.parametrize(
    "string",
    [
        "",
        "\n",
        "\n ...",
        "...\n\n ",
    ],
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


@pytest.mark.parametrize("string", ["", "_a", "asd$"])
def test_identifier_error(string):
    assert_parsing_fails(grammar.identifier, string)


@pytest.mark.parametrize(
    "string, expected",
    [
        ("import abc", model.Command([model.Literal(s) for s in ["import", " ", "abc"]])),
        (
            "import ab.cd.ef",
            model.Command([model.Literal(s) for s in ["import", " ", "ab.cd.ef"]]),
        ),
        (
            "import a.b.*",
            model.Command([model.Literal(s) for s in ["import", " ", "a.b.*"]]),
        ),
    ],
)
def test_import(string, expected):
    actual = grammar.parse_string(string).code[0]  # noqa
    assert actual == expected


@pytest.mark.parametrize(
    "string, expected",
    [
        ("% hello world", model.Comment("%", " hello world")),
        ("%", model.Comment("%", "")),
    ],
)
def test_comment(string, expected):
    actual = grammar.comment.parse_string(string)[0]
    assert actual == expected


@pytest.mark.parametrize("string", [",", ";"])
def test_array_delimiter(string):
    assert_parsing_returns_unmodified_string(grammar.array_delimiter, string)


@pytest.mark.parametrize(
    "string, expected",
    [
        ("clear", model.Command([model.Literal("clear")])),
        (
            "clear a123 b_",
            model.Command([model.Literal(s) for s in ["clear", " ", "a123", " ", "b_"]]),
        ),
        # ("command -flag arg", model.Command(["command", " ", "-flag", " ", "arg"]))
    ],
)
def test_command(string, expected):
    actual = grammar.command.parse_string(string)[0]
    assert actual == expected


@pytest.mark.parametrize(
    "string",
    [
        "command\narg",
        "command;arg",
        "command(arg)",
    ],
)
def test_command_error(string):
    assert_parsing_fails(grammar.command, string)


@pytest.mark.parametrize(
    ["string", "parser", "expected"],
    (
        (
            "a",
            grammar.DelimitedList(grammar.identifier, delimiter=","),
            model.DelimitedList([model.Literal("a")]),
        ),
        (
            "a\n, b",
            grammar.DelimitedList(grammar.identifier, delimiter=","),
            model.DelimitedList([model.Literal(s) for s in ["a", "\n, ", "b"]]),
        ),
        (
            "a ;; b   ;;c",
            grammar.DelimitedList(grammar.identifier, delimiter=";;"),
            model.DelimitedList(
                [model.Literal(s) for s in ["a", " ;; ", "b", "   ;;", "c"]]
            ),
        ),
    ),
)
def test_delimited_list(string, parser, expected):
    actual = parser.parse_string(string)[0]
    assert actual == expected


@pytest.mark.parametrize(
    ("input_", "expected"),
    (
        ("'test'", "'test'"),
        ('"test"', '"test"'),
        ('"a""b"', '"a""b"'),
        ('"a' 'b"', '"a' 'b"'),
    ),
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
        "func(1,a,  2 / 3 + max(1, 2))",
    ),
)
def test_call(string):
    model = grammar.call.parse_string(string)[0]
    expected = str(model)
    assert expected == string


@pytest.mark.parametrize(
    "string",
    (
        "a + 1 + 's1' + \"s2\"",
        "1 - 2 / 3 * 4 == 5 ~= 6 > 7 < 8 >= 9 <= 10 .* 11 ./12 \\ 13",
        "1+2",
        "1:5",
    ),
)
def test_operation(string):
    model = grammar.operation.parse_string(string)[0]
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
    ),
)
def test_anonymous_function(string):
    model = grammar.anonymous_function.parse_string(string)[0]
    expected = str(model)
    assert expected == string


@pytest.mark.parametrize(
    "string",
    (
        "[]",
        "[1, a, 'hello', true, mean(x + 1)]",
        "{1, 2, 3}",
    ),
)
def test_array(string):
    model = grammar.array.parse_string(string)[0]
    expected = str(model)
    assert expected == string


@pytest.mark.parametrize(
    "string",
    (
        "function func()\ndisp('hello')\nend",
        "function func()\ndisp('hello')",
    ),
)
def test_function(string):
    model = grammar.function.parse_string(string)[0]
    expected = str(model)
    assert expected == string


# @pytest.mark.parametrize(
#     "string",
#     (
#         "",
#     )
# )
# def test_arguments_list(string):
#     model = grammar.arguments_list.parse_string(string)[0]
#     expected = str(model)
#     assert expected == string


@pytest.mark.parametrize(
    "string",
    (
        ";",
        " ;\n",
        "\n",
    )
)
def test_statement_delimiter(string):
    model = grammar.statement_delimiter.parse_string(string)[0]
    expected = str(model)
    assert expected == string

@pytest.mark.parametrize(
    "string",
    (
        "a",
        "a;b",
        "a % comment",
        "a% comment",
        "a = 1\nb(2) % comment",
    ),
)
def test_code(string):
    model = grammar.code.parse_string(string, parse_all=True)[0]
    expected = str(model)
    assert expected == string


@pytest.mark.parametrize(
    "string",
    (
        "else",
        "else \n a = 1"
    ),
)
def test_else(string):
    model = grammar.else_.parse_string(string)[0]
    assert str(model) == string


@pytest.mark.parametrize(
    "string",
    (
        "elseif true",
        "elseif 1 == 2 \n a = 1",
    ),
)
def test_else_if(string):
    model = grammar.else_if.parse_string(string)[0]
    assert str(model) == string


@pytest.mark.parametrize(
    "string",
    (
        "if true\n end",
        "if true\n a = 1 end",
    ),
)
def test_if(string):
    model = grammar.if_.parse_string(string)[0]
    expected = str(model)
    assert expected == string


@pytest.mark.parametrize(
    "string",
    (
        "properties end",
        "properties\n end",
        "properties\n a;b end",
        "properties\n a\nb\nend",
    ),
)
def test_properties(string):
    model = grammar.properties.parse_string(string)[0]
    expected = str(model)
    assert expected == string

@pytest.mark.parametrize(
    "string",
    (
        "methods \n end",
        "methods \n function a() \n end \n end",
        "methods(Static)\nend",
    )
)
def test_methods(string):
    model = grammar.methods.parse_string(string)[0]
    expected = str(model)
    assert expected == string


@pytest.mark.parametrize(
    "string",
    (
        "classdef A end",
        "classdef A \n properties \n a \n end \n end",
        "classdef A \n methods \n a \n end \n end",
    )
)
def test_classdef(string):
    model = grammar.classdef.parse_string(string)[0]
    expected = str(model)
    assert expected == string

@pytest.mark.parametrize(
    "string",
    (
        "switch x\n end",
        "switch x\n case 1\n otherwise \n b \n end",
    )
)
def test_switch(string):
    model = grammar.switch.parse_string(string)[0]
    expected = str(model)
    assert expected == string


@pytest.mark.parametrize(
    "string",
    (
        "catch",
        "catch \n a = 1",
        "catch exc \n a = 1",
    )
)
def test_catch(string):
    model = grammar.catch.parse_string(string)[0]
    assert str(model) == string


@pytest.mark.parametrize(
    "string",
    (
        "try \n end",
        "try \n a \n end",
        "try \n catch \n end",
        "try \n a; catch \n b = 1 \n end",
    )
)
def test_try(string):
    model = grammar.try_.parse_string(string)[0]
    assert str(model) == string


@pytest.mark.parametrize(
    "string",
    (
        "for i = 1\n end",
        "for i = 1:2\n a = 1 end",
        "for i = test\n a = 1\n b = 2\n end",
    ),
)
def test_for(string):
    model = grammar.for_.parse_string(string)[0]
    assert str(model) == string


@pytest.mark.parametrize(
    "string",
    (
        "while true\n end",
        "while a == func()\n a = 1 end",
        "while true\n a = 1\n b = 2\n end",
    ),
)
def test_while(string):
    model = grammar.while_.parse_string(string)[0]
    assert str(model) == string


@pytest.mark.parametrize(
    "string",
    (
        "",
        " a = 1 \n b = 2",
        "a = 1 \n b = 2  ",
        " ;; a = 1 ;\n "
    ),
)
def test_file(string):
    model = grammar.file.parse_string(string, parse_all=True)[0]
    assert str(model) == string



if __name__ == "__main__":
    pytest.main()
