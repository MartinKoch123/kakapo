from typing import Sequence

from pyparsing import (
    Literal,
    Suppress,
    White,
    Opt,
    ParserElement,
    Or,
    Word,
    alphas,
    alphanums,
    Group,
    rest_of_line,
    ZeroOrMore,
    OneOrMore,
    Regex,
    empty,
    FollowedBy,
    common,
    Forward,
    Empty,
    QuotedString,
    Keyword,
)

import model

MAX_IDENTIFIER_LENGTH = 63


class ReservedKeyword(ParserElement):
    """
    A reserved keyword.
    Examples: "if", "return", "function"
    """

    KEYWORDS = [
        "arguments",
        "break",
        "case",
        "catch",
        "classdef",
        "continue",
        "else",
        "elseif",
        "end",
        "for",
        "function",
        "global",
        "if",
        "otherwise",
        "parfor",
        "persistent",
        "return",
        "spmd",
        "switch",
        "try",
        "while",
    ]

    def __init__(self):
        super().__init__()
        self.parser = Or(Literal(s) for s in ReservedKeyword.KEYWORDS)

    def parseImpl(self, instring, loc, doActions=True):
        return self.parser._parse(instring, loc, doActions)

    def _generateDefaultName(self) -> str:
        return "ReservedKeyword"


ParserElement.setDefaultWhitespaceChars("")

nothing = Empty().set_parse_action(lambda s, loc, toks: [""])

"""White space"""
# ws = White(" \t\n")
# ws = OneOrMore(ws | Literal("...")).parse_with_tabs()
# ws.add_parse_action(lambda s, loc, toks: ["".join(toks)])
ws = Word(" \t\n.").parse_with_tabs()

"""Optional white space"""
ows = Opt(ws, default="")

operator = Or(
    [
        "+",
        "-",
        "*",
        ".*",
        "/",
        "./",
        "\\",
        "==",
        "~=",
        ">",
        ">=",
        "<",
        "<=",
        "&",
        "&&",
        "|",
        "||",
        ":",
    ]
)


def or_none(expr: ParserElement):
    """Parse expr or return None if not found."""
    return Opt(expr, default=None)


class DelimitedList(ParserElement):
    """
    Parser for delimited list.

    Converts tokens into a model.DelimitedList object while parsing.
    """

    def __init__(self, expr: ParserElement, delimiter: str | ParserElement = ",", min_elements: int = 1, optional_delimiter: bool = False):
        super().__init__()

        if isinstance(delimiter, str):
            delimiter = Literal(delimiter)
        delimiter = ows + delimiter + ows
        if optional_delimiter:
            delimiter = delimiter | White(" \t\n")
        delimiter.add_parse_action(lambda s, loc, toks: ["".join(toks)])
        self.parser = (
            (
                expr
                + delimiter
                + FollowedBy(expr)
            )[max(min_elements - 1, 0), ...]
            + expr
        )
        if min_elements == 0:
            self.parser = self.parser | empty

    def parseImpl(self, instring, loc, doActions=True):
        loc, tokens = self.parser._parse(instring, loc, doActions)
        return loc, model.DelimitedList(tokens)

    def _generateDefaultName(self) -> str:
        return "DelimitedList"


class Block(ParserElement):
    def __init__(self, name: str, content: ParserElement, optional_end: bool = False):
        super().__init__()

        end = ws + Literal("end")
        if optional_end:
            end |= nothing + nothing

        self.parser = (
            Literal(name)
            + ws
            + content
            + end
        )

    def parseImpl(self, instring, loc, doActions=True):
        loc, tokens = self.parser._parse(instring, loc, doActions)
        return loc, model.Block(tokens)

    def _generateDefaultName(self) -> str:
        return "Block"


def space_delimited_list(expr: ParserElement, allow_empty: bool = False) -> ParserElement:
    result = ZeroOrMore(expr + ws + FollowedBy(expr)) + expr
    if allow_empty:
        result = result | empty
    return result


def ows_delimited_list(expr: ParserElement, allow_empty: bool = False) -> ParserElement:
    result = ZeroOrMore(expr + ows + FollowedBy(expr)) + expr
    if allow_empty:
        result = result | empty
    return result


def parenthesized(
    content: ParserElement,
    brackets: Sequence[tuple[str, str]] = (("(", ")"),),
    optional: bool = False,
):
    with_parenthesis = Or(
        (
            opening_bracket
            + ows
            + content
            + ows
            + closing_bracket
        ) for opening_bracket, closing_bracket in brackets
    )
    if not optional:
        return with_parenthesis

    without_parenthesis = nothing + content + nothing
    return with_parenthesis | without_parenthesis


