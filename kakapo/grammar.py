"""
Parsing logic for MATLAB code.

Terminology:
 - Block: Code delimited by a block keyword and the 'end' keyword, e.g. function, if, for.
 - Construct: Unit of code which can stand on its own, e.g. statements, blocks, comments.

Todo:
 - Support all format of command arguments.

"""

# pyright: reportUnusedExpression=false


from typing import Sequence
from pathlib import Path
import itertools

from pyparsing import (
    Char,
    Combine,
    common,
    empty,
    Empty,
    line_end,
    Literal,
    Opt,
    Or,
    FollowedBy,
    Forward,
    ParserElement,
    PrecededBy,
    QuotedString,
    Regex,
    StringEnd,
    rest_of_line,
    White,
    Word,
    ZeroOrMore,
)

from . import model


OPERATORS = [
    "+",
    "-",
    "*",
    ".*",
    "/",
    "./",
    "^",
    ".^",
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
    "methods",
    "otherwise",
    "parfor",
    "persistent",
    "properties",
    "return",
    "spmd",
    "switch",
    "try",
    "while",
]

# Turn-off the default behavior of ignoring whitespace. Whitespace parsing will be handled manually.
ParserElement.set_default_whitespace_chars("")


def nothing(n: int = 1):
    return Empty().set_parse_action(
        lambda s, loc, toks: [model.Missing() for i in range(n)]
    )


def empty_string(n: int = 1):
    return Empty().set_parse_action(lambda s, loc, toks: [model.Literal("") for i in range(n)])


def or_none(expr: ParserElement):
    """Parse expr or return Missing if not found."""
    return Opt(expr, default=model.Missing())

def or_empty(expr: ParserElement):
    """Parse expr or return an empty Literal if not found."""
    return Opt(expr, default=model.Literal(""))


def join_strings(s, loc, toks):
    return model.Literal("".join(str(t) for t in toks))


class ReservedKeyword(ParserElement):
    """A reserved keyword."""

    def __init__(self):
        super().__init__()
        self.parser = Or(Literal(s) for s in KEYWORDS)

    def parseImpl(self, instring, loc, doActions=True):
        return self.parser._parse(instring, loc, doActions)

    def _generateDefaultName(self) -> str:
        return "ReservedKeyword"


"""White space including ellipsis."""
ws = Combine(
    (
        White(" \t\n") 
        | Literal("...")
    )[1, ...]
).parse_with_tabs() # fmt: skip

"""Optional white space"""
ows = Opt(ws, default=model.Literal("")).parse_with_tabs()

element_delimiter = Combine(
    (
        White(" \t") 
        | (Literal("...") + Regex(r"[ \t]*\n?[ \t]*"))
    )[1, ...]
).parse_with_tabs()

optional_element_delimiter = Opt(
    element_delimiter, default=model.Literal("")
).parse_with_tabs()

operator = Or(OPERATORS)


class Leaf(ParserElement):
    """Parser for the model.Leaf object. A leaf consists only af a string and does not contain child elements."""

    def __init__(self, literal: str):
        super().__init__()
        self.parser = Literal(literal)

    def parseImpl(self, instring, loc, doActions=True):
        loc, tokens = self.parser._parse(instring, loc, doActions)
        assert len(tokens) == 1
        return loc, model.Literal(tokens[0])

    def _generateDefaultName(self) -> str:
        return "Leaf"


class DelimitedList(ParserElement):
    """
    Parser for delimited list.

    Converts tokens into a model.DelimitedList object while parsing.
    """

    def __init__(
        self,
        element: ParserElement,
        delimiter: str | ParserElement,
        min_elements: int = 1,
        delimiter_is_optional: bool = False,
    ):
        super().__init__()

        if isinstance(delimiter, str):
            delimiter = Literal(delimiter)
        delimiter = ows + delimiter + ows
        if delimiter_is_optional:
            delimiter = delimiter | ws
        delimiter.add_parse_action(
            lambda s, loc, toks: model.Literal("".join(str(t) for t in toks))
        )
        min_sub_exp = max(min_elements - 1, 0)
        self.parser = (
            (
                element 
                + delimiter 
                + FollowedBy(element)
            )[min_sub_exp, ...] 
            + element
        ) # fmt: skip
        if min_elements == 0:
            self.parser = self.parser | empty

    def parseImpl(self, instring, loc, doActions=True):
        loc, tokens = self.parser._parse(instring, loc, doActions)
        return loc, model.DelimitedList(list(tokens))

    def _generateDefaultName(self) -> str:
        return "DelimitedList"


