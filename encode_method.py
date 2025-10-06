from lawu import ast


class EncodeMethod:
    __slots__ = ('method')

    def __init__(self, method: ast.Method):
        print(method.pretty())
        self.method = method