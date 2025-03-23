import model


def normalize_whitespace_in_arguments_list(code: model.Element):
    types = [model.OutputArguments, model.ArgumentsList]
    for output_arguments in code.iterate(types):
        output_arguments: model.OutputArguments

        for i, token in enumerate(output_arguments.arguments_list):
            if i % 2 == 0:
                continue
            else:
                token: str = token
                token = token.strip() + " "
                output_arguments.arguments_list.children[i] = token


def normalize_whitespace_in_parenthesized(code: model.Element):
    types = [model.Parenthesized]
    for element in code.iterate(types):
        element: model.Parenthesized
        for index in [1, 3]:
            element.children[index] = ""


def normalize_whitespace_in_assignment(code: model.Element):
    types = [model.OutputArguments]
    for element in code.iterate(types):
        element: model.OutputArguments
        for index in [1, 3]:
            element.children[index] = " "


def remove_semicolon_after_end(code: model.Element):
    types = [model.Block]
    for element in code.iterate(types):
        element: model.Block
        if element.children[-1] == ";":
            element.children[-1] = ""