class Block(ParserElement):

    def __init__(
        self,
        name: str,
        content: ParserElement,
        head: ParserElement | None = None,
        end: bool | str = True,
    ):
        super().__init__()

        head = head if head else nothing()

        end_placeholder = empty_string() + nothing()

        end_element = ows + Leaf("end")
        if isinstance(end, str):
            assert end == "optional"
            end_element |= end_placeholder
        elif not end:
            end_element = end_placeholder

        self.parser = (
            Leaf(name)
            + (
                (optional_element_delimiter + head)
                | nothing(2)
            )
            + (
                (construct_delimiter + content)
                | nothing(2)
            )
            + end_element
        )

    def parseImpl(self, instring, loc, doActions=True):
        return self.parser._parse(instring, loc, doActions)

    def _generateDefaultName(self) -> str:
        return "Block"


def ows_delimited_list(expr: ParserElement, allow_empty: bool = False) -> ParserElement:
    result = expr + ZeroOrMore(construct_delimiter + expr)
    if allow_empty:
        result = result | empty
    return result


def parenthesized(
    content: ParserElement,
    brackets: Sequence[tuple[str, str]] = (("(", ")"),),
    optional: bool = False,
):
    # Turning this into a class was a lot slower for some reason
    with_parenthesis = Or(
        (
            Leaf(opening_bracket) 
            + ows 
            + content 
            + ows 
            + Leaf(closing_bracket)
        ) for opening_bracket, closing_bracket in brackets
    ) # fmt: skip

    if not optional:
        parser = with_parenthesis
    else:
        without_parenthesis = (
            nothing() + empty_string() + content + empty_string() + nothing()
        )
        parser = with_parenthesis | without_parenthesis
    return parser.add_parse_action(model.Parenthesized.from_tokens).set_name(
        "Parenthesized"
    )


"""
A string identifying a variable, function or class. Includes namespace syntax.
Examples:
 - test123
 - a.b.c
"""
identifier_pattern = {
    "Initial": r"[A-Za-z]",
    "Body": r"[\w.]*",
    "DontEndWithDot": r"(?<!\.)",
}

identifier = (
    ~ReservedKeyword() 
    + Regex("".join(identifier_pattern.values()))
) # fmt: skip

"""A comment. Starts at the comment marker '%' end ends before the next line break."""
comment = Leaf("%") + rest_of_line.add_parse_action(model.Literal.from_tokens)


construct_delimiter = (
    ows + Literal(";") + ows
    | Regex(r"[ \t]*\n") + empty_string() + ows
    | Regex(r"[ \t]*") + empty_string() + ows + FollowedBy(Literal("%"))
    # | line_end
)


"""A quoted string with single or double quotes."""
string = (
    QuotedString(quote_char='"', esc_quote='""', unquote_results=False) | 
    QuotedString(quote_char="'", esc_quote="''", unquote_results=False)
) # fmt: skip

expression = Forward()

"""Array"""
array_delimiter = Leaf(",") | Leaf(";")
array = parenthesized(
    DelimitedList(
        expression,
        min_elements=0,
        delimiter=array_delimiter,
        delimiter_is_optional=True,
    ),
    brackets=(("[", "]"), ("{", "}")),
).set_name("Array")

call = Forward()

output_arguments = (
    parenthesized(
        DelimitedList(call, delimiter=","),
        brackets=(("[", "]"),),
        optional=True,
    )
    + ows
    + Leaf("=")
    + ows
)

output_statement = Forward()

argument_brackets = (("(", ")"), ("{", "}"))
argument = output_statement | expression | Leaf(":")
arguments_list = (
    or_none(Leaf("."))
    + parenthesized(
        DelimitedList(argument, delimiter=",", min_elements=0), 
        brackets=argument_brackets,
    )
) # fmt: skip

"""A variable or a function call with or without arguments. Includes nested calls."""
call << (identifier + or_none(arguments_list[1, ...]))

"""
Anonymous function definition
Examples: 
 - @(x) x + 1
 - @mean
"""
anonymous_function = Leaf("@") + ows + or_none(arguments_list) + ows + expression

# number = common.number.set_parse_action(model.Literal.from_tokens)
number = Regex(r"[-+\d][\d.eE]*").set_parse_action(model.Literal.from_tokens)

operand_atom = Forward()
operation = Forward()
operand = Forward()
operand_atom << (
    call
    | number
    | string
    | array
    | anonymous_function
    | parenthesized(operand)
    | parenthesized(operation)
)

left_operation = (Leaf("-") | Leaf("~")) + operand_atom
right_operation = operand_atom + (Leaf("'") | Leaf(".'"))

single_element_operation = left_operation | right_operation

