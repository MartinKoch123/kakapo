import unittest
import grammar
import model
import pyparsing as pp

import pytest


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
    actual = grammar.parse_string(string)[1][0]
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


class MatparseTest(unittest.TestCase):

    def test_delimited_list(self):
        tests = (
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
        for string, parser, expected in tests:
            actual = parser.parse_string(string, parse_all=True)[0]
            self.assertEqual(expected, actual)

    # def test_output_arguments_list(self):
    #     tests = (
    #         ("a = ", ("", mpm.DelimitedList.build([Call(['a', None])])), "", " ", "=", " ")),
    #         ("a\n, b = ", ("", mpm.DelimitedList.build("ab", left_white="\n"), "", " ", "=", " ")),
    #         ("[a] = ", ("[", "", mpm.DelimitedList.build("a"), "", "]", " ", "=", " ")),
    #         ("[a,b,c] = ", ("[", "", mpm.DelimitedList.build("abc", right_white=""), "", "]", " ", "=", " ")),
    #     )
    #
    #     for string, expected_tokens in tests:
    #         actual = mpg.output_arguments.parse_string(string)[0]
    #         expected = mpm.OutputArgumentList(expected_tokens)
    #         self.assertEqual(expected, actual)

    def test_string(self):
        tests = (
            ("'test'", "'test'"),
            ('"test"', '"test"'),
            ('"a""b"', '"a""b"'),
            ('"a' 'b"', '"a' 'b"'),
        )
        for input_, expected in tests:
            with self.subTest(msg=f"input: {input_}"):
                actual = grammar.string.parse_string(input_)[0]
                self.assertEqual(expected, actual)

    def test_call(self):
        tests = (
            "func",
            "func()",
            "func(  )",
            "func(1)",
            "func(1, a)",
            "func(1,a,  c)",
        )
        parser = grammar.call
        for string in tests:
            self.assert_parse_dump(string, parser)

    def test_operation(self):
        tests = (
            "a + 1 + 's1' + \"s2\"",
            "1 - 2 / 3 * 4 == 5 ~= 6 > 7 < 8 >= 9 <= 10 .* 11 ./12 \\ 13",
            "1+2",
        )
        for string in tests:
            self.assert_parse_dump(string, parser=grammar.operation)

    def test_anonymous_function(self):
        tests = (
            "@(x)x",
            "@(x) x",
            "@(x, y) 1 + 2",
            "@() 1 + 2",
            "@mean",
        )
        for string in tests:
            self.assert_parse_dump(string, parser=grammar.anonymous_function)

    def test_array(self):
        tests = (
            "[]",
            "[1, a, 'hello', true, mean(x + 1)]",
            "{1, 2, 3}",
        )
        for string in tests:
            self.assert_parse_dump(string, parser=grammar.array)

    def assert_parse_dump(self, string: str, parser: pp.ParserElement):
        model = parser.parse_string(string, parse_all=True)[0]
        expected = str(model)
        self.assertEqual(
            expected, string, msg=f'Parser: {parser.__class__.name}, Input: "{string}"'
        )


if __name__ == "__main__":
    unittest.main()
