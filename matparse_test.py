import unittest
from archive import matparse as mp
import pyparsing as pp


class MatparseTest(unittest.TestCase):

    def test_white_space(self):

        positives = [" ", "\t", "\n", " \t\n"]
        negatives = ["", "a"]

        for s in positives:
            result = mp.ws.parse_string(s)
            self.assertEqual([s], result.as_list())

        for s in negatives:
            parse = lambda x: mp.ws.parse_string(x)
            self.assertRaises(pp.exceptions.ParseException, parse, s)

    def test_optional_white_space(self):

        for s in ["", " "]:
            result = mp.ows.parse_string(s)
            self.assertEqual([s], result.as_list())

    def test_reserved_keyword(self):
        positives = ["classdef", "if", "while"]
        negatives = ["asdf", "max", ""]

        for s in positives:
            result = mp.reserved_keywords.parse_string(s)
            self.assertEqual([s], result.as_list())

        for s in negatives:
            parse = lambda x: mp.reserved_keywords.parse_string(x)
            self.assertRaises(pp.ParseException, parse, s)

    def test_matlab_name(self):
        positives = ["a", "TEST", "x_123", "a" * 63]
        for s in positives:
            result = mp.matlab_name.parse_string(s)
            self.assertEqual([s], result.as_list())

        negatives = ["", "_a", "asd$", "a" * 64]
        for s in negatives:
            parse = lambda x: mp.matlab_name.parse_string(x)
            self.assertRaises(pp.ParseException, parse, s)

    def test_keyword(self):
        actual = mp.keyword("function").parse_string("function  ")[0]
        expected = mp.Identifier(name="function", whitespace="  ")
        self.assertEqual(expected, actual)




if __name__ == '__main__':
    unittest.main()
