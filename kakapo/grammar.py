"""
Parsing logic for MATLAB code.
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
    FollowedBy,
    Forward,
    Keyword,
    Literal,
    Opt,
    Or,
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
from pyparsing.tools.cvt_pyparsing_pep8_names import pre_pep8_arg_name, pre_pep8_method_name

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


class ReservedKeyword(ParserElement):
    """A reserved keyword."""

    def __init__(self):
        super().__init__()
        self.parser = Or(Keyword(s) for s in KEYWORDS).add_parse_action(model.Literal.from_tokens)

    def parseImpl(self, instring, loc, doActions=True):
        return self.parser._parse(instring, loc, doActions)

    def _generateDefaultName(self) -> str:
        return "ReservedKeyword"


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
        body: ParserElement,
        head: ParserElement | None = None,
        optional_head: bool = False,
        optional_head_delimiter: bool = False,
        end: bool | str = True,
    ):
        super().__init__()

        if optional_head_delimiter:
            pre_head_delimiter = element_delimiter | empty_string()
        else:
            pre_head_delimiter = element_delimiter

        end_placeholder = empty_string() + nothing()

        end_element = end_delimiter + Leaf("end")
        if isinstance(end, str):
            assert end == "optional"
            end_element |= end_placeholder
        elif not end:
            end_element = end_placeholder

        if head is None:
            head_parser = nothing(2)
            pre_body_delimiter = regex_literal(r"[ \t\n;]*")
        else:
            if optional_head:
                head_parser = (pre_head_delimiter + head) | nothing(2)
            else:
                head_parser = pre_head_delimiter + head
            pre_body_delimiter = statement_delimiter

        body_parser = (pre_body_delimiter + body) | nothing(2)

        self.parser = (
            Keyword(name).add_parse_action(model.Literal.from_tokens)
            + head_parser
            + body_parser
            + end_element
        ) # fmt: skip

    def parseImpl(self, instring, loc, doActions=True):
        return self.parser._parse(instring, loc, doActions)

    def _generateDefaultName(self) -> str:
        return "Block"


def nothing(n: int = 1):
    return Empty().set_parse_action(
        lambda s, loc, toks: [model.Missing() for i in range(n)]
    )


def empty_string(n: int = 1):
    return Empty().set_parse_action(
        lambda s, loc, toks: [model.Literal("") for i in range(n)]
    )


def join_strings(s, loc, toks):
    return model.Literal("".join(str(t) for t in toks))


def regex_literal(pattern: str) -> ParserElement:
    return Regex(pattern).add_parse_action(model.Literal.from_tokens)


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


"""White space including ellipsis."""
ws = Combine(
    (
        White(" \t\n") 
        | Literal("...")
    )[1, ...]
).parse_with_tabs() # fmt: skip


"""Optional white space"""
ows = (ws | empty_string()).parse_with_tabs()


element_delimiter = Combine(
    (
        White(" \t") 
        | (Literal("...") + Regex(r"[ \t]*\n?[ \t]*"))
    )[1, ...]
).parse_with_tabs() # fmt: skip


statement_delimiter = Combine(
    ows + Leaf(";") + ows
    | regex_literal(r"[ \t]*\n") + empty_string() + ows
    | regex_literal(r"[ \t]*") + empty_string() + ows + FollowedBy(Literal("%"))
)

end_delimiter = regex_literal(r"[ \t\n;]+")

operator = Or(OPERATORS)


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

assignment_target = (
    parenthesized(
        DelimitedList(call | identifier, delimiter=","),
        brackets=(("[", "]"),),
        optional=True,
    )
    + ows
    + Leaf("=")
    + ows
)

assignment_statement = Forward()

argument_brackets = (("(", ")"), ("{", "}"))
argument = assignment_statement | expression | Leaf(":")
arguments_list = (
    (Leaf(".") | nothing(1))
    + parenthesized(
        DelimitedList(argument, delimiter=",", min_elements=0), 
        brackets=argument_brackets,
    )
) # fmt: skip

"""A variable or a function call with or without arguments. Includes nested calls."""
call << (
    identifier
    + arguments_list[1, ...]
) # fmt: skip

def nest_calls(s, loc, toks):
    result = model.Call.from_tokens(toks[:2])  # base + first args
    for args in toks[2:]:
        result = model.Call.from_tokens([result, args])
    return result

call.add_parse_action(nest_calls)

"""
Anonymous function definition
Examples: 
 - @(x) x + 1
 - @mean
