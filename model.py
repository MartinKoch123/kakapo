from typing import Sequence


class Element:

    _parser = None

    def __init__(self, tokens: Sequence):
        self.children = tokens

    def __iter__(self):
        return iter(self.children)

    def __str__(self):
        return "".join(str(tok) for tok in self if tok is not None)

    def __getitem__(self, item: int):
        return self.children[item]

    def __len__(self):
        return len(self.children)

    def __repr__(self):
        name = self.__class__.__name__
        return f"{name}({self.children})"

    def __eq__(self, other):
        """Elements are equal if they have equal type and their children are equal."""
        return (
            type(self) == type(other)
            and len(self) == len(other)
            and all(own_child == other_child for own_child, other_child in zip(self, other))
        )

    def pretty_string(self, indent_level: int = 0, compact: bool = False) -> str:
        indent = indent_level * 4 * " "
        type_ = self.__class__.__name__

        head = f"{type_}(["
        tail = f"])"

        if all(not isinstance(child, Element) for child in self):
            body = ", ".join(repr(child) for child in self)
            return indent + head + body + tail

        body_parts = []
        for child in self:
            if isinstance(child, Element):
                body_parts += [child.pretty_string(indent_level + 1, compact)]
            else:
                if compact and none_or_whitespace(child):
                    continue
                body_parts += [f"{indent}    {child!r},"]
        body = '\n'.join(body_parts)
        return f"{indent}{head}\n{body}\n{indent}{tail}"

    def to_list(self) -> list:
        return [c.to_list() if isinstance(c, Element) else c for c in self]

    def to_repr_list(self) -> list:
        return [c.to_repr_list() if isinstance(c, Element) else c for c in self]

    @classmethod
    def from_tokens(cls, tokens: Sequence):
        return cls(list(tokens))


class ArgumentsList(Element):

    _OPENING_PARENTHESIS = 0
    _DELIMITED_LIST = 2
    _CLOSING_PARENTHESIS = 4

    @property
    def elements(self):
        return self.children[self._DELIMITED_LIST].elements


class OutputArgumentList(Element):

    @property
    def elements(self):
        delimited_list: DelimitedList = self.children[2]
        return delimited_list.elements


class Call(Element):

    _IDENTIFIER = 0
    _ARGUMENTS_LIST = 1

    @property
    def arguments_list(self) -> ArgumentsList | None:
        return self.children[self._ARGUMENTS_LIST]

    @property
    def arguments(self) -> Sequence:
        if self.arguments_list is None:
            return tuple()
        delimited_list: DelimitedList = self.children[1]
        return delimited_list.elements


class Function(Element):

    _OUTPUT_ARGUMENTS = 2
    _ARGUMENTS_LIST = 3
    _CODE = 5

    @property
    def code(self):
        return self[self._CODE]


class Comment(Element):

    _PERCENTAGE_SIGN = 0
    _STRING = 1

    @property
    def string(self):
        return self[self._STRING]


class Operation(Element):
    pass


class ParenthesizedOperation(Element):
    pass


class Statement(Element):

    _OUTPUT_ARGUMENTS = 0
    _BODY = 1

    @property
    def output_arguments(self) -> Sequence:
        output_args_list = self[self._OUTPUT_ARGUMENTS]
        if output_args_list is None:
            return tuple()
        return output_args_list.elements

    @property
    def body(self):
        return self[self._BODY]


class Code(Element):
    pass


class DelimitedList(Element):

    @property
    def elements(self) -> list:
        return self.children[::4]

    @classmethod
    def build(cls, elements: Sequence[Element | str], delimiter: str = ",", left_white: str = "", right_white: str = " "):
        tokens = [elements[0]]
        for element in elements[1:]:
            tokens += [left_white + delimiter + right_white, element]
        return cls(tokens)


class Block(Element):

    @property
    def name(self) -> str:
        return self.children[0]

    @property
    def content(self) -> list:
        return self.children[2:-2]


class AnonymousFunction(Element):

    @property
    def arguments(self) -> list:
        if self.children[1] is None:
            return []
        delimited_list: DelimitedList = self.children[1]
        return delimited_list.elements

    @property
    def expression(self):
        return self.children[3]


class Array(Element):
    @property
    def elements(self) -> list:
        if self.children[2] is None:
            return []
        delimited_list: DelimitedList = self.children[2]
        return delimited_list.elements


class SingleElementOperation(Element):
    pass


def none_or_whitespace(x) -> bool:
    return x is None or isinstance(x, str) and (x.isspace() or x == "")