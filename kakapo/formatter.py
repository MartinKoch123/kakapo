from unittest import case

from . import model


INDENT = 4 * " "


def format_type(type_: type[model.Component]):
    def decorator(func):
        def wrapper(code: model.Component):
            for element in code.iterate():
                if isinstance(element, type_):
                    func(element)

        return wrapper

    return decorator


@format_type(model.ElementsList)
def normalize_whitespace_in_arguments_list(elements_list: model.ElementsList):
    for i, token in enumerate(elements_list.elements_list):
        # Children 1, 3, ... are whitespace and delimiters.
        if i % 2 == 0:
            continue
        string: str = token.value
        string = string.strip(" \n\t")  # Remove whitespace surrounding delimiter
        string = string.replace("...", "")  # Remove ellipsis
        string += " "  # Add single space after delimiter.
        if isinstance(elements_list, model.Operation):
            string = " " + string
        elements_list.elements_list.children[i] = model.Leaf(string)


@format_type(model.Parenthesized)
def normalize_whitespace_in_parenthesized(parenthesized: model.Parenthesized):
    parenthesized.whitespace_before_content = ""
    parenthesized.whitespace_after_content = ""


@format_type(model.OutputArguments)
def normalize_whitespace_in_assignment(output_arguments: model.OutputArguments):
    """Ensure equality sign of assignment is surrounded by single spaces."""
    output_arguments.whitespace_before_equal_sign = " "
    output_arguments.whitespace_after_equal_sign = " "


@format_type(model.Block)
def remove_white_space_and_semicolon_after_end_keyword(block: model.Block):
    """Remove optional semicolon after the 'end' keyword."""
    block.whitespace_before_semicolon = ""
    block.semicolon = ""


@format_type(model.If)
def remove_white_space_and_semicolon_after_if_condition(if_statement: model.If):
    head: model.Statement = if_statement.head
    head.whitespace_before_semicolon = ""
    head.semicolon = ""


def remove_white_space_and_semicolon_after_keyword(code: model.Component):
    for element in code.iterate():
        match element:
            case model.Statement(
                body=model.Leaf(value="return" | "break" | "continue")
            ):
                element.whitespace_before_semicolon = ""
                element.semicolon = ""


@format_type(model.Statement)
def remove_white_space_before_semicolon(statement: model.Statement):
    statement.whitespace_before_semicolon = ""


@format_type(model.Function)
def ensure_function_end(function: model.Function):
    """Ensure function block ends with 'end' keyword."""
    if function.whitespace_before_end == "":
        function.whitespace_before_end = "\n"
    function.end_keyword = "end"


def normalize_trailing_whitespace(file: model.File):
    """Remove all trailing whitespace in a file and add a newline."""
    file.trailing_whitespace = "\n"


def normalize_leading_whitespace(file: model.File):
    """Remove all leading whitespace in a file."""
    file.leading_whitespace = ""


def ensure_comment_leading_space(element: model.Component):
    """Ensure there is a single space after the comment marker if the comment is not empty."""
    for element in element.iterate():
        match element:
            case model.Comment(content=c) if c and not c.startswith(" "):
                element.content = " " + c


@format_type(model.Code)
def ensure_empty_line_before_comment(code: model.Code):
    """Ensures an empty line before each block of comments."""
    for i, child in enumerate(code.children):
        if i < 2:
            continue
        if not isinstance(child, model.Comment):
            continue
        predecessor = code.children[i - 1]
        prepredecessor = code.children[i - 2]
        if isinstance(prepredecessor, model.Comment):
            continue
        assert type(predecessor) is str

        # Inline comment, or already has an empty line before it.
        if predecessor.count("\n") != 1:
            continue
        code.children[i - 1] = "\n" + predecessor


def normalize_indentation(element: model.Component):

    for element, level in element.iterate_with_indent():

        if not isinstance(element, model.Construct) and (
            not isinstance(element, model.Leaf)
            or element.value not in ["end", "elseif", "else"]
        ):
            continue
        parent = element.parent

        element_is_block_head = (
            parent
            and isinstance(parent, model.Block)
            and type(parent.head) is type(element)
            and parent.head == element
        )
        if element_is_block_head:
            continue

        # Workaround for for elseif. #TODO refactor model.If
        own_index = parent.index_of_child(element)
        if (
            own_index > 1
            and isinstance(parent[own_index - 2], model.Leaf)
            and parent[own_index - 2].value == "elseif"
        ):
            continue

        indent = level * INDENT

        if element.predecessor is not None:
            assert type(element.predecessor) is str
            new: str = element.predecessor.rstrip(" ")
            if not new.endswith("\n"):
                new += "\n"

            element.predecessor = new + indent

        elif parent is not None and parent.predecessor is not None:
            assert type(parent.predecessor) is str
            new: str = parent.predecessor.rstrip(" ")
            if not new.endswith("\n"):
                new += "\n"
            parent.predecessor = new + indent


def break_arguments(element: model.Component, max_line_length: int = 120):
    for element, level in element.iterate_with_indent():

        if not isinstance(element, model.Statement):
            continue

        outer_indent = level * INDENT
        inner_indent = (level + 1) * INDENT

        line_length = len(str(element) + inner_indent)
        if line_length <= max_line_length:
            continue

        body = element.body
        if not isinstance(body, model.Call):
            continue

        args_list = body.arguments_list
        if args_list is None:
            continue

        args_list[1][1] = " ...\n" + inner_indent

        for i, token in enumerate(args_list.elements_list):
            if i % 2 == 0:
                continue

            args_list.elements_list[i] = ", ...\n" + inner_indent

        args_list[1][3] = " ...\n" + outer_indent


def format_file(file: model.File):
    normalize_whitespace_in_arguments_list(file)
    normalize_whitespace_in_parenthesized(file)
    normalize_whitespace_in_assignment(file)
    remove_white_space_and_semicolon_after_end_keyword(file)
    remove_white_space_and_semicolon_after_if_condition(file)
    remove_white_space_before_semicolon(file)
    remove_white_space_and_semicolon_after_keyword(file)
    normalize_indentation(file)
    ensure_function_end(file)
    normalize_leading_whitespace(file)
    normalize_trailing_whitespace(file)
    ensure_empty_line_before_comment(file)
    ensure_comment_leading_space(file)
    break_arguments(file)