operand << (
    single_element_operation
    | operand_atom
    | parenthesized(operand)
    | parenthesized(operation)
)
operation << DelimitedList(operand, delimiter=operator, min_elements=2)
expression << (operation | operand)

keyword = Or(Leaf(kw) for kw in ["return", "break", "continue"])

"""An assignment or an expression with either no result or an unused result."""

statement_core = expression | keyword

no_output_statement = nothing(1) + statement_core
output_statement << (output_arguments + statement_core)
statement = output_statement | no_output_statement

code = Forward()

elseif_block_part = Leaf("elseif") + ws + no_output_statement + ws + code

else_block_part = Leaf("else") + ws + code

"""If block including possible "elseif" and "else" subblocks."""
if_block = Block(
    name="if",
    head=no_output_statement,
    content=(code + ZeroOrMore(ws + elseif_block_part) + Opt(ws + else_block_part)),
    end=True,
)

"""For-loop code block."""
for_loop = Block(
    name="for",
    head=output_statement,
    content=code,
    end=True,
)

"""While-loop code block."""
while_loop = Block(name="while", head=no_output_statement, content=code)

"""Function definition block."""
function = Block(name="function", head=statement, content=code, end="optional")

catch = (
    Leaf("catch")
    + Opt(White(" \t") + statement_core, default=model.Missing()).add_parse_action(
        lambda toks: ["", ""] if toks[0] is None else toks
    )
    + ws
    + code
)

try_catch = Block(name="try", content=(code + or_none(ws + catch)))

"""'case'-block within a switch statement."""
switch_case = Block(name="case", head=no_output_statement, content=code, end=False)

"""'otherwise'-block within a switch statement."""
switch_otherwise = Block(name="otherwise", content=code, end=False)

"""Switch statement code block"""
switch = Block(
    name="switch",
    head=no_output_statement,
    content=code
)

classdef = Block(
    name="classdef",
    head=identifier,
    content=code,
)

properties = Block(
    name="properties",
    head=or_none(arguments_list),
    content=code,
)

methods = Block(
    name="methods",
    head=or_none(arguments_list),
    content=code,
)

command_identifier = Combine(identifier + Opt(".*"))
command = (
    command_identifier 
    + ZeroOrMore(element_delimiter + command_identifier)
    + (StringEnd() | FollowedBy(construct_delimiter))
)

any_block = (
    if_block
    | for_loop
    | while_loop
    | function
    | try_catch
    | switch
    | classdef
    | methods
    | properties
    | switch_case
    | switch_otherwise
)

code << ows_delimited_list(command | statement | comment | any_block, allow_empty=True)

"""A file consisting of code wrapped by optional white space."""
file = ows + code + ows

# Packrat gives a massive performance increase.
file.enable_packrat()

# Add parse actions to grammar objects that turn the tokens into the respective dataclass.
parse_actions = {
    arguments_list: model.ArgumentsList,
    function: model.Function,
    if_block: model.If,
    try_catch: model.TryCatch,
    for_loop: model.ForLoop,
    while_loop: model.WhileLoop,
    call: model.Call,
    output_arguments: model.OutputArguments,
    comment: model.Comment,
    operation: model.Operation,
    no_output_statement: model.Statement,
    output_statement: model.Statement,
    code: model.Code,
    anonymous_function: model.AnonymousFunction,
    array: model.Array,
    single_element_operation: model.SingleElementOperation,
    file: model.File,
    switch: model.Switch,
    switch_case: model.Case,
    switch_otherwise: model.Case,
    command: model.Command,
    classdef: model.Classdef,
    methods: model.Methods,
    properties: model.Properties,
    command_identifier: model.Literal,
    identifier: model.Literal,
    ws: model.Literal,
    element_delimiter: model.Literal,
    construct_delimiter: model.ConstructDelimiter,
    string: model.Literal,
}

for parser_element, target_class in parse_actions.items():
    parser_element.add_parse_action(target_class.from_tokens)


def parse_string(s: str) -> model.File:
    """Parse a MATLAB code string and return its representation model."""
    parse_result = file.parse_string(s, parse_all=True)

    file_: model.File = parse_result[0]
    for element in itertools.chain([file_], file_.descendants()):
        if isinstance(element, model.Composite):
            children = list(element)
            for i, child in enumerate(children):
                child.parent = element
                if i > 0:
                    child.predecessor = children[i - 1]
                if i < len(children) - 1:
                    child.successor = children[i + 1]

    return file_  # type: ignore


def parse_file(file_path: Path | str) -> model.File:
    """Parse a MATLAB .m file and return its representation model."""
    string = Path(file_path).read_text()
    return parse_string(string)
