from unittest import case

from . import model


INDENT = 4 * " "


def normalize_whitespace_in_arguments_list(code: model.Component):
    for element in code.iterate():
        match element:
            case model.ElementsList():
                for i, token in enumerate(element.elements_list):
                    # Children 1, 3, ... are whitespace and delimiters.
                    if i % 2 == 0:
                        continue
                    token: str = token
                    token = token.strip(" \n\t")  # Remove whitespace surrounding delimiter
                    token = token.replace("...", "")  # Remove ellipsis
                    token += " "  # Add single space after delimiter.
                    if isinstance(element, model.Operation):
                        token = " " + token
                    element.elements_list.children[i] = token


def normalize_whitespace_in_parenthesized(code: model.Composite):
    for element in code.iterate():
        match element:
            case model.Parenthesized():
                element.whitespace_before_content = ""
                element.whitespace_after_content = ""


def normalize_whitespace_in_assignment(code: model.Component):
    """Ensure equality sign of assignment is surrounded by single spaces."""
    for element in code.iterate():
        match element:
            case model.OutputArguments():
                element.whitespace_before_equal_sign = " "
                element.whitespace_after_equal_sign = " "


def remove_white_space_and_semicolon_after_end_keyword(code: model.Component):
    """Remove optional semicolon after the 'end' keyword."""
    for element in code.iterate():
        match element:
            case model.Block():
                element.whitespace_before_semicolon = ""
                element.semicolon = ""


def remove_white_space_and_semicolon_after_if_condition(code: model.Component):
    for element in code.iterate():
        match element:
            case model.If():
                head: model.Statement = element.head
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


def remove_white_space_before_semicolon(code: model.Component):
    for element in code.iterate():
        match element:
            case model.Statement():
                element.whitespace_before_semicolon = ""


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


def ensure_function_end(element: model.Component):
    """Ensure function block ends with 'end' keyword."""
    for element in element.iterate():
        match element:
            case model.Function():
                if element.whitespace_before_end == "":
                    element.whitespace_before_end = "\n"
                element.end_keyword = "end"


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


def ensure_empty_line_before_comment(element: model.Component):
    """Ensures an empty line before each block of comments."""
    for element in element.iterate():
        match element:
            # case model.Comment() if element.predecessor is not None:
            #     assert type(element.predecessor) is str

            #     parent = element.parent
            #     i_element = parent.index_of_child(element)

            #     if isinstance(parent[i_element - 2], model.Comment):
            #         continue

            #     if element.predecessor.count("\n") < 2:
            #         parent[i_element - 1] = "\n" + element.predecessor
            case model.Code():
                for i, child in enumerate(element.children):
                    if i < 2:
                        continue
                    if not isinstance(child, model.Comment):
                        continue
                    predecessor = element.children[i - 1]
                    prepredecessor = element.children[i - 2]
                    if isinstance(prepredecessor, model.Comment):
                        continue
                    assert type(predecessor) is str
                    if predecessor.count("\n") != 1: # Inline comment, or already has an empty line before it.
                        continue
                    element.children[i - 1] = "\n" + predecessor
                    




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