"""
A string identifying a variable, function or class. Includes namespace syntax.
Examples:
 - a1_2
 - a.b.c
"""
identifier = (
    ~ReservedKeyword()
    + Word(alphas, alphanums + "_.", max=MAX_IDENTIFIER_LENGTH, min=1)
)

"""A comment. Starts at the comment marker '%' end ends at the next line break."""
comment = Literal("%") + rest_of_line

"""A quoted string with single or double quotes."""
string = (
    QuotedString(quote_char='"', esc_quote='""', unquote_results=False)
    | QuotedString(quote_char="'", esc_quote="''", unquote_results=False)
)

expression = Forward()

"""Array"""
array_delimiter = Literal(",") | Literal(";")
array = parenthesized(
    DelimitedList(expression, min_elements=0, delimiter=array_delimiter, optional_delimiter=True),
    brackets=(("[", "]"), ("{", "}"))
).set_name("Array")

output_arguments = (
    parenthesized(
        DelimitedList(identifier),
        brackets=(("[", "]"),),
        optional=True,
    )
    + ows
    + Literal("=")
    + ows
)


argument_brackets = (("(", ")"), ("{", "}"))
arguments_list = parenthesized(
    DelimitedList(
        expression | Literal(":"),
        min_elements=0
    ),
    brackets=argument_brackets
).set_name("ArgumentsList")

"""A variable or a function call with or without arguments. Includes nested calls."""
call = identifier + or_none(arguments_list[1, ...])

"""
Anonymous function definition
Examples: 
 - @(x) x + 1
 - @mean
"""
anonymous_function = (
    Literal("@")
    + ows
    + or_none(arguments_list)
    + ows
    + expression
)

operand_atom = call | common.number | string | array | anonymous_function

operand = Forward()

left_operation = (Literal("-") | Literal("~")) + operand_atom
right_operation = operand_atom + (Literal("'") | Literal(".'"))

single_element_operation = left_operation | right_operation

operand << (single_element_operation | operand_atom)
operand.set_name("Element")

operation = Forward()

parenthesized_operation = parenthesized(operation).set_name("ParenthesizedOperation")

operation << DelimitedList(
    parenthesized(
        operand | parenthesized_operation,
        optional=True),
    delimiter=operator,
    min_elements=2
).set_name("Operation")

expression << parenthesized(operation | operand, optional=True)
expression.set_name("Expression")

keyword = Or(Literal(kw) for kw in ["return", "break", "continue"])

"""An assignment or an expression with either no result or an unused result."""
statement = (
    or_none(output_arguments)
    + (expression | keyword)
    + or_none(ows + FollowedBy(Literal(";")))
    + or_none(Literal(";"))
)

code = Forward()

elseif_block_part = (
    Literal("elseif")
    + ws
    + expression
    + ws
    + code
)

else_block_part = (
    Literal("else")
    + ws
    + code
)

"""If block including possible "elseif" and "else" subblocks."""
if_block = Block(
    name="if",
    content=(
        expression
        + ws
        + code
        + ZeroOrMore(ws + elseif_block_part)
        + Opt(ws + else_block_part)
    )
)

for_loop = Block(
    name="for",
    content=(
        statement
        + ws
        + code
    )
)

function = Block(
    name="function",
    content=(
        or_none(output_arguments)
        + call
        + ws
        + code
    ),
    optional_end=True
)

catch = (
    Literal("catch")
    + Opt(White(" \t") + expression, default=None).add_parse_action(lambda toks: ["", ""] if toks[0] is None else toks)
    + ws
    + code
)

try_catch = Block(
    name="try",
    content=(
        code
        + or_none(ws + catch)
    )
)

code << ows_delimited_list(
    statement | comment | if_block | for_loop | function | try_catch,
    allow_empty=True
)

# Add parse actions to grammar objects which turn the tokens into the respective dataclass.
parse_actions = {
    arguments_list: model.ArgumentsList,
    function: model.Function,
    call: model.Call,
    output_arguments: model.OutputArgumentList,
    comment: model.Comment,
    operation: model.Operation,
    statement: model.Statement,
    code: model.Code,
    anonymous_function: model.AnonymousFunction,
    array: model.Array,
    single_element_operation: model.SingleElementOperation,
    parenthesized_operation: model.ParenthesizedOperation,
}

for parser_element, target_class in parse_actions.items():
    parser_element.add_parse_action(target_class.from_tokens)