"""
anonymous_function = (
    Leaf("@") 
    + ows 
    + (arguments_list | nothing(1)) 
    + ows 
    + expression
)

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
    | identifier
    | anonymous_function
    | parenthesized(operand)
    | parenthesized(operation)
)

prefix_operation = (Leaf("-") | Leaf("~")) + operand_atom
postfix_operation = operand_atom + (Leaf("'") | Leaf(".'"))

unary_operation = prefix_operation | postfix_operation

operand << (
        unary_operation
        | operand_atom
        | parenthesized(operand)
        | parenthesized(operation)
)
operation << DelimitedList(operand, delimiter=operator, min_elements=2)
expression << (operation | operand)

keyword_statement = Or(Leaf(kw) for kw in ["return", "break", "continue"])


statement_core = expression | keyword_statement
"""An assignment or an expression with either no result or an unused result."""

expression_statement = nothing(1) + statement_core
assignment_statement << (assignment_target + statement_core)
statement = assignment_statement | expression_statement

code = Forward()

if_ = Block(
    name="if",
    head=expression_statement,
    body=code,
    end=True,
)

else_ = Block(name="else", body=code, end=False)  # End belongs to if-block.

else_if = Block(
    name="elseif",
    head=expression_statement,
    body=code,
    end=False,  # End belongs to if-block.
)


for_ = Block(
    name="for",
    head=assignment_statement,
    body=code,
    end=True,
)
"""For-loop code block."""


while_ = Block(name="while", head=expression_statement, body=code)
"""While-loop code block."""


function = Block(name="function", head=statement, body=code, end="optional")
"""Function definition block."""


catch = Block(
    name="catch",
    head=identifier,
    optional_head=True,
    body=code,
    end=False,
)
"""'catch'-block of a try-catch block."""


try_ = Block(name="try", body=code)

switch_case = Block(name="case", head=expression_statement, body=code, end=False)
"""'case'-block of a switch statement."""


switch_otherwise = Block(name="otherwise", body=code, end=False)
"""'otherwise'-block of a switch statement."""


switch = Block(name="switch", head=expression_statement, body=code)
"""Switch statement code block"""

classdef = Block(
    name="classdef",
    head=identifier,
    body=code,
)

properties = Block(
    name="properties",
    head=arguments_list,
    body=code,
    optional_head=True,
)

methods = Block(
    name="methods",
    head=arguments_list,
    body=code,
    optional_head=True,
    optional_head_delimiter=True
)

command_identifier = Combine(identifier + Opt(".*"))
command = (
    command_identifier
    + ZeroOrMore(element_delimiter + command_identifier)
    + (StringEnd() | FollowedBy(statement_delimiter))
)

any_block = (
    catch
    | classdef
    | else_
    | else_if
    | if_
    | for_
    | function
    | methods
    | properties
    | switch
    | switch_case
    | switch_otherwise
    | try_
    | while_
)


code_element = command | statement | comment | any_block
code << code_element + ZeroOrMore(statement_delimiter + code_element)


file = (
    regex_literal(r"[ \t\n;]*") 
    + (code | nothing(1)) 
    + (regex_literal(r"[ \t\n;]*") | (empty_string() + StringEnd())) # Regex fails mysteriously at string end.
)
"""A file consisting of code wrapped by optional white space."""


# Packrat gives a massive performance increase.
file.enable_packrat()

# Add parse actions to grammar objects that turn the tokens into the respective dataclass.
parse_actions = {
    anonymous_function: model.AnonymousFunction,
    array: model.Array,
    arguments_list: model.ArgumentsList,
    expression_statement: model.Statement,
    catch: model.Catch,
    classdef: model.Classdef,
    code: model.Code,
    command: model.Command,
    command_identifier: model.Literal,
    comment: model.Comment,
    statement_delimiter: model.Literal,
    element_delimiter: model.Literal,
    else_: model.Else,
    else_if: model.ElseIf,
    file: model.File,
    for_: model.ForLoop,
    function: model.Function,
    identifier: model.Literal,
    if_: model.If,
    methods: model.Methods,
    operation: model.Operation,
    assignment_target: model.AssignmentTarget,
    assignment_statement: model.Statement,
    postfix_operation: model.PostfixOperation,
    prefix_operation: model.PrefixOperation,
    properties: model.Properties,
    string: model.Literal,
    switch: model.Switch,
    switch_case: model.Case,
    switch_otherwise: model.Case,
    try_: model.Try,
    while_: model.WhileLoop,
    ws: model.Literal,
}

for parser_element, target_class in parse_actions.items():
    parser_element.add_parse_action(target_class.from_tokens)


def parse_string(s: str) -> model.File:
    """Parse a MATLAB code string and return its representation model."""
    parse_result = file.parse_string(s, parse_all=True)

    file_: model.File = parse_result[0]
    for element in itertools.chain([file_], file_.descendants()):
        if not isinstance(element, model.Composite):
            continue
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
