import bbcode


class BBCodeTag:

    def __init__(self, name, description, on_open=None, on_close=None):
        self.name = name
        self.description = description
        self.on_open = on_open
        self.on_close = on_close


class BBCodeAdapter:
    tags = [
        BBCodeTag(
            name="m",
            description="Medium-sized text",
            on_open=lambda p: p.set_size("M"),
            on_close=lambda p: p.set_size("S"),
        ),
        BBCodeTag(
            name="l",
            description="Large-sized text",
            on_open=lambda p: p.set_size("L"),
            on_close=lambda p: p.set_size("S"),
        ),
    ]

    def __init__(self, printer):
        self.printer = printer

    def print(self, raw):
        parser = bbcode.Parser()
        parser.add_simple_formatter("m", "%(value)s")
        parser.add_simple_formatter("l", "%(value)s")
        tokens = parser.tokenize(raw)
        for token in tokens:
            token_type, tag_name, _, token_text = token
            if token_type == bbcode.Parser.TOKEN_DATA:
                self.printer.print(token_text)
            elif token_type == bbcode.Parser.TOKEN_NEWLINE:
                self.printer.print("\n")
            else:
                tag = next((t for t in BBCodeAdapter.tags if t.name == tag_name), None)
                if tag is None:
                    raise ValueError("{} is not a valid tag".format(tag_name))
                if token_type == bbcode.Parser.TOKEN_TAG_START:
                    tag.on_open(self.printer)
                else:
                    tag.on_close(self.printer)
