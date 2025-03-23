import unittest
import grammar as mpg
import model as mpm
import pyparsing as pp

# Issue: by default tabs are parse as spaced. Call parse_with_tabs on every parser element?


class MatparseTest(unittest.TestCase):

    def test_white_space(self):

        positives = [" ", "\t", "\n", " \t\n"]
        negatives = ["", "a"]

        for s in positives:
            result = mpg.ws.parse_string(s)
            self.assertEqual([s], result.as_list())

        for s in negatives:
            parse = lambda x: mpg.ws.parse_string(x)
            self.assertRaises(pp.exceptions.ParseException, parse, s)

    def test_optional_white_space(self):

        for s in ["", " "]:
            result = mpg.ows.parse_string(s)
            self.assertEqual([s], result.as_list())

    def test_reserved_keyword(self):
        positives = ["classdef", "if", "while"]
        negatives = ["asdf", "max", ""]

        for s in positives:
            result = mpg.ReservedKeyword().parse_string(s)
            self.assertEqual([s], result.as_list())

        for s in negatives:
            parse = lambda x: mpg.ReservedKeyword().parse_string(x)
            self.assertRaises(pp.ParseException, parse, s)

    def test_comment(self):
        tests = (
            ("% comment", mpm.Comment(("%", " comment"))),
            ("%", mpm.Comment(("%", ""))),
        )
        for string, expected in tests:
            with self.subTest(msg=string):
                actual = mpg.comment.parse_string(string)[0]
                self.assertEqual(expected, actual)

    def test_identifier(self):
        positives = ["a", "TEST", "x_123", "a" * 63]
        for s in positives:
            result = mpg.identifier.parse_string(s, parse_all=True)
            self.assertEqual([s], result.as_list())

        negatives = ["", "_a", "asd$", "a" * 64]
        for s in negatives:
            with self.assertRaises(pp.ParseException):
                mpg.identifier.parse_string(s, parse_all=True)

    def test_delimited_list(self):
        tests = (
            ("a", mpg.DelimitedList(pp.Word(pp.alphas), delimiter=","), mpm.DelimitedList(["a"])),
            ("a\n, b", mpg.DelimitedList(pp.Word(pp.alphas), delimiter=","), mpm.DelimitedList(["a", "\n, ", "b"])),
            ("a ;; b   ;;c", mpg.DelimitedList(pp.Word(pp.alphas), delimiter=";;"), mpm.DelimitedList(["a", " ;; ", "b", "   ;;", "c"])),
        )
        for string, parser, expected in tests:
            actual = parser.parse_string(string, parse_all=True)[0]
            self.assertEqual(expected, actual)

    def test_output_arguments_list(self):
        tests = (
            ("a = ", ("", mpm.DelimitedList.build(["a"]), "", " ", "=", " ")),
            ("a\n, b = ", ("", mpm.DelimitedList.build("ab", left_white="\n"), "", " ", "=", " ")),
            ("[a] = ", ("[", "", mpm.DelimitedList.build("a"), "", "]", " ", "=", " ")),
            ("[a,b,c] = ", ("[", "", mpm.DelimitedList.build("abc", right_white=""), "", "]", " ", "=", " ")),
        )

        for string, expected_tokens in tests:
            actual = mpg.output_arguments.parse_string(string)[0]
            expected = mpm.OutputArgumentList(expected_tokens)
            self.assertEqual(expected, actual)

    def test_string(self):
        tests = (
            ("'test'", "'test'"),
            ('"test"', '"test"'),
            ('"a""b"', '"a""b"'),
            ('"a''b"', '"a''b"'),
        )
        for input_, expected in tests:
            with self.subTest(msg=f"input: {input_}"):
                actual = mpg.string.parse_string(input_)[0]
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
        parser = mpg.call
        for string in tests:
            self.assert_parse_dump(string, parser)

    def test_operation(self):
        tests = (
            "a + 1 + 's1' + \"s2\"",
            "1 - 2 / 3 * 4 == 5 ~= 6 > 7 < 8 >= 9 <= 10 .* 11 ./12 \\ 13",
            "1+2",
        )
        for string in tests:
            self.assert_parse_dump(string, parser=mpg.operation)

    def test_anonymous_function(self):
        tests = (
            "@(x)x",
            "@(x) x",
            "@(x, y) 1 + 2",
            "@() 1 + 2",
            "@mean",

        )
        for string in tests:
            self.assert_parse_dump(string, parser=mpg.anonymous_function)

    def test_array(self):
        tests = (
            "[]",
            "[1, a, 'hello', true, mean(x + 1)]",
            "{1, 2, 3}",
        )
        for string in tests:
            self.assert_parse_dump(string, parser=mpg.array)

    def assert_parse_dump(self, string: str, parser: pp.ParserElement):
        model = parser.parse_string(string, parse_all=True)[0]
        expected = str(model)
        self.assertEqual(expected, string, msg=f"Parser: {parser.__class__.name}, Input: \"{string}\"")


if __name__ == '__main__':
    unittest.main()
